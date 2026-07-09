"""The Backtest Lab engine — honest by construction.

What "honest" means here, mechanically (curriculum M06, the seven sins):

  LOOKAHEAD   the signal at month t uses prices up to t only. The core is a
              pure function over a price panel, so this property has a test:
              changing future prices must not change today's selection.
  COSTS       every weight change pays that symbol's per-side cost (half
              spread + TOB + commission as % of the position). Gross and
              net curves are both returned — the gap IS Lesson 2.
  LEDGER      every run is appended to data/experiments.json. The more
              configurations you try, the less your best result means
              (deflated Sharpe). The ledger makes forgetting impossible.
  SURVIVORSHIP the free universe contains only today's survivors, so
              absolute results are FLATTERED. This warning travels in the
              result payload itself — the UI cannot lose it.

Strategies are deliberately parameter-poor (12-1 momentum, top-N, equal
weight). Fewer knobs = less to overfit. The ML book must one day beat
THIS after the same costs, or it doesn't ship.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from dewaag.engine.costs import HALF_SPREAD, TOB_RATE
from dewaag.vault import store

LEDGER_PATH = store.DATA_DIR / "experiments.json"


# ------------------------------------------------------------ pure core

def side_cost_pct(tier: str, position_eur: float) -> float:
    """Per-side trading cost as a fraction of the position, tier-aware.
    Note the commission term: flat €3 is heavy on small positions —
    small accounts genuinely pay more, and this model says so."""
    kind = "etf" if tier == "etf" else "share"
    commission_pct = 3.0 / max(position_eur, 1.0)
    return HALF_SPREAD.get(tier, 0.004) + TOB_RATE[kind] + commission_pct


def momentum_12_1(panel: pd.DataFrame, i: int) -> pd.Series:
    """12-1 momentum at month index i, using rows <= i only."""
    return panel.iloc[i - 1] / panel.iloc[i - 12] - 1.0


def run(panel: pd.DataFrame, tiers: dict[str, str], *, top_n: int = 8,
        capital: float = 10_000.0, strategy: str = "mom_12_1") -> dict:
    """panel: month-end adjusted closes, columns = symbols, rows = dates
    (ascending). tiers: symbol -> liquidity tier. Returns curves + stats."""
    dates = panel.index
    n = len(dates)
    if n < 15:
        raise ValueError("need at least 15 months of history")

    w_prev: pd.Series = pd.Series(dtype=float)
    gross, net = [1.0], [1.0]
    ew = [1.0]
    turnover_hist, cost_hist = [], []
    curve_dates = [str(dates[13].date())]

    for i in range(13, n - 1):
        rets_next = panel.iloc[i + 1] / panel.iloc[i] - 1.0  # earned i -> i+1

        eligible = panel.iloc[i - 12:i + 1].dropna(axis=1).columns
        eligible = [s for s in eligible if pd.notna(rets_next.get(s))]

        if strategy == "mom_12_1":
            sig = momentum_12_1(panel, i)[eligible].dropna()
            picks = sig.sort_values(ascending=False).head(top_n).index
        elif strategy == "equal_weight":
            picks = pd.Index(eligible)
        else:
            raise ValueError(f"unknown strategy {strategy}")

        if len(picks) == 0:
            gross.append(gross[-1]); net.append(net[-1]); ew.append(ew[-1])
            curve_dates.append(str(dates[i + 1].date()))
            continue

        w_new = pd.Series(1.0 / len(picks), index=picks)

        # drift last month's weights before comparing (you don't pay costs
        # for the market moving your weights — only for trades you place)
        if len(w_prev):
            grown = w_prev * (1.0 + panel.iloc[i][w_prev.index] / panel.iloc[i - 1][w_prev.index] - 1.0).fillna(0.0)
            w_drift = grown / grown.sum() if grown.sum() > 0 else w_prev
        else:
            w_drift = pd.Series(dtype=float)

        all_syms = w_new.index.union(w_drift.index)
        delta = w_new.reindex(all_syms, fill_value=0.0) - w_drift.reindex(all_syms, fill_value=0.0)
        turnover = float(delta.abs().sum()) / 2.0

        cost = 0.0
        for sym, d in delta.items():
            if abs(d) < 1e-12:
                continue
            pos_eur = abs(d) * capital * net[-1]
            cost += abs(d) * side_cost_pct(tiers.get(sym, "mid"), pos_eur)

        r_gross = float((w_new * rets_next[w_new.index]).sum())
        gross.append(gross[-1] * (1.0 + r_gross))
        net.append(net[-1] * (1.0 + r_gross - cost))

        ew_rets = rets_next[eligible].dropna()
        ew.append(ew[-1] * (1.0 + float(ew_rets.mean())) if len(ew_rets) else ew[-1])

        turnover_hist.append(turnover)
        cost_hist.append(cost)
        curve_dates.append(str(dates[i + 1].date()))
        w_prev = w_new

    return {
        "dates": curve_dates,
        "gross": [round(x, 4) for x in gross],
        "net": [round(x, 4) for x in net],
        "equal_weight": [round(x, 4) for x in ew],
        "stats": {
            "strategy": strategy, "top_n": top_n, "capital": capital,
            "months": len(gross) - 1,
            "gross": _stats(gross), "net": _stats(net), "equal_weight": _stats(ew),
            "avg_turnover_1way": round(float(np.mean(turnover_hist)), 3) if turnover_hist else 0.0,
            "total_cost_drag": round(gross[-1] / net[-1] - 1.0, 4) if net[-1] > 0 else None,
        },
        "warnings": [
            "SURVIVORSHIP: universe = today's members only — dead companies are missing, so absolute results are flattered. Relative comparisons (vs equal-weight, vs benchmark) are safer reading.",
            "Free daily data, monthly fills at close — real fills would differ (Lesson 2).",
        ],
    }


def _stats(curve: list[float]) -> dict:
    c = pd.Series(curve)
    rets = c.pct_change().dropna()
    months = len(rets)
    if months == 0 or c.iloc[0] <= 0:
        return {}
    cagr = float(c.iloc[-1] ** (12.0 / months) - 1.0)
    vol = float(rets.std() * np.sqrt(12)) if months > 1 else None
    sharpe = float(rets.mean() / rets.std() * np.sqrt(12)) if months > 1 and rets.std() > 0 else None
    dd = float((c / c.cummax() - 1.0).min())
    return {"cagr": round(cagr, 4), "vol": round(vol, 4) if vol else None,
            "sharpe": round(sharpe, 2) if sharpe else None, "max_dd": round(dd, 4)}


# ------------------------------------------------------- vault wiring

def build_panel(start_year: int = 2006) -> tuple[pd.DataFrame, dict, pd.Series | None]:
    """Month-end adjusted closes for all stocks + tiers + IWDA benchmark."""
    universe = store.load_universe()
    tiers = dict(zip(universe["symbol"], universe["tier"]))
    raw = store.query("SELECT symbol, date, adj_close FROM prices")
    raw["date"] = pd.to_datetime(raw["date"])
    panel = raw.pivot_table(index="date", columns="symbol", values="adj_close")
    monthly = panel.resample("ME").last()
    monthly = monthly[monthly.index >= f"{start_year}-01-01"]

    bench = monthly["IWDA"] if "IWDA" in monthly.columns else None
    stocks = [s for s in monthly.columns
              if tiers.get(s) not in ("etf", "fx")]
    return monthly[stocks], tiers, bench


def run_from_vault(strategy: str = "mom_12_1", top_n: int = 8,
                   start_year: int = 2006, capital: float = 10_000.0) -> dict:
    panel, tiers, bench = build_panel(start_year)
    result = run(panel, tiers, top_n=top_n, capital=capital, strategy=strategy)

    if bench is not None:
        b = bench.reindex(pd.to_datetime(result["dates"])).ffill()
        b = b / b.dropna().iloc[0]
        result["benchmark"] = [None if pd.isna(x) else round(float(x), 4) for x in b]
        bstats = _stats([float(x) for x in b.dropna()])
        result["stats"]["benchmark"] = bstats

    _log_run(result["stats"])
    result["ledger_count"] = ledger_count()
    return result


# ------------------------------------------------------- the ledger

def _log_run(stats: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    ledger = []
    if LEDGER_PATH.exists():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    ledger.append({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "strategy": stats["strategy"], "top_n": stats["top_n"],
        "months": stats["months"],
        "net_cagr": stats["net"].get("cagr"), "net_sharpe": stats["net"].get("sharpe"),
    })
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def ledger_count() -> int:
    if not LEDGER_PATH.exists():
        return 0
    return len(json.loads(LEDGER_PATH.read_text(encoding="utf-8")))


def ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
