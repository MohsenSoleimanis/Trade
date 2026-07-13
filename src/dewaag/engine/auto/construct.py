"""L5 — The architect (portfolio construction).

Convictions become target weights by mathematics, not gut. Two ideas most
people get wrong, done right here:

  * SIZE BY RISK, not by money. A calm stock and a wild stock at the same
    euro weight are NOT the same bet. We weight by conviction / volatility
    (inverse-vol), so each holding contributes comparable risk.
  * DEPLOY BY WEATHER. The regime's gross dial decides how much of the book
    is invested vs. held in cash — more cash in a storm, less in clear skies.

Every weight obeys the constitution: no single stock above its cap, and the
whole book never exceeds 100% (leverage is 0, permanently).
"""

from __future__ import annotations

import pandas as pd

MIN_SCORE = 60.0        # only above-median-attractive names are eligible
MIN_CONF = 0.35         # a call the committee barely agrees on is not a call
MAX_NAMES = 15          # concentration is capped by count as well as weight


def _cap_and_normalize(raw: dict[str, float], cap: float, gross: float) -> dict[str, float]:
    """Scale weights to sum to `gross`, then iteratively clip any name over
    `cap` and redistribute — the standard capped-normalization loop."""
    w = dict(raw)
    for _ in range(50):
        tot = sum(w.values())
        if tot <= 0:
            return {}
        w = {k: v / tot * gross for k, v in w.items()}
        over = {k: v for k, v in w.items() if v > cap + 1e-9}
        if not over:
            break
        for k in over:
            w[k] = cap
        room = gross - sum(v for k, v in w.items() if k in over)
        free = {k: v for k, v in w.items() if k not in over}
        ftot = sum(free.values())
        if ftot <= 0 or room <= 0:
            break
        for k in free:
            w[k] = free[k] / ftot * room
    return {k: round(v, 4) for k, v in w.items() if v > 1e-4}


def build_targets(signals_df: pd.DataFrame, blended: dict, regime: dict,
                  max_position_pct: float) -> dict:
    """The ideal target portfolio — capital-independent. Returns target
    WEIGHTS (fractions of the book), not euros: the brain's opinion of the
    right shape, which then scales to any account size at L9."""
    cap = max_position_pct / 100.0
    gross = float(regime.get("gross_target", 0.8))

    vol = signals_df["vol_1y"]
    eligible = []
    for sym, b in blended.items():
        if b["score"] < MIN_SCORE or b["confidence"] < MIN_CONF:
            continue
        v = vol.get(sym)
        if v is None or pd.isna(v) or v <= 0:
            v = 0.30                                  # unknown risk = treat as fairly wild
        # conviction above the bar, divided by risk (inverse-vol sizing),
        # nudged by confidence so shaky calls get less
        edge = (b["score"] - MIN_SCORE) * b["confidence"]
        eligible.append((sym, edge / float(v), b))

    eligible.sort(key=lambda t: -t[1])
    eligible = eligible[:MAX_NAMES]

    raw = {sym: raw_w for sym, raw_w, _ in eligible}
    # you cannot deploy more than (names x cap) without breaking the single-name
    # cap — so the deployable gross is bounded by capacity; the rest stays cash.
    gross = min(gross, len(raw) * cap)
    weights = _cap_and_normalize(raw, cap, gross)

    invested = round(sum(weights.values()), 4)
    picks = []
    for sym, raw_w, b in eligible:
        if sym not in weights:
            continue
        picks.append({"symbol": sym, "weight": weights[sym],
                      "score": b["score"], "confidence": b["confidence"],
                      "fired": b["fired"]})
    picks.sort(key=lambda p: -p["weight"])

    return {"picks": picks,
            "invested": invested,
            "cash": round(1.0 - invested, 4),
            "gross_target": gross,
            "note": ("Weights, not euros — the ideal SHAPE of the book, which scales to any capital. "
                     f"{int(round(1.0-invested)*100) if False else round((1.0-invested)*100)}% is held in cash by the "
                     "regime's storm-dial; a world core-ETF can hold that sleeve instead of idle cash.")}
