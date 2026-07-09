"""The cost model — every trade preview shows these BEFORE commitment.

Lesson 2: spread, TOB and commission are invisible on every other
platform; here they are first-class citizens of the order ticket.
Numbers are honest estimates for a small Belgian retail order.
"""

from __future__ import annotations

COMMISSION_EUR = 3.0  # flat, IBKR-tier-like

# Belgian stock-exchange tax per side (verify current rates yearly)
TOB_RATE = {"share": 0.0035, "etf": 0.0012}

# typical half-spread you pay crossing the book, by liquidity tier (L2)
HALF_SPREAD = {"mega": 0.0002, "large": 0.0005, "mid": 0.0020,
               "small": 0.0060, "etf": 0.0003}


def estimate(tier: str, notional: float) -> dict:
    """Cost of ONE side (a buy or a sell) of `notional` EUR."""
    kind = "etf" if tier == "etf" else "share"
    half_spread = HALF_SPREAD.get(tier, 0.004) * notional
    tob = TOB_RATE[kind] * notional
    total = COMMISSION_EUR + half_spread + tob
    return {
        "commission": round(COMMISSION_EUR, 2),
        "half_spread": round(half_spread, 2),
        "tob": round(tob, 2),
        "total": round(total, 2),
        "total_pct": round(total / notional, 6) if notional else 0.0,
    }
