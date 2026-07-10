"""Broker providers — paper_local (offline sim) and ibkr (real paper account).

Security model, stated plainly: there are no API keys. IB Gateway runs on
YOUR machine, YOU log into it, and De Waag connects to 127.0.0.1 only.
Credentials never exist in this codebase, its config, or its logs.

Provider is chosen in config/broker.yaml. When 'ibkr' is selected and the
gateway is offline, orders are REFUSED with instructions — never silently
routed to the simulator. You must always know which venue filled you.
"""

from __future__ import annotations

import socket
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BROKER_CONFIG = REPO_ROOT / "config" / "broker.yaml"

# exchange column in the universe -> IBKR primary exchange
PRIMARY_EXCHANGE = {"NASDAQ": "NASDAQ", "NYSE": "NYSE", "EBR": "ENEXT.BE", "AMS": "AEB"}
# routing exchange (SMART works for all of these)
ROUTING = "SMART"
# symbols whose IBKR spelling differs from ours
IB_SYMBOL = {"BRK-B": "BRK B"}


def load_broker_config() -> dict:
    if BROKER_CONFIG.exists():
        cfg = yaml.safe_load(BROKER_CONFIG.read_text(encoding="utf-8")) or {}
    else:
        cfg = {}
    cfg.setdefault("provider", "paper_local")
    ib = cfg.setdefault("ibkr", {})
    ib.setdefault("host", "127.0.0.1")
    ib.setdefault("port", 7497)      # 7497 = PAPER port; 7496 would be live
    ib.setdefault("client_id", 7)
    return cfg


def contract_spec(symbol: str) -> dict:
    """Our symbol -> IBKR contract parameters, from the universe table."""
    from dewaag.vault import store

    u = store.load_universe().set_index("symbol")
    if symbol not in u.index:
        raise ValueError(f"unknown symbol {symbol}")
    row = u.loc[symbol]
    if row["tier"] == "fx":
        raise ValueError("FX reference series are not tradable")
    return {
        "symbol": IB_SYMBOL.get(symbol, symbol),
        "exchange": ROUTING,
        "primaryExchange": PRIMARY_EXCHANGE.get(str(row["exchange"]), ""),
        "currency": str(row["currency"]),
    }


def gateway_available(host: str = "127.0.0.1", port: int = 7497, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# --------------------------------------------------------------- IBKR ops

def _connect():
    """Fresh short-lived connection per operation — simple and robust for
    a daily-horizon system (no long-lived socket to babysit)."""
    from ib_async import IB

    cfg = load_broker_config()["ibkr"]
    ib = IB()
    ib.connect(cfg["host"], cfg["port"], clientId=cfg["client_id"], timeout=8, readonly=False)
    return ib


def ibkr_status() -> dict:
    cfg = load_broker_config()
    out = {"provider": cfg["provider"], "port": cfg["ibkr"]["port"],
           "connected": False, "account": None, "net_liquidation": None,
           "cash": None, "ib_positions": None}
    if not gateway_available(cfg["ibkr"]["host"], cfg["ibkr"]["port"]):
        return out
    try:
        ib = _connect()
        try:
            accounts = ib.managedAccounts()
            out["account"] = accounts[0] if accounts else None
            summary = {v.tag: v.value for v in ib.accountSummary()}
            out["net_liquidation"] = float(summary.get("NetLiquidation", 0) or 0)
            out["cash"] = float(summary.get("TotalCashValue", 0) or 0)
            out["ib_positions"] = len(ib.positions())
            out["connected"] = True
        finally:
            ib.disconnect()
    except Exception as e:  # noqa: BLE001 — status must never crash the app
        out["error"] = str(e)[:150]
    return out


def _valid(x) -> bool:
    return x is not None and x == x and x > 0  # x==x rejects NaN


def _live_quote(ib, contract) -> dict:
    """Bid/ask/last for pricing a MARKETABLE limit. We use DELAYED data
    (type 3) directly: it's free for Euronext (the paper account has no live
    subscription), enough to cross the spread — and it needs a few seconds to
    arrive, so we poll rather than guess a fixed sleep (that was the bug that
    left orders priced off a stale close)."""
    ib.reqMarketDataType(3)  # delayed (~15 min); free, no subscription needed
    t = ib.reqMktData(contract, "", False, False)
    for _ in range(16):       # poll up to ~8s for the delayed quote to populate
        ib.sleep(0.5)
        if _valid(t.ask) or _valid(t.bid) or _valid(t.last):
            break
    quote = {"bid": t.bid if _valid(t.bid) else None,
             "ask": t.ask if _valid(t.ask) else None,
             "last": t.last if _valid(t.last) else (t.close if _valid(t.close) else None)}
    try:
        ib.cancelMktData(contract)
    except Exception:  # noqa: BLE001
        pass
    return quote


def place_limit_order(symbol: str, side: str, shares: int,
                      fallback_price: float, wait_seconds: int = 18) -> dict:
    """Place a MARKETABLE DAY limit on the paper account and wait for a fill.

    We fetch the live quote and set the limit at (or just through) the current
    ask for a buy / bid for a sell — so it fills like a market order but with a
    price cap (Lesson 2: never a naked market order, but a stale limit that
    never crosses is just as useless). Unfilled remainder is cancelled — a
    forgotten resting order is a gift to informed traders (trap #2).
    """
    from ib_async import LimitOrder, Stock

    spec = contract_spec(symbol)
    ib = _connect()
    try:
        contract = Stock(spec["symbol"], spec["exchange"], spec["currency"],
                         primaryExchange=spec["primaryExchange"])
        ib.qualifyContracts(contract)
        q = _live_quote(ib, contract)

        if side == "BUY":
            ref = q["ask"] or q["last"] or fallback_price
            limit = round(ref * 1.003, 2)   # cross the ask + small buffer
        else:
            ref = q["bid"] or q["last"] or fallback_price
            limit = round(ref * 0.997, 2)
        priced_from = "live/delayed quote" if (q["ask"] or q["bid"] or q["last"]) else "stale close (NO market data)"

        order = LimitOrder("BUY" if side == "BUY" else "SELL", shares, limit, tif="DAY")
        trade = ib.placeOrder(contract, order)
        waited = 0.0
        while not trade.isDone() and waited < wait_seconds:
            ib.sleep(1)
            waited += 1
        status = trade.orderStatus.status
        filled = int(trade.orderStatus.filled or 0)
        avg = float(trade.orderStatus.avgFillPrice or 0)
        commission = None
        for f in trade.fills:
            if f.commissionReport and f.commissionReport.commission:
                commission = (commission or 0.0) + float(f.commissionReport.commission)
        if filled < shares and not trade.isDone():
            ib.cancelOrder(order)
            ib.sleep(1)

        note = None
        if filled < shares:
            if not (q["ask"] or q["bid"] or q["last"]):
                note = (f"no market data for {symbol} on your paper account — IBKR couldn't price a fill. "
                        f"Enable delayed data in TWS (Global Config → API, or the market-data settings) "
                        f"or add this exchange's data subscription. US names usually have free data; "
                        f"Euronext often needs it enabled.")
            else:
                note = (f"{filled}/{shares} filled at limit €{limit} (priced from {priced_from}, "
                        f"bid {q['bid']} / ask {q['ask']}). Remainder cancelled — the quote may have moved; retry.")
        return {"status": status, "filled": filled, "avg_price": avg,
                "commission": commission, "limit": limit, "quote": q, "note": note}
    finally:
        ib.disconnect()


def ibkr_positions() -> list[dict]:
    ib = _connect()
    try:
        out = []
        for p in ib.positions():
            out.append({"ib_symbol": p.contract.symbol, "exchange": p.contract.primaryExchange,
                        "currency": p.contract.currency, "shares": float(p.position),
                        "avg_cost": float(p.avgCost)})
        return out
    finally:
        ib.disconnect()
