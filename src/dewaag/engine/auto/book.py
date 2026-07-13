"""The engine's OWN autonomous book — cut loose from the personal account.

This is the correction to a real mistake: the engine was chained to your
personal €100 paper book and its unsigned-constitution wall, so it could
never actually act — it just said "blocked". That made a new brain feel
like the old app.

Here the engine is its own trader. Its own simulated capital, its own
pre-signed charter (sensible, fixed), its own ledger and track record. It
proposes; you approve; it fills into THIS book and the equity curve grows.
Nothing here touches your personal portfolio — the two are separate on
purpose. When you trust the engine's record, you mirror its moves by hand.

Simulated capital is deliberately scale-free (default €100k) so the full
diversified book can exist and costs/caps are realistic — it is NOT your
money and is labeled as such everywhere.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from dewaag.vault import store

ENGINE_BOOK_PATH = store.DATA_DIR / "auto" / "engine_book.json"
STARTING_CAPITAL = 1_000.0     # a real small-account size, not a placeholder

HALF_SPREAD = {"mega": 0.0002, "large": 0.0005, "mid": 0.002,
               "small": 0.006, "etf": 0.0003}


def engine_constitution():
    """The engine's charter — pre-signed and fixed. Same laws as the
    personal one (1% risk/idea, 10% position cap, zero leverage), so the
    veto (L6) is real; only it isn't waiting on a human signature."""
    from dewaag.constitution import Constitution
    return Constitution(
        owner="De Waag Engine", signed_on="2026-01-01",
        max_risk_per_idea_pct=1.0, max_position_pct=10.0,
        max_drawdown_eur=round(STARTING_CAPITAL * 0.20, 2),
        emergency_fund_months=6, leverage=0, require_thesis=True,
        min_years_before_strategy_change=1,
        strategy_statement="Systematic ten-layer ensemble; approve-per-trade.")


# ---------- state ----------

def _empty() -> dict:
    return {"currency": "EUR", "simulated": True,
            "starting_cash": STARTING_CAPITAL, "cash": STARTING_CAPITAL,
            "created": str(date.today()), "positions": {}, "trades": [],
            "equity_history": []}


def load() -> dict:
    if ENGINE_BOOK_PATH.exists():
        return json.loads(ENGINE_BOOK_PATH.read_text(encoding="utf-8"))
    return _empty()


def save(state: dict) -> None:
    ENGINE_BOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENGINE_BOOK_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------- marking ----------

def _last_close(symbol: str) -> float | None:
    try:
        df = store.load_prices(symbol).sort_values("date")
        return float(df.iloc[-1]["close"])
    except Exception:  # noqa: BLE001
        return None


def snapshot() -> dict:
    from dewaag.portfolio import to_eur

    state = load()
    uni = store.load_universe().set_index("symbol")
    positions, invested, open_risk = [], 0.0, 0.0
    for sym, p in state["positions"].items():
        currency = str(uni.loc[sym, "currency"]) if sym in uni.index else "EUR"
        last = _last_close(sym) or p["avg_cost_native"]
        value_eur = to_eur(last * p["shares"], currency)
        cost_eur = p["avg_cost_eur"] * p["shares"]
        wrong = p.get("wrong_price")
        if wrong:
            open_risk += to_eur(max(0.0, last - wrong) * p["shares"], currency)
        invested += value_eur
        positions.append({
            "symbol": sym, "name": str(uni.loc[sym, "name"]) if sym in uni.index else sym,
            "tier": str(uni.loc[sym, "tier"]) if sym in uni.index else "?",
            "currency": currency, "shares": p["shares"], "last": round(last, 4),
            "value_eur": round(value_eur, 2), "cost_eur": round(cost_eur, 2),
            "pnl_eur": round(value_eur - cost_eur, 2),
            "pnl_pct": round(value_eur / cost_eur - 1, 4) if cost_eur else 0.0,
            "wrong_price": wrong, "opened_at": p.get("opened_at"),
        })
    equity = round(state["cash"] + invested, 2)

    today = str(date.today())
    hist = state["equity_history"]
    if not hist or hist[-1]["date"] != today:
        hist.append({"date": today, "equity": equity})
        save(state)
    peak = max((h["equity"] for h in hist), default=equity)

    return {
        "simulated": True,
        "equity": equity, "cash": round(state["cash"], 2), "invested": round(invested, 2),
        "starting": state["starting_cash"],
        "pnl_eur": round(equity - state["starting_cash"], 2),
        "pnl_pct": round(equity / state["starting_cash"] - 1, 4),
        "positions": sorted(positions, key=lambda p: -p["value_eur"]),
        "open_risk_eur": round(open_risk, 2),
        "drawdown_eur": round(max(0.0, peak - equity), 2),
        "equity_history": hist[-260:],
        "trades": state["trades"][-30:],
        "constitution_signed": True,      # the engine's charter is always signed
    }


# ---------- execution (approve routes here) ----------

def execute_proposal(p: dict) -> dict:
    """Fill an approved proposal into the engine's own book. Re-gates against
    the engine charter first — approve can never bypass the veto."""
    from dewaag.engine.costs import estimate
    from dewaag.engine.sizing import gate_order
    from dewaag.portfolio import to_eur

    state = load()
    snap = snapshot()
    c = engine_constitution()
    sym, side, shares = p["symbol"], p["side"], int(p["shares"])
    tier, currency = p.get("tier", "mid"), p.get("currency", "EUR")
    last = _last_close(sym) or p.get("price")
    if not last or shares <= 0:
        return {"ok": False, "blocks": ["no price / bad size"]}

    half = HALF_SPREAD.get(tier, 0.004)
    fill = last * (1 + half) if side == "BUY" else last * (1 - half)
    notional_eur = to_eur(fill * shares, currency)
    costs = estimate(tier, notional_eur)
    total_eur = notional_eur + costs["total"] if side == "BUY" else notional_eur - costs["total"]

    held = state["positions"].get(sym, {"shares": 0})
    pos_after = to_eur(fill * (held["shares"] + shares), currency) if side == "BUY" else 0.0
    blocks = gate_order(c, portfolio_value=snap["equity"], position_value_after=pos_after,
                        shares=shares, entry=fill, wrong_price=p.get("wrong_price"),
                        thesis=p.get("rationale", ""), side=side, tier=tier)
    if side == "BUY" and total_eur > state["cash"]:
        blocks.append(f"engine book has €{state['cash']:,.0f}, needs €{total_eur:,.0f} — no leverage.")
    if side == "SELL" and shares > held.get("shares", 0):
        blocks.append("engine book holds fewer shares than the exit asks.")
    if blocks:
        return {"ok": False, "blocks": blocks}

    fill_eur = to_eur(fill, currency)
    if side == "BUY":
        state["cash"] -= total_eur
        old = state["positions"].get(sym)
        if old:
            tot = old["shares"] + shares
            old["avg_cost_eur"] = (old["avg_cost_eur"] * old["shares"] + fill_eur * shares) / tot
            old["avg_cost_native"] = (old["avg_cost_native"] * old["shares"] + fill * shares) / tot
            old["shares"] = tot
            old["wrong_price"] = p.get("wrong_price")
        else:
            state["positions"][sym] = {"shares": shares, "avg_cost_eur": fill_eur,
                                       "avg_cost_native": fill, "wrong_price": p.get("wrong_price"),
                                       "opened_at": str(date.today())}
    else:
        state["cash"] += total_eur
        held = state["positions"][sym]
        held["shares"] -= shares
        if held["shares"] <= 0:
            del state["positions"][sym]

    trade = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "symbol": sym, "side": side, "shares": shares, "fill": round(fill, 4),
             "currency": currency, "costs_eur": costs["total"], "total_eur": round(total_eur, 2),
             "rationale": p.get("rationale", "")}
    state["trades"].append(trade)
    save(state)
    return {"ok": True, "trade": trade, "book": snapshot()}
