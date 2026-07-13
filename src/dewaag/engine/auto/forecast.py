"""Forecasting — the honest kind.

You cannot predict direction (Lesson 1). You CAN forecast RISK: volatility
clusters, so recent volatility predicts near-term volatility well. This turns
that into an expected RANGE — where a name (or the whole book) will most
likely trade over a horizon — centered on today's price, with NO direction
guess baked in (that would be the dishonest part).

Method: EWMA variance (RiskMetrics, λ=0.94) on daily returns — it weights
recent days more, so it tracks the current risk regime, not a stale average.
Range over h days = today's price × (1 ± k·σ_daily·√h).
  ±1σ  ≈ a normal month     (~2 in 3 chance the price stays inside)
  ±2σ  ≈ a rough month       (~19 in 20 chance inside)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dewaag.vault import store

LAMBDA = 0.94          # RiskMetrics daily EWMA decay
TRADING_DAYS = 252
DEFAULT_HORIZON = 21   # ~one trading month


def _returns(symbol: str) -> tuple[pd.Series, float]:
    df = store.load_prices(symbol).sort_values("date")
    s = pd.Series(df["adj_close"].values, index=pd.to_datetime(df["date"])).astype(float)
    return s.pct_change().dropna(), float(df.iloc[-1]["close"])


def _ewma_vol_daily(returns: pd.Series) -> float | None:
    if len(returns) < 30:
        return float(returns.std()) if len(returns) else None
    var = (returns ** 2).ewm(alpha=1 - LAMBDA).mean().iloc[-1]
    return float(np.sqrt(var))


def expected_range(symbol: str, horizon_days: int = DEFAULT_HORIZON) -> dict:
    """The likely trading range for one instrument over the horizon."""
    try:
        r, last = _returns(symbol)
    except FileNotFoundError:
        return {"available": False}
    vd = _ewma_vol_daily(r)
    if not vd or last <= 0:
        return {"available": False}
    sig_h = vd * float(np.sqrt(horizon_days))

    def band(k: float) -> dict:
        return {"low": round(last * (1 - k * sig_h), 2), "high": round(last * (1 + k * sig_h), 2),
                "pct": round(k * sig_h, 4)}

    return {
        "available": True, "symbol": symbol, "last": round(last, 2),
        "horizon_days": horizon_days,
        "vol_daily": round(vd, 4), "vol_annual": round(vd * float(np.sqrt(TRADING_DAYS)), 4),
        "one_sigma": band(1.0), "two_sigma": band(2.0),
        "note": ("A forecast of the RANGE (risk), not the direction — centered on today's price. "
                 "~2-in-3 chance the price stays inside the ±1σ band over the month, ~19-in-20 inside ±2σ."),
    }


def book_forecast(horizon_days: int = DEFAULT_HORIZON) -> dict:
    """The engine book's likely value range next month — diversification-aware,
    because it's built from the ACTUAL weighted return history of the holdings,
    not a naive sum of individual risks. Cash carries no risk."""
    from dewaag.engine.auto.book import snapshot

    snap = snapshot()
    eq = float(snap["equity"])
    if not snap["positions"] or eq <= 0:
        return {"available": False, "note": "No positions yet — the book is all cash, which carries no market risk."}

    series, weights = {}, {}
    for p in snap["positions"]:
        try:
            r, _ = _returns(p["symbol"])
        except FileNotFoundError:
            continue
        series[p["symbol"]] = r
        weights[p["symbol"]] = p["value_eur"] / eq        # cash weight (the rest) contributes 0 risk
    if not series:
        return {"available": False}

    df = pd.DataFrame(series).dropna()
    if len(df) < 30:
        return {"available": False}
    port = pd.Series(0.0, index=df.index)
    for s in df.columns:
        port = port + df[s] * weights[s]
    vd = _ewma_vol_daily(port)
    if not vd:
        return {"available": False}
    sig_h = vd * float(np.sqrt(horizon_days))

    return {
        "available": True, "equity": round(eq, 2), "horizon_days": horizon_days,
        "vol_daily": round(vd, 4), "vol_annual": round(vd * float(np.sqrt(TRADING_DAYS)), 4),
        "one_sigma_pct": round(sig_h, 4),
        "one_sigma": {"low": round(eq * (1 - sig_h), 2), "high": round(eq * (1 + sig_h), 2)},
        "two_sigma": {"low": round(eq * (1 - 2 * sig_h), 2), "high": round(eq * (1 + 2 * sig_h), 2)},
        "invested_weight": round(sum(weights.values()), 3),
        "note": ("Your book's likely value range next month — risk, not a prediction of up or down. "
                 "A large cash slice narrows it; a concentrated stock book widens it."),
    }
