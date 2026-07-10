"""Autopilot — runs the disciplined loop and NARRATES every decision.

You learn by watching it work: each proposed action turns its numbers into
plain-language sentences ("Quality 72/100 means…"), so the dashboard stops
being a wall of digits. Honest frame: a paper-money demonstrator of the
evidence-based process, not a profit engine.

Guarantees:
  * every action passes the SAME constitution gates as a manual order —
    autopilot cannot bypass one risk rule (it calls portfolio.execute)
  * full-auto is paper-only; the broker refuses the live port anyway
  * it holds few names, buys slowly, and arms an exit on everything
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dewaag.constitution import load_constitution
from dewaag.engine.sizing import backwards_size
from dewaag.vault import store

CONFIG_PATH = store.REPO_ROOT / "config" / "autopilot.yaml"


def _exchange_of(symbol: str) -> str:
    u = store.load_universe().set_index("symbol")
    return str(u.loc[symbol, "exchange"]) if symbol in u.index else "NYSE"


def load_config() -> dict:
    cfg = {}
    if CONFIG_PATH.exists():
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    cfg.setdefault("target_holdings", 5)
    cfg.setdefault("max_new_per_cycle", 1)
    cfg.setdefault("exit_pct", 0.20)
    cfg.setdefault("full_auto", False)
    return cfg


# ---------------------------------------------------------- narration helpers

def _rank_word(score: float | None) -> str:
    if score is None:
        return "unrated"
    if score >= 67:
        return "the top third"
    if score >= 34:
        return "the middle"
    return "the bottom third"


def _explain_quality(q: float | None) -> str:
    return (f"Quality {int(q)}/100 — among your ~44 companies, this one's profitability, "
            f"debt and cash conversion rank in {_rank_word(q)} for business quality."
            if q is not None else "Quality — not enough data to rank.")


def _explain_value(v: float | None) -> str:
    if v is None:
        return "Value — no positive earnings to judge, so we stay cautious."
    if v >= 67:
        return f"Value {int(v)}/100 — it's cheaper on earnings than most of the universe; the market expects little, which may be too gloomy."
    if v >= 34:
        return f"Value {int(v)}/100 — priced around the middle of the pack, neither cheap nor expensive."
    return f"Value {int(v)}/100 — pricier than most; you'd be paying up for quality or growth."


def _explain_momentum(m: float | None) -> str:
    if m is None:
        return "Momentum — not enough history yet."
    verb = "rewarding" if m >= 67 else ("ignoring" if m >= 34 else "punishing")
    return f"Momentum {int(m)}/100 — over the past year the market has been {verb} this stock."


# ---------------------------------------------------------- the planner

def generate_plan() -> dict:
    from dewaag.engine.signals import compute_signals
    from dewaag.market_hours import status as market_status
    from dewaag.portfolio import preview, snapshot

    cfg = load_config()
    c = load_constitution()
    snap = snapshot()
    df = compute_signals()
    stocks = df[~df["tier"].isin(["etf", "fx"])].copy()

    held = {p["symbol"] for p in snap["positions"]}
    equity = snap["equity"]

    intro = []
    if not c.signed:
        return {"signed": False, "intro": ["Sign your Risk Constitution first — Autopilot obeys those rules and won't move without them."],
                "sells": [], "buys": [], "settings": cfg, "equity": equity, "held": list(held)}

    # ---- 1. review holdings: any position at/below its written exit? ----
    sells = []
    for p in snap["positions"]:
        if p["wrong_price"] and p["last"] <= p["wrong_price"]:
            sells.append({
                "action": "SELL", "symbol": p["symbol"], "name": p["name"],
                "shares": p["shares"], "entry": p["last"], "wrong_price": p["wrong_price"],
                "reason_code": "exit_hit",
                "thesis": f"exit rule: price {p['last']:.2f} at/below your written wrong-price {p['wrong_price']:.2f}",
                "narration": [
                    f"{p['name']} has fallen to €{p['last']:.2f}, at or below the €{p['wrong_price']:.2f} line you set when you bought it.",
                    "Your own written rule says: at this price the reason to own it is likely broken.",
                    "Selling here is discipline, not panic — it caps the loss exactly where you decided, calmly, in advance.",
                ],
            })

    # ---- 2. new ideas to reach the target holding count ----
    buys = []
    room = min(cfg["max_new_per_cycle"], max(0, cfg["target_holdings"] - len(held)))
    if room > 0:
        # evidence-favored zone: decent quality, not a value trap, positive earnings
        cand = stocks[(stocks["composite"].notna())
                      & (~stocks["symbol"].isin(held))
                      & (stocks["pe"].notna())
                      & ~((stocks["v_score"] > 70) & (stocks["q_score"] < 35))]  # skip trap shape
        # prefer quality-at-a-reasonable-price; among those, prefer names
        # whose market is OPEN now (so the plan is actually actionable today),
        # then overall composite.
        cand = cand.assign(
            qarp=((cand["q_score"] > 55) & (cand["v_score"] > 50)).astype(int),
            tradeable=cand["symbol"].map(
                lambda s: 1 if market_status(_exchange_of(s)).get("open") else 0),
        )
        cand = cand.sort_values(["qarp", "tradeable", "composite"], ascending=[False, False, False])

        budget = equity * c.max_risk_per_idea_pct / 100.0
        for _, r in cand.head(room).iterrows():
            entry = float(r["price"])
            vol = float(r["vol_1y"]) if r["vol_1y"] is not None else 0.25
            exit_pct = cfg["exit_pct"] + (0.05 if vol > 0.35 else 0.0)  # wider stop for wild names
            wrong = round(entry * (1 - exit_pct), 2)
            size = backwards_size(equity, c.max_risk_per_idea_pct, entry, wrong)
            if not size["ok"] or size["shares"] < 1:
                continue
            shares = size["shares"]
            # respect the position cap too
            cap_shares = int((equity * c.max_position_pct / 100.0) // entry)
            shares = min(shares, cap_shares)
            if shares < 1:
                continue
            cur = r["currency"]
            pv = preview(r["symbol"], "BUY", shares)
            mkt = market_status(_exchange_of(r["symbol"]))
            reason = "quality at a reasonable price" if r.get("qarp") else "best overall on the evidence"
            sign = "$" if cur == "USD" else "€"
            mkt_line = (f"Its market is {mkt['label']} — you can place this now."
                        if mkt["open"] else
                        f"Heads up: its market is {mkt['label']}, so this only fills once it opens. "
                        f"A limit order placed now would just cancel — better to wait, or pick a name whose market is open.")
            buys.append({
                "action": "BUY", "symbol": r["symbol"], "name": r["name"],
                "sector": r.get("sector", ""), "currency": cur,
                "shares": shares, "entry": entry, "wrong_price": wrong,
                "market": mkt,
                "risk_eur": round(shares * (entry - wrong) * (1 / (pv["notional_eur"] / (entry * shares)) if pv["notional_eur"] else 1), 0),
                "cost_eur": pv["costs"]["total"], "position_eur": pv["notional_eur"],
                "scores": {k: (None if r[k] is None or (isinstance(r[k], float) and r[k] != r[k]) else int(r[k]))
                           for k in ("q_score", "v_score", "m_score", "composite")},
                "reason_code": "qarp" if r.get("qarp") else "composite",
                "thesis": f"{reason}; quality {r['q_score']}, value {r['v_score']}, composite {r['composite']} — sized by the 1% rule with a {int(exit_pct*100)}% exit.",
                "narration": [
                    f"I'm looking at {r['name']} ({r['symbol']}), a {r.get('sector','')} company — picked because it's {reason}.",
                    _explain_quality(r["q_score"]),
                    _explain_value(r["v_score"]),
                    _explain_momentum(r["m_score"]),
                    f"Your rule risks at most 1% of your €{equity:,.0f} — that's €{budget:,.0f} on this idea.",
                    f"I'd buy at about {sign}{entry:,.2f} and set the exit at {sign}{wrong:,.2f} ({int(exit_pct*100)}% below) — wide enough to survive normal noise, so I only sell if the reason is truly broken.",
                    f"Each share can lose {sign}{entry-wrong:,.2f}, so the 1% budget buys {shares} shares — about {sign}{entry*shares:,.0f} invested.",
                    f"Trading costs ≈ €{pv['costs']['total']:.0f} (spread + Belgian TOB tax + commission) — I use a limit order so we never overpay.",
                    mkt_line,
                    f"This keeps you diversified toward {cfg['target_holdings']} small positions — spreading bets is your only free protection.",
                ],
            })
        if not buys and room > 0:
            intro.append("No new buy today — nothing cleared the evidence filter (quality, not a value-trap, positive earnings). Doing nothing is a valid move.")

    if not sells and not buys and not intro:
        intro.append("Everything is within your rules today — no action needed. A calm day is the system working, not failing.")
    intro.insert(0, f"Portfolio €{equity:,.0f} · {len(held)} of {cfg['target_holdings']} target positions · reviewing exits, then looking for one careful new idea.")

    return {"signed": True, "intro": intro, "sells": sells, "buys": buys,
            "settings": cfg, "equity": equity, "held": list(held)}


def execute_action(action: dict) -> dict:
    """Run ONE approved action through the gated executor (all rules apply)."""
    from dewaag.portfolio import execute

    return execute(action["symbol"], action["action"], int(action["shares"]),
                   thesis="[autopilot] " + action.get("thesis", ""),
                   wrong_price=action.get("wrong_price"))


def run_auto() -> dict:
    """Full-auto: execute every proposed action. PAPER ONLY — the broker
    refuses the live port, and we refuse full-auto unless config says so."""
    cfg = load_config()
    if not cfg["full_auto"]:
        return {"ran": False, "reason": "full_auto is off — approve actions one by one (safer while you learn)"}
    plan = generate_plan()
    if not plan["signed"]:
        return {"ran": False, "reason": "constitution unsigned"}
    results = []
    for act in plan["sells"] + plan["buys"]:
        results.append({"symbol": act["symbol"], "side": act["action"],
                        "result": execute_action(act)})
    return {"ran": True, "results": results}
