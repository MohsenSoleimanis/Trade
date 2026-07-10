"""Backwards position sizing + the constitution gates (Lesson 6, as law).

`gate_order` returns a verdict object, never raises: the Trading Desk
shows WHY something is blocked — every gate is a micro-lesson, and a
silent block teaches nothing.
"""

from __future__ import annotations

from dewaag.constitution import Constitution


def backwards_size(portfolio_value: float, risk_pct: float,
                   entry: float, wrong_price: float) -> dict:
    """Risk budget ÷ loss-per-share = shares. Conviction is not a parameter."""
    risk_budget = portfolio_value * risk_pct / 100.0
    loss_per_share = entry - wrong_price
    if loss_per_share <= 0:
        return {"ok": False, "reason": "your 'I am wrong' price must be BELOW the entry — it is the level where your thesis is dead (Lesson 6 §3)"}
    shares = int(risk_budget // loss_per_share)
    return {
        "ok": True,
        "risk_budget": round(risk_budget, 2),
        "loss_per_share": round(loss_per_share, 2),
        "shares": shares,
        "investment": round(shares * entry, 2),
        "worst_case_loss": round(shares * loss_per_share, 2),
    }


def gate_order(c: Constitution, *, portfolio_value: float, position_value_after: float,
               shares: int, entry: float, wrong_price: float | None,
               thesis: str, side: str, tier: str = "mid") -> list[str]:
    """Every reason this order may not pass. Empty list = cleared."""
    blocks: list[str] = []

    if not c.signed:
        blocks.append("constitution UNSIGNED — fill max_drawdown_eur and signed_on in config/risk-constitution.yaml. The desk stays locked until calm-you has signed the rules (Lesson 6 §6).")
        return blocks  # nothing else matters until signed

    if side == "SELL":
        return blocks  # closing/reducing risk is never blocked

    if c.require_thesis and len(thesis.strip()) < 20:
        blocks.append("thesis required — one honest sentence: why this, why now, and what would prove you wrong (constitution §6).")

    if wrong_price is None or wrong_price <= 0:
        blocks.append("'I am wrong if it falls to ___' price required — sizing is computed backwards from it (Lesson 6 §3).")
    elif wrong_price >= entry:
        blocks.append("the 'wrong' price must be below entry.")
    else:
        worst_loss = shares * (entry - wrong_price)
        budget = portfolio_value * c.max_risk_per_idea_pct / 100.0
        if worst_loss > budget * 1.005:  # tiny tolerance for rounding
            blocks.append(
                f"risk €{worst_loss:,.0f} exceeds your {c.max_risk_per_idea_pct}% budget "
                f"(€{budget:,.0f}). Reduce shares or rethink the exit — conviction never enters the formula (§1)."
            )

    # §2 caps SINGLE-COMPANY risk. A broad ETF is a basket of ~1,500
    # companies — it IS the diversification the cap exists to protect.
    # Core ETFs get a wider ceiling (60%) instead of the stock cap.
    cap_pct = 60.0 if tier == "etf" else c.max_position_pct
    cap = portfolio_value * cap_pct / 100.0
    if position_value_after > cap * 1.005:
        blocks.append(
            f"position would be €{position_value_after:,.0f} — above the {cap_pct:.0f}% cap "
            f"(€{cap:,.0f}). Feeling sure is data about you, not the stock (§2)."
        )

    return blocks
