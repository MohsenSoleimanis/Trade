"""Lesson 4 as code: EPS, P/E, the decoder, and the value machine.

The shortcut formula everywhere:  value = profit / (rate - growth),
so  fair P/E = 1 / (rate - growth)  and  implied growth = rate - 1/PE.
All outputs are ranges-with-assumptions, never points — the UI must
show the assumptions next to every number (precision illusion trap).
"""

from __future__ import annotations

DEFAULT_RATE = 0.08  # the demanded return used across the app; the UI's
                     # sliders let the user disagree — that's the point.


def snapshot(price: float | None, net_income: float | None,
             shares: float | None, rate: float = DEFAULT_RATE) -> dict:
    """Everything the Company page's valuation panel needs."""
    eps = None
    if net_income is not None and shares:
        eps = net_income / shares

    pe = None
    if eps and eps > 0 and price:
        pe = price / eps

    implied_growth = None
    if pe and pe > 0:
        # decode the promise inside the price (Lesson 4 §3)
        implied_growth = rate - 1.0 / pe

    market_cap = price * shares if (price and shares) else None

    return {
        "price": price,
        "eps": eps,
        "pe": pe,
        "rate": rate,
        "implied_growth": implied_growth,
        "market_cap": market_cap,
    }


def fair_value_per_share(eps: float, rate: float, growth: float) -> float | None:
    """The value machine. Returns None when assumptions break the formula
    (growth too close to rate) — the UI shows a warning, never a number,
    because 'infinity' is not a price target, it's a wrong assumption."""
    gap = rate - growth
    if gap < 0.005 or eps is None or eps <= 0:
        return None
    return eps * (1.0 + growth) / gap
