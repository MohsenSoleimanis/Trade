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


def place_limit_order(symbol: str, side: str, shares: int,
                      limit_price: float, wait_seconds: int = 12) -> dict:
    """Place a DAY limit order on the paper account, wait briefly for a fill.

    Limit orders only (Lesson 2 is law at the venue too). If it doesn't fill
    within the wait, the order is CANCELLED and reported — a resting order
    you forgot is a gift to better-informed traders (trap #2).
    """
    from ib_async import LimitOrder, Stock

    spec = contract_spec(symbol)
    ib = _connect()
    try:
        contract = Stock(spec["symbol"], spec["exchange"], spec["currency"],
                         primaryExchange=spec["primaryExchange"])
        ib.qualifyContracts(contract)
        order = LimitOrder("BUY" if side == "BUY" else "SELL", shares,
                           round(limit_price, 2), tif="DAY")
        trade = ib.placeOrder(contract, order)
        ib.sleep(1)
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
        return {"status": status, "filled": filled, "avg_price": avg,
                "commission": commission,
                "note": None if filled == shares else
                f"only {filled}/{shares} filled within {wait_seconds}s — remainder cancelled "
                f"(adjust the limit toward the ask/bid and retry, or wait for the auction)"}
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
