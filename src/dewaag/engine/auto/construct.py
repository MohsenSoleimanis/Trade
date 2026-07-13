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

# broad world baskets — the CORE. Held as the diversified foundation, not
# picked by the committee (a whole-world index has no single-name alpha).
# Preference order = lowest share price first (buyable in a small account).
WORLD_CORE = ("WEBN", "VWCE", "IWDA")
# how much of the deployed book is the safe core vs. the alpha satellites.
# more core when the weather is bad; costs and small size make a big core
# the honest default for a small account (own the market, tilt at the edges).
CORE_FRACTION = {"risk_on": 0.60, "neutral": 0.72, "risk_off": 0.85}


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
    """The ideal target portfolio as a CORE-SATELLITE book (weights, not euros):

      CORE      — a broad world basket, the diversified foundation. Sized by
                  the regime; exempt from the single-name cap because it IS
                  the diversification the cap protects.
      SATELLITES— the committee's top convictions (stocks + tactical baskets),
                  each capped, sized by conviction / risk.

    This is how a small account actually grows real money: own the market
    cheaply, then tilt at the edges — not bet the book on a few stocks."""
    cap = max_position_pct / 100.0
    gross = float(regime.get("gross_target", 0.8))
    risk = regime.get("risk", "neutral")

    # ---- the core: the cheapest-share world basket that we actually hold ----
    core_sym = next((s for s in WORLD_CORE if s in signals_df.index), None)
    core_frac = CORE_FRACTION.get(risk, 0.72) if core_sym else 0.0
    core_weight = round(gross * core_frac, 4)
    sat_gross = gross - core_weight

    # ---- satellites: top convictions, excluding the world-core baskets ----
    vol = signals_df["vol_1y"]
    eligible = []
    for sym, b in blended.items():
        if sym in WORLD_CORE:
            continue                                  # never double the core
        if b["score"] < MIN_SCORE or b["confidence"] < MIN_CONF:
            continue
        v = vol.get(sym)
        if v is None or pd.isna(v) or v <= 0:
            v = 0.30
        edge = (b["score"] - MIN_SCORE) * b["confidence"]
        eligible.append((sym, edge / float(v), b))

    eligible.sort(key=lambda t: -t[1])
    eligible = eligible[:MAX_NAMES]
    raw = {sym: raw_w for sym, raw_w, _ in eligible}
    sat_gross = min(sat_gross, len(raw) * cap)        # capacity-bounded
    sat_weights = _cap_and_normalize(raw, cap, sat_gross) if raw else {}

    picks = []
    if core_sym and core_weight > 0:
        picks.append({"symbol": core_sym, "weight": core_weight, "score": 100.0,
                      "confidence": 1.0, "fired": ["world core"], "is_core": True})
    for sym, _, b in eligible:
        if sym in sat_weights:
            picks.append({"symbol": sym, "weight": sat_weights[sym], "score": b["score"],
                          "confidence": b["confidence"], "fired": b["fired"], "is_core": False})
    picks.sort(key=lambda p: (-p.get("is_core", False), -p["weight"]))

    invested = round(sum(p["weight"] for p in picks), 4)
    return {"picks": picks,
            "invested": invested,
            "cash": round(1.0 - invested, 4),
            "gross_target": gross,
            "core_symbol": core_sym,
            "core_weight": core_weight,
            "note": (f"Core-satellite: ~{round(core_weight*100)}% in a broad world basket ({core_sym or 'n/a'}) as the "
                     f"foundation, ~{round((invested-core_weight)*100)}% across capped satellite convictions, "
                     f"{round((1.0-invested)*100)}% cash by the regime's storm-dial.")}
