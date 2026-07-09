"""The Risk Engine — what Risk Navigator / PORT do, sized for one owner.

Provides, computed from the vault (no inputs required from the human):

  PORTFOLIO RISK   volatility from the covariance of holdings (EUR-based,
                   FX folded in for USD names), 1-month VaR 95/99 both
                   parametric and historical, expected shortfall
  CONTRIBUTION     each position's share of total portfolio risk — the
                   drill-down that shows WHERE the risk actually lives
  EXPOSURE         weights by currency, country, liquidity tier
  STRESS REPLAYS   your CURRENT weights pushed through real history:
                   the 2008 crisis, the COVID crash, the 2022 rate shock,
                   and the worst single month in the data
  WHAT-IF          the OMS question: how does THIS order change all of
                   the above — answered before the order exists

Everything here is estimation from history, and history is a rough guide:
correlations rise in crashes (Lesson 6), so real bad days are usually
worse than the model's bad days. The numbers say so in the payload.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dewaag.vault import store

WEEKS = 156          # ~3y of weekly returns for the covariance
MONTH_FACTOR = np.sqrt(4.33)   # weekly -> monthly scaling
YEAR_FACTOR = np.sqrt(52)

# named windows of real history (start, end, label)
SCENARIOS = [
    ("2008-09-01", "2009-03-09", "2008 financial crisis (worst stretch)"),
    ("2020-02-19", "2020-03-23", "COVID crash (5 weeks)"),
    ("2022-01-03", "2022-10-14", "2022 rate shock"),
]


# ------------------------------------------------------------ data

def _eur_weekly(symbol: str, currency: str, fx: pd.Series | None) -> pd.Series | None:
    """Weekly EUR-denominated adjusted prices — the double bet included."""
    try:
        df = store.load_prices(symbol).sort_values("date")
    except FileNotFoundError:
        return None
    s = pd.Series(df["adj_close"].values, index=pd.to_datetime(df["date"])).dropna()
    if currency == "USD" and fx is not None:
        aligned = fx.reindex(s.index).ffill()
        s = s / aligned            # USD price / (USD per EUR) = EUR price
    return s.resample("W-FRI").last().dropna()


def _fx_series() -> pd.Series | None:
    try:
        df = store.load_prices("EURUSD").sort_values("date")
        return pd.Series(df["adj_close"].values, index=pd.to_datetime(df["date"])).dropna()
    except FileNotFoundError:
        return None


def returns_matrix(symbols: list[str]) -> pd.DataFrame:
    universe = store.load_universe().set_index("symbol")
    fx = _fx_series()
    cols = {}
    for sym in symbols:
        cur = str(universe.loc[sym, "currency"]) if sym in universe.index else "EUR"
        s = _eur_weekly(sym, cur, fx)
        if s is not None and len(s) > 30:
            cols[sym] = s
    if not cols:
        return pd.DataFrame()
    prices = pd.DataFrame(cols).tail(WEEKS + 1)
    return prices.pct_change().dropna(how="all")


# ------------------------------------------------------------ pure math

def portfolio_vol(weights: pd.Series, rets: pd.DataFrame) -> float | None:
    """Annualized portfolio volatility from the covariance matrix."""
    syms = [s for s in weights.index if s in rets.columns]
    if not syms:
        return None
    w = weights[syms].values
    cov = rets[syms].cov().values * 52  # annualized
    return float(np.sqrt(max(0.0, w @ cov @ w)))


def risk_contributions(weights: pd.Series, rets: pd.DataFrame) -> dict[str, float]:
    """Each position's share of portfolio variance (sums to 1). The
    drill-down: where the risk actually lives, which is often NOT where
    the money lives."""
    syms = [s for s in weights.index if s in rets.columns]
    if not syms:
        return {}
    w = weights[syms].values
    cov = rets[syms].cov().values * 52
    port_var = float(w @ cov @ w)
    if port_var <= 0:
        return {}
    marginal = cov @ w
    contrib = w * marginal / port_var
    return {s: round(float(c), 4) for s, c in zip(syms, contrib)}


def var_es(weights: pd.Series, rets: pd.DataFrame, equity: float) -> dict:
    """1-month VaR/ES in euros — parametric AND historical, because when
    they disagree, the disagreement is information (fat tails, Lesson 3
    of the statistics track)."""
    syms = [s for s in weights.index if s in rets.columns]
    if not syms or equity <= 0:
        return {}
    w = weights[syms]
    port_weekly = (rets[syms] * w).sum(axis=1, min_count=1).dropna()
    if len(port_weekly) < 40:
        return {}
    vol_m = float(port_weekly.std()) * MONTH_FACTOR
    # parametric (normal) — the optimistic textbook number
    var95_p = 1.645 * vol_m * equity
    # historical — 4-week overlapping compounded returns, take the tail
    monthly = (1 + port_weekly).rolling(4).apply(np.prod, raw=True).dropna() - 1
    var95_h = float(-np.percentile(monthly, 5)) * equity
    var99_h = float(-np.percentile(monthly, 1)) * equity
    tail = monthly[monthly <= np.percentile(monthly, 5)]
    es95 = float(-tail.mean()) * equity if len(tail) else None
    return {
        "horizon": "1 month",
        "var95_parametric": round(max(0.0, var95_p), 0),
        "var95_hist": round(max(0.0, var95_h), 0),
        "var99_hist": round(max(0.0, var99_h), 0),
        "es95_hist": round(max(0.0, es95), 0) if es95 is not None else None,
    }


def stress_replays(weights: pd.Series, equity: float) -> list[dict]:
    """Push CURRENT weights through real historical windows."""
    universe = store.load_universe().set_index("symbol")
    fx = _fx_series()
    out = []
    series = {}
    for sym in weights.index:
        cur = str(universe.loc[sym, "currency"]) if sym in universe.index else "EUR"
        s = _eur_weekly(sym, cur, fx)
        if s is not None:
            series[sym] = s
    if not series:
        return out
    prices = pd.DataFrame(series)

    for start, end, label in SCENARIOS:
        window = prices.loc[start:end]
        if len(window) < 3:
            continue
        rel = window.iloc[-1] / window.iloc[0] - 1.0
        covered = [s for s in weights.index if s in rel.index and pd.notna(rel[s])]
        if not covered:
            continue
        w_cov = weights[covered]
        port_ret = float((w_cov * rel[covered]).sum())
        out.append({
            "scenario": label,
            "portfolio_return": round(port_ret, 4),
            "loss_eur": round(-port_ret * equity, 0),
            "coverage": round(float(w_cov.sum() / weights.sum()), 2) if weights.sum() else 0,
        })

    # worst single month in the shared history of current holdings
    rets = prices.pct_change().dropna(how="all")
    port_weekly = (rets * weights.reindex(rets.columns).fillna(0)).sum(axis=1, min_count=1).dropna()
    if len(port_weekly) > 40:
        monthly = (1 + port_weekly).rolling(4).apply(np.prod, raw=True).dropna() - 1
        worst = float(monthly.min())
        out.append({
            "scenario": f"worst month in your holdings' own history ({monthly.idxmin().date()})",
            "portfolio_return": round(worst, 4),
            "loss_eur": round(-worst * equity, 0),
            "coverage": 1.0,
        })
    return out


# ------------------------------------------------------------ reports

def _weights_from_positions(positions: list[dict], equity: float) -> pd.Series:
    if not positions or equity <= 0:
        return pd.Series(dtype=float)
    w = pd.Series({p["symbol"]: p["value_eur"] / equity for p in positions})
    return w[w > 0]


def portfolio_report() -> dict:
    from dewaag.portfolio import snapshot

    snap = snapshot()
    weights = _weights_from_positions(snap["positions"], snap["equity"])
    cash_w = snap["cash"] / snap["equity"] if snap["equity"] else 1.0

    if weights.empty:
        return {"empty": True, "equity": snap["equity"],
                "note": "no positions — portfolio risk is cash risk: none short-term, inflation long-term (Lesson 5)."}

    rets = returns_matrix(list(weights.index))
    vol = portfolio_vol(weights, rets)

    universe = store.load_universe().set_index("symbol")
    def bucket(field: str) -> dict:
        agg: dict[str, float] = {}
        for sym, w in weights.items():
            key = str(universe.loc[sym, field]) if sym in universe.index else "?"
            agg[key] = agg.get(key, 0.0) + float(w)
        return {k: round(v, 3) for k, v in sorted(agg.items(), key=lambda x: -x[1])}

    # weighted average of individual vols vs portfolio vol = the free lunch, measured
    indiv = {}
    for sym in weights.index:
        if sym in rets.columns:
            indiv[sym] = float(rets[sym].std() * YEAR_FACTOR)
    wavg_vol = float(sum(weights[s] * v for s, v in indiv.items())) if indiv else None

    return {
        "empty": False,
        "equity": snap["equity"],
        "invested_weight": round(float(weights.sum()), 3),
        "cash_weight": round(cash_w, 3),
        "portfolio_vol": round(vol, 4) if vol else None,
        "weighted_avg_vol": round(wavg_vol, 4) if wavg_vol else None,
        "diversification_gain": round(wavg_vol - vol, 4) if (vol and wavg_vol) else None,
        "var": var_es(weights, rets, snap["equity"]),
        "contributions": risk_contributions(weights, rets),
        "exposure": {"currency": bucket("currency"), "country": bucket("country"), "tier": bucket("tier")},
        "stress": stress_replays(weights, snap["equity"]),
        "caveat": "Estimates from 3y of history. Correlations RISE in crashes (Lesson 6) — expect real bad days to be worse than modeled ones.",
    }


def what_if(symbol: str, side: str, shares: int) -> dict:
    """Risk Navigator's what-if: the full before/after of one order."""
    from dewaag.portfolio import preview, snapshot

    snap = snapshot()
    pv = preview(symbol, side, shares)
    delta = pv["notional_eur"] if side == "BUY" else -pv["notional_eur"]

    positions = {p["symbol"]: p["value_eur"] for p in snap["positions"]}
    before_w = _weights_from_positions(snap["positions"], snap["equity"])

    positions[symbol] = positions.get(symbol, 0.0) + delta
    positions = {s: v for s, v in positions.items() if v > 1}
    after_list = [{"symbol": s, "value_eur": v} for s, v in positions.items()]
    after_w = _weights_from_positions(after_list, snap["equity"])

    syms = sorted(set(before_w.index) | set(after_w.index))
    rets = returns_matrix(syms)

    def block(w: pd.Series) -> dict:
        return {
            "vol": round(portfolio_vol(w, rets) or 0.0, 4),
            "var95_eur": var_es(w, rets, snap["equity"]).get("var95_hist"),
            "top_risk": max(risk_contributions(w, rets).items(), key=lambda x: x[1])[0]
            if len(w) and risk_contributions(w, rets) else None,
        }

    return {"symbol": symbol, "side": side, "shares": shares,
            "before": block(before_w) if len(before_w) else {"vol": 0.0, "var95_eur": 0, "top_risk": None},
            "after": block(after_w) if len(after_w) else {"vol": 0.0, "var95_eur": 0, "top_risk": None}}
