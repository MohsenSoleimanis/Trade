"""Belgian net-proceeds math — "if I sell now, what lands in my pocket?"

Every number a Belgian retail investor actually loses on the way out:
  half-spread (crossing the book) + TOB (beurstaks, both ways but here
  the sell side) + commission + the 2026 capital-gains tax
  ("solidariteitsbijdrage/meerwaardebelasting": 10% on realized gains
  above a €10,000/year exemption — VERIFY current rules yearly, this
  changed in 2026 and details move).

We report a RANGE for the tax: best case (your yearly exemption is still
fully available) and worst case (already used) — because the truth
depends on your other sales this year, which the system can't know yet.
"""

from __future__ import annotations

CGT_RATE = 0.10
CGT_EXEMPTION_EUR = 10_000.0   # annual, per person — verify yearly


def sale_proceeds(*, shares: int, mark_price_native: float, fx_to_eur: float,
                  tier: str, avg_cost_eur: float) -> dict:
    """Full breakdown of a sale at today's mark. All outputs in EUR."""
    from dewaag.engine.costs import COMMISSION_EUR, HALF_SPREAD, TOB_RATE

    gross_native = shares * mark_price_native
    gross_eur = gross_native * fx_to_eur

    spread = HALF_SPREAD.get(tier, 0.004) * gross_eur
    tob = TOB_RATE["etf" if tier == "etf" else "share"] * gross_eur
    commission = COMMISSION_EUR
    net_sale = gross_eur - spread - tob - commission

    basis = avg_cost_eur * shares
    gain = net_sale - basis

    if gain > 0:
        cgt_worst = CGT_RATE * gain                                  # exemption used up
        cgt_best = CGT_RATE * max(0.0, gain - CGT_EXEMPTION_EUR)     # exemption available
    else:
        cgt_worst = cgt_best = 0.0   # losses: no tax (and under the new
        # regime, generally no offsetting either — don't count on losses)

    return {
        "shares": shares,
        "gross_eur": round(gross_eur, 2),
        "costs": {
            "spread": round(spread, 2),
            "tob": round(tob, 2),
            "commission": round(commission, 2),
            "total": round(spread + tob + commission, 2),
        },
        "net_sale_eur": round(net_sale, 2),
        "cost_basis_eur": round(basis, 2),
        "gain_eur": round(gain, 2),
        "cgt": {
            "rate": CGT_RATE,
            "exemption_eur": CGT_EXEMPTION_EUR,
            "best_case": round(cgt_best, 2),
            "worst_case": round(cgt_worst, 2),
        },
        "in_pocket_best": round(net_sale - cgt_best, 2),
        "in_pocket_worst": round(net_sale - cgt_worst, 2),
        "note": ("Capital-gains tax is new since 2026 (10% above a €10k/yr exemption) — "
                 "the range depends on how much exemption you've already used this year. "
                 "Verify current rules; dividends are taxed separately (30% BE withholding, "
                 "15%+30% chain on US payers)."),
    }
