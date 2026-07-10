"""The paper portfolio + local paper broker.

BROKER PROVIDERS (same pattern as the Agent Floor): today this is
`paper_local` — simulated fills at last close + half-spread, costs
included, entirely offline. When the IBKR paper account is approved,
an `ibkr` provider slots in behind the same execute() call and the
Trading Desk doesn't change one pixel.

State lives in data/portfolio.json — a file you can open and read,
like everything in the vault. Every trade is appended to the log with
its thesis: the decision journal starts at the first order.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from dewaag.constitution import load_constitution
from dewaag.engine.costs import estimate
from dewaag.engine.sizing import gate_order
from dewaag.vault import store

PORTFOLIO_PATH = store.DATA_DIR / "portfolio.json"
STARTING_CASH_EUR = 10_000.0


# ---------- state ----------

def _empty_state() -> dict:
    return {
        "currency": "EUR",
        "starting_cash": STARTING_CASH_EUR,
        "cash": STARTING_CASH_EUR,
        "created": str(date.today()),
        "positions": {},        # symbol -> {shares, avg_cost_eur, thesis, wrong_price, opened_at}
        "trades": [],
        "equity_history": [],   # [{date, equity}] one per day, for the drawdown meter
    }


def load_state() -> dict:
    if PORTFOLIO_PATH.exists():
        return json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    return _empty_state()


def save_state(state: dict) -> None:
    PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------- market data helpers ----------

def _last_close(symbol: str) -> float:
    prices = store.load_prices(symbol)
    return float(prices.sort_values("date").iloc[-1]["close"])


def _mark_price(symbol: str) -> float:
    """Best available price: delayed live quote via TWS when it's running,
    the vault's last close otherwise. The whole app marks to this — so when
    the market moves, so do your P&L, previews and alerts."""
    from dewaag.broker import get_quotes

    q = get_quotes([symbol]).get(symbol)
    return float(q["price"]) if q else _last_close(symbol)


def _eurusd() -> float:
    """USD per 1 EUR. The double bet (Lesson 2 §6) must be priced, not ignored."""
    try:
        return _last_close("EURUSD")
    except Exception:  # noqa: BLE001 — pre-ingest fallback, roughly right
        return 1.08


def to_eur(amount: float, currency: str) -> float:
    return amount / _eurusd() if currency == "USD" else amount


# ---------- valuation ----------

def snapshot() -> dict:
    """Positions marked to last close (in EUR), risk usage, drawdown state."""
    state = load_state()
    universe = store.load_universe().set_index("symbol")
    c = load_constitution()

    positions = []
    invested = 0.0
    open_risk_eur = 0.0
    for sym, p in state["positions"].items():
        currency = str(universe.loc[sym, "currency"]) if sym in universe.index else "EUR"
        last = _mark_price(sym)
        value_eur = to_eur(last * p["shares"], currency)
        cost_eur = p["avg_cost_eur"] * p["shares"]
        wrong = p.get("wrong_price")
        risk_eur = to_eur(max(0.0, (last - wrong)) * p["shares"], currency) if wrong else 0.0
        open_risk_eur += risk_eur
        invested += value_eur
        positions.append({
            "symbol": sym, "name": str(universe.loc[sym, "name"]) if sym in universe.index else sym,
            "tier": str(universe.loc[sym, "tier"]) if sym in universe.index else "?",
            "currency": currency, "shares": p["shares"],
            "last": last, "value_eur": round(value_eur, 2),
            "pnl_eur": round(value_eur - cost_eur, 2),
            "pnl_pct": round(value_eur / cost_eur - 1, 4) if cost_eur else 0.0,
            "wrong_price": wrong, "thesis": p.get("thesis", ""),
            "opened_at": p.get("opened_at"),
        })

    equity = round(state["cash"] + invested, 2)

    # one equity snapshot per day — the drawdown meter's memory
    today = str(date.today())
    hist = state["equity_history"]
    if not hist or hist[-1]["date"] != today:
        hist.append({"date": today, "equity": equity})
        save_state(state)
    peak = max(h["equity"] for h in hist)

    return {
        "currency": "EUR",
        "cash": round(state["cash"], 2),
        "invested": round(invested, 2),
        "equity": equity,
        "pnl_since_start": round(equity - state["starting_cash"], 2),
        "positions": sorted(positions, key=lambda p: -p["value_eur"]),
        "open_risk_eur": round(open_risk_eur, 2),
        "drawdown_eur": round(max(0.0, peak - equity), 2),
        "drawdown_limit_eur": c.max_drawdown_eur,
        "equity_history": hist[-260:],
        "trades": state["trades"][-50:],
        "constitution_signed": c.signed,
    }


# ---------- the paper broker ----------

def preview(symbol: str, side: str, shares: int) -> dict:
    """Everything the ticket shows before you commit — price, costs, totals."""
    universe = store.load_universe().set_index("symbol")
    if symbol not in universe.index:
        raise ValueError(f"unknown symbol {symbol}")
    tier = str(universe.loc[symbol, "tier"])
    currency = str(universe.loc[symbol, "currency"])
    exchange = str(universe.loc[symbol, "exchange"])
    last = _mark_price(symbol)

    # paper fill model: last close nudged against you by the tier's half-spread
    half = {"mega": 0.0002, "large": 0.0005, "mid": 0.002, "small": 0.006, "etf": 0.0003}.get(tier, 0.004)
    fill = last * (1 + half) if side == "BUY" else last * (1 - half)
    notional_eur = to_eur(fill * shares, currency)
    costs = estimate(tier, notional_eur)
    from dewaag.market_hours import status as market_status
    return {
        "symbol": symbol, "side": side, "tier": tier, "currency": currency,
        "market": market_status(exchange),
        "last": round(last, 4), "fill": round(fill, 4), "shares": shares,
        "notional_eur": round(notional_eur, 2), "costs": costs,
        "total_eur": round(notional_eur + costs["total"], 2) if side == "BUY"
                     else round(notional_eur - costs["total"], 2),
        "fill_model": "paper_local: last close + half-spread (IBKR adapter arrives with account approval)",
    }


def execute(symbol: str, side: str, shares: int, thesis: str = "",
            wrong_price: float | None = None) -> dict:
    """Gate → fill → record. Returns {ok, blocks?, trade?, portfolio}."""
    if shares <= 0:
        return {"ok": False, "blocks": ["shares must be positive"]}
    state = load_state()
    snap = snapshot()
    c = load_constitution()
    pv = preview(symbol, side, shares)

    held = state["positions"].get(symbol, {"shares": 0})
    position_after_eur = (
        to_eur(pv["fill"] * (held["shares"] + shares), pv["currency"]) if side == "BUY" else 0.0
    )
    blocks = gate_order(
        c, portfolio_value=snap["equity"], position_value_after=position_after_eur,
        shares=shares, entry=pv["fill"], wrong_price=wrong_price,
        thesis=thesis, side=side, tier=pv["tier"],
    )
    if side == "BUY" and pv["total_eur"] > state["cash"]:
        blocks.append(f"not enough cash: need €{pv['total_eur']:,.2f}, have €{state['cash']:,.2f}. No leverage — the door stays closed (§5).")
    if side == "SELL" and shares > held["shares"]:
        blocks.append(f"you hold {held['shares']} shares — no short selling in this book.")
    if blocks:
        return {"ok": False, "blocks": blocks}

    # fill — through the configured venue
    from dewaag.broker import gateway_available, load_broker_config, place_limit_order

    broker_cfg = load_broker_config()
    broker_name = "paper_local"
    if broker_cfg["provider"] == "ibkr":
        ib = broker_cfg["ibkr"]
        if not gateway_available(ib["host"], ib["port"]):
            return {"ok": False, "blocks": [
                "IBKR selected but the gateway is offline — start IB Gateway (paper login) and retry. "
                "Silent fallback to the simulator is disabled on purpose: you must always know which venue filled you."]}
        # limit at our previewed fill price (last close nudged by half-spread):
        # honest default that usually crosses; unfilled remainders are cancelled.
        result = place_limit_order(symbol, side, shares, pv["fill"])
        if result["filled"] == 0:
            return {"ok": False, "blocks": [
                f"IBKR paper — not filled. {result.get('note') or result.get('status', '')}"]}
        if result["filled"] < shares:
            shares = result["filled"]  # book exactly what really filled
            pv = preview(symbol, side, shares)
        pv["fill"] = result["avg_price"] or pv["fill"]
        if result.get("commission") is not None:
            pv["costs"]["commission"] = round(float(result["commission"]), 2)
            pv["costs"]["total"] = round(pv["costs"]["commission"] + pv["costs"]["half_spread"] + pv["costs"]["tob"], 2)
        notional = to_eur(pv["fill"] * shares, pv["currency"])
        pv["notional_eur"] = round(notional, 2)
        pv["total_eur"] = round(notional + pv["costs"]["total"], 2) if side == "BUY" else round(notional - pv["costs"]["total"], 2)
        broker_name = "ibkr_paper"

    fill_eur_per_share = to_eur(pv["fill"], pv["currency"])
    if side == "BUY":
        state["cash"] -= pv["total_eur"]
        old = state["positions"].get(symbol)
        if old:
            total_shares = old["shares"] + shares
            old["avg_cost_eur"] = (old["avg_cost_eur"] * old["shares"] + fill_eur_per_share * shares) / total_shares
            old["shares"] = total_shares
            old["wrong_price"] = wrong_price
            old["thesis"] = thesis
        else:
            state["positions"][symbol] = {
                "shares": shares, "avg_cost_eur": fill_eur_per_share,
                "thesis": thesis, "wrong_price": wrong_price,
                "opened_at": str(date.today()),
            }
    else:
        state["cash"] += pv["total_eur"]
        held = state["positions"][symbol]
        held["shares"] -= shares
        if held["shares"] == 0:
            del state["positions"][symbol]

    trade = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbol": symbol, "side": side, "shares": shares,
        "fill": pv["fill"], "currency": pv["currency"],
        "costs_eur": pv["costs"]["total"], "total_eur": pv["total_eur"],
        "thesis": thesis, "wrong_price": wrong_price,
        "broker": broker_name,
    }
    state["trades"].append(trade)
    save_state(state)

    # trades move pipeline cards: BUY -> LIVE, full SELL -> CLOSED (+ post-mortem task)
    from dewaag.pipeline import on_trade
    remaining = state["positions"].get(symbol, {}).get("shares", 0)
    on_trade(symbol, side, remaining)

    return {"ok": True, "trade": trade, "portfolio": snapshot()}
