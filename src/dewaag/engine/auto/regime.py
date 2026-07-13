"""L2 — The weather brain.

Before deciding anything, classify the environment. Every strategy in the
committee (L3) is told which weather it is operating in, and the allocator
(L4) re-weights them for it. A system blind to regime eventually walks into
the storm.

Everything here is measured from prices we already trust — the benchmark
and the macro channels (VIX, rates, oil). No forecasting: a regime is a
description of NOW, not a prediction of next.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dewaag.vault import store

TRADING_DAYS = 252


def _series(symbol: str) -> pd.Series | None:
    try:
        df = store.load_prices(symbol).sort_values("date")
    except FileNotFoundError:
        return None
    return pd.Series(df["adj_close"].values, index=pd.to_datetime(df["date"])).dropna()


def _last(symbol: str) -> float | None:
    s = _series(symbol)
    return float(s.iloc[-1]) if s is not None and len(s) else None


def classify(signals_df: pd.DataFrame | None = None) -> dict:
    """Return the current regime as a set of plain tags + human drivers.

    tags drive the allocator; drivers explain it to the human. `signals_df`
    is injectable so tests can drive breadth without the whole vault.
    """
    world = _series("IWDA")
    tags: set[str] = set()
    drivers: list[str] = []

    # --- trend: is the world above its own 200-day line? ---
    trend = None
    if world is not None and len(world) >= 200:
        ma200 = float(world.iloc[-200:].mean())
        trend = "up" if float(world.iloc[-1]) > ma200 else "down"
        tags.add("bull" if trend == "up" else "bear")
        drivers.append(f"World equities are {'above' if trend == 'up' else 'below'} their 200-day average — a {'rising' if trend == 'up' else 'falling'} tide.")

    # --- realized volatility of the world (annualized, last quarter) ---
    world_vol = None
    if world is not None and len(world) > 80:
        r = world.iloc[-63:].pct_change().dropna()
        world_vol = float(r.std() * np.sqrt(TRADING_DAYS))

    # --- market fear: the VIX level ---
    vix = _last("VIX")
    vol_state = None
    if vix is not None:
        vol_state = ("calm" if vix < 15 else "normal" if vix < 20
                     else "nervous" if vix < 30 else "stressed")
        tags.add("low_vol" if vix < 20 else "high_vol")
        drivers.append(f"VIX {vix:.0f} — the market is {vol_state}.")

    # --- rates: direction of the US 10y over 3 months ---
    rates = None
    us10 = _series("US10Y")
    if us10 is not None and len(us10) > 70:
        chg = float(us10.iloc[-1] - us10.iloc[-63])
        rates = "rising" if chg > 0.15 else "falling" if chg < -0.15 else "flat"
        if rates != "flat":
            tags.add("rising_rates" if rates == "rising" else "falling_rates")
        drivers.append(f"US 10-year yield is {rates} ({chg:+.2f} pts in 3 months) — {'a headwind for expensive, long-duration names' if rates == 'rising' else 'relief for growth valuations' if rates == 'falling' else 'steady'}.")

    # --- breadth: what share of stocks are above their own 200-day line? ---
    breadth = None
    if signals_df is not None and "above_200d" in signals_df.columns:
        stocks = signals_df[signals_df["tier"].isin(["mega", "large", "mid", "small"])]
        vals = stocks["above_200d"].dropna()
        if len(vals):
            breadth = float(vals.mean())
            drivers.append(f"{breadth*100:.0f}% of the universe is in its own uptrend — {'broad participation' if breadth > 0.6 else 'narrow, fragile leadership' if breadth < 0.4 else 'mixed'}.")

    # --- the single verdict: risk-on or risk-off ---
    score = 0.0
    if trend == "up":
        score += 1
    elif trend == "down":
        score -= 1
    if vix is not None:
        score += 1 if vix < 18 else -1 if vix > 26 else 0
    if breadth is not None:
        score += 1 if breadth > 0.6 else -1 if breadth < 0.4 else 0
    if rates == "falling":
        score += 0.5
    elif rates == "rising":
        score -= 0.25

    if score >= 1.5:
        risk, label = "risk_on", "Risk-on — clear skies"
    elif score <= -1.5:
        risk, label = "risk_off", "Risk-off — storm"
    else:
        risk, label = "neutral", "Mixed — choppy"
    tags.add(risk)

    # gross-exposure dial: how much of the book the weather says to deploy
    gross = {"risk_on": 0.95, "neutral": 0.80, "risk_off": 0.55}[risk]

    return {
        "label": label,
        "risk": risk,
        "trend": trend,
        "vol_state": vol_state,
        "world_vol": None if world_vol is None else round(world_vol, 3),
        "vix": vix,
        "rates": rates,
        "breadth": None if breadth is None else round(breadth, 3),
        "tags": sorted(tags),
        "gross_target": gross,
        "drivers": drivers,
        "note": "A regime describes the market now — it is not a forecast. It only decides which strategies get more weight and how much of the book to deploy.",
    }
