"""L3 — The analyst committee (alpha ensemble).

Not one bet: a committee of independent, academically-grounded strategies,
each scoring every stock 0–100 (higher = more attractive by that lens).
They are deliberately diverse, so their mistakes cancel. None of them is
"the answer" — the allocator (L4) decides whose vote counts today.

Each strategy declares the regimes it historically thrives in (favored) and
struggles in (disfavored); the allocator uses those to tilt the weights.

Honesty is wired in: momentum carries a low prior because our own Backtest
Lab refuted hand-rolled monthly momentum net of costs (Lesson 7). It stays
on the committee — as a minority voice, never the chair.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

STOCK_TIERS = ("mega", "large", "mid", "small")


def _pct(col: pd.Series) -> pd.Series:
    """Percentile 0–100 among peers that HAVE the number. Missing stays
    missing — never silently averaged (that is how bias sneaks in)."""
    return col.rank(pct=True) * 100.0


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    edge: str                       # the one-line reason it should work
    prior: float                    # base trust before regime (evidence-set)
    favored: frozenset              # regime tags it thrives in
    disfavored: frozenset
    score: Callable[[pd.DataFrame], pd.Series]  # stocks -> 0..100 Series


def _value(s: pd.DataFrame) -> pd.Series:
    return _pct(s["earnings_yield"])                     # cheap by earnings yield


def _quality(s: pd.DataFrame) -> pd.Series:
    return s["q_score"]                                  # already sector-aware


def _momentum(s: pd.DataFrame) -> pd.Series:
    return _pct(s["mom_12_1"])                           # 12-1, the classic


def _lowvol(s: pd.DataFrame) -> pd.Series:
    return _pct(-s["vol_1y"])                            # the low-volatility anomaly


def _trend(s: pd.DataFrame) -> pd.Series:
    return _pct(s["dist_200d"])                          # distance above the 200d line


def _reversion(s: pd.DataFrame) -> pd.Series:
    return _pct(-s["ret_1m"])                            # buy the recent losers (short-term)


def _growth(s: pd.DataFrame) -> pd.Series:
    g = pd.concat([_pct(s["rev_growth"]), _pct(s["growth_trend"])], axis=1)
    return g.mean(axis=1, skipna=True)                   # growing AND accelerating


def _defensive(s: pd.DataFrame) -> pd.Series:
    return _pct(-s["beta_1y"])                           # low beta to the world


def _neglect(s: pd.DataFrame) -> pd.Series:
    """Book B: small/mid Belgian names the big funds can't fish. A neglect
    tilt, blended with quality so it never rewards small-and-bad."""
    small = s["tier"].isin(["small", "mid"]).astype(float) * 100.0
    be = (s["country"] == "BE").astype(float) * 100.0
    base = pd.concat([small, be, s["q_score"]], axis=1).mean(axis=1, skipna=True)
    return base


STRATEGIES: list[Strategy] = [
    Strategy("quality", "Quality", "Profitable, durable businesses compound and survive drawdowns.",
             1.3, frozenset({"risk_off", "bear", "high_vol"}), frozenset(), _quality),
    Strategy("value", "Value", "Cheap vs earnings tends to beat expensive over the long run.",
             1.3, frozenset({"risk_on", "falling_rates"}), frozenset({"bear"}), _value),
    Strategy("lowvol", "Low volatility", "Calm stocks have historically beaten wild ones per unit of risk.",
             1.1, frozenset({"risk_off", "high_vol", "bear"}), frozenset({"risk_on"}), _lowvol),
    Strategy("trend", "Trend", "Names above their own long average tend to keep trending.",
             1.0, frozenset({"bull", "risk_on"}), frozenset({"bear", "high_vol"}), _trend),
    Strategy("growth", "Quality growth", "Accelerating revenue with quality is what the market pays up for.",
             1.0, frozenset({"risk_on", "falling_rates", "bull"}), frozenset({"rising_rates"}), _growth),
    Strategy("neglect", "Neglect (Book B)", "Under-covered Belgian small caps — water the big funds can't fish.",
             0.9, frozenset({"risk_on", "neutral"}), frozenset({"risk_off"}), _neglect),
    Strategy("defensive", "Defensive (low beta)", "Low-beta names cushion the book when the tide goes out.",
             0.8, frozenset({"risk_off", "bear", "high_vol"}), frozenset({"risk_on"}), _defensive),
    Strategy("momentum", "Momentum", "Recent winners persist — but our Lab refuted it net of costs, so: minority voice.",
             0.7, frozenset({"bull", "risk_on"}), frozenset({"bear", "high_vol"}), _momentum),
    Strategy("reversion", "Short-term reversion", "Sharp recent losers often bounce — a small, high-turnover edge.",
             0.6, frozenset({"high_vol"}), frozenset({"bull"}), _reversion),
]


def committee_scores(signals_df: pd.DataFrame) -> pd.DataFrame:
    """Every strategy's 0–100 vote for every stock. Index = symbol, one
    column per strategy key. ETFs/fx/macro are not stock-picked here."""
    stocks = signals_df[signals_df["tier"].isin(STOCK_TIERS)].copy()
    out = pd.DataFrame(index=stocks.index)
    for strat in STRATEGIES:
        try:
            out[strat.key] = strat.score(stocks).round(1)
        except KeyError:
            out[strat.key] = pd.NA        # a missing feature drops that vote, never fakes it
    return out


def by_key() -> dict[str, Strategy]:
    return {s.key: s for s in STRATEGIES}
