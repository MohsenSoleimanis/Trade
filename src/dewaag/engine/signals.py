"""The Signal Engine — the part that reads the whole universe itself.

For every company, computed cross-sectionally (against all others):

  MOMENTUM  12-1 month return, 6m/3m returns, distance from 200-day average
  QUALITY   ROE level & stability, margin trend, debt, cash conversion
  VALUE     earnings yield (1/PE) vs the whole universe
  RISK      realized volatility, max drawdown, beta vs the IWDA benchmark

Each dimension becomes a percentile score 0–100 among peers, and the
composite is their plain average — Lesson 7: a simple average of good
signals is brutally hard to beat, so that is the baseline this engine
ships with. LightGBM ranking (Phase 5b) must beat THIS to earn its place.

This is evidence ranking, not prophecy: the engine orders the universe
by documented factor evidence and shows its work. The judgment — and
the responsibility — remain human.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dewaag.vault import store
from dewaag.vault.fundamentals import load_fundamentals

_cache: dict = {"key": None, "df": None}

TRADING_DAYS = 252


def _series(symbol: str) -> pd.Series | None:
    try:
        df = store.load_prices(symbol).sort_values("date")
    except FileNotFoundError:
        return None
    s = pd.Series(df["adj_close"].values, index=pd.to_datetime(df["date"]))
    return s.dropna()


def _price_block(s: pd.Series, bench: pd.Series | None) -> dict:
    out: dict = {}
    last = float(s.iloc[-1])

    def ret(days: int) -> float | None:
        if len(s) <= days:
            return None
        return float(last / s.iloc[-1 - days] - 1)

    out["ret_1m"], out["ret_3m"], out["ret_6m"], out["ret_12m"] = (
        ret(21), ret(63), ret(126), ret(TRADING_DAYS))
    # 12-1 momentum: last year EXCLUDING the last month — the classic
    # formulation (the most recent month tends to mean-revert).
    if len(s) > TRADING_DAYS:
        out["mom_12_1"] = float(s.iloc[-21] / s.iloc[-TRADING_DAYS] - 1)
    else:
        out["mom_12_1"] = None

    yr = s.iloc[-TRADING_DAYS:]
    rets = yr.pct_change().dropna()
    out["vol_1y"] = float(rets.std() * np.sqrt(TRADING_DAYS)) if len(rets) > 60 else None
    peak = yr.cummax()
    out["max_dd_1y"] = float((yr / peak - 1).min()) if len(yr) > 60 else None

    ma200 = float(s.iloc[-200:].mean()) if len(s) >= 200 else None
    out["above_200d"] = bool(last > ma200) if ma200 else None
    out["dist_200d"] = float(last / ma200 - 1) if ma200 else None

    lo, hi = float(yr.min()), float(yr.max())
    out["pos_52w"] = float((last - lo) / (hi - lo)) if hi > lo else None

    if bench is not None and len(rets) > 60:
        b = bench.pct_change().dropna()
        joined = pd.concat([rets, b], axis=1, join="inner").dropna()
        if len(joined) > 60 and joined.iloc[:, 1].var() > 0:
            out["beta_1y"] = float(joined.cov().iloc[0, 1] / joined.iloc[:, 1].var())
        else:
            out["beta_1y"] = None
    else:
        out["beta_1y"] = None
    return out


def _fundamental_block(symbol: str, price: float) -> dict:
    from dewaag.engine.ratios import toolkit

    tk = toolkit(load_fundamentals(symbol))
    years = tk["years"]
    out: dict = {"pe": None, "earnings_yield": None, "roe": None, "roe_avg": None,
                 "margin_trend": None, "dte": None, "cash_conv_avg": None,
                 "rev_growth": None, "growth_trend": None, "fund_years": len(years)}
    if not years:
        return out
    latest = years[-1]
    roes = [y["roe"] for y in years if y["roe"] is not None]
    margins = [y["net_margin"] for y in years if y["net_margin"] is not None]
    convs = [y["cash_conversion"] for y in years if y["cash_conversion"] is not None]
    growths = [y["rev_growth"] for y in years if y["rev_growth"] is not None]

    out["roe"] = latest["roe"]
    out["roe_avg"] = float(np.mean(roes)) if roes else None
    out["margin_trend"] = (margins[-1] - margins[0]) if len(margins) >= 2 else None
    out["dte"] = latest["debt_to_equity"]
    out["cash_conv_avg"] = float(np.mean(convs)) if convs else None
    out["rev_growth"] = growths[-1] if growths else None
    out["growth_trend"] = (growths[-1] - growths[0]) if len(growths) >= 2 else None

    ni, sh = latest.get("net_income"), latest.get("shares")
    if ni and sh and price:
        eps = ni / sh
        if eps > 0:
            out["pe"] = price / eps
            out["earnings_yield"] = eps / price
    return out


def _pct_rank(col: pd.Series) -> pd.Series:
    """Percentile 0–100 among non-null peers. None stays None — a missing
    number is missing, never silently average (that's how bias sneaks in)."""
    return col.rank(pct=True) * 100


def compute_signals() -> pd.DataFrame:
    universe = store.load_universe()
    key = str(store.vault_status().get("last_date"))
    if _cache["key"] == key and _cache["df"] is not None:
        return _cache["df"]

    bench = _series("IWDA")
    rows = []
    for _, u in universe.iterrows():
        if u["tier"] in ("fx",):
            continue
        s = _series(u["symbol"])
        if s is None or len(s) < 260:
            continue
        price_native = float(store.load_prices(u["symbol"]).sort_values("date").iloc[-1]["close"])
        row = {"symbol": u["symbol"], "name": u["name"], "country": u["country"],
               "tier": u["tier"], "currency": u["currency"],
               "sector": u.get("sector", "other"), "price": price_native}
        row.update(_price_block(s, bench))
        row.update(_fundamental_block(u["symbol"], price_native))
        rows.append(row)

    df = pd.DataFrame(rows).set_index("symbol", drop=False)
    stocks = df[df["tier"] != "etf"]

    # --- dimension scores: percentiles among stocks (ETF excluded) ---
    # SECTOR-AWARE RULERS (audit fix): banks, insurers and holdings live on
    # leverage, and their cash-flow statements aren't industrial cash flows.
    # Judging KBC by debt/equity was a metric mismatch, not a finding.
    quality_full = pd.concat([
        _pct_rank(stocks["roe_avg"]),
        _pct_rank(-stocks["dte"]),                      # less debt = better
        _pct_rank(stocks["cash_conv_avg"].clip(upper=2)),  # >2 is noise, not virtue
        _pct_rank(stocks["margin_trend"]),
    ], axis=1).mean(axis=1, skipna=True)
    quality_fin = pd.concat([
        _pct_rank(stocks["roe_avg"]),
        _pct_rank(stocks["margin_trend"]),
    ], axis=1).mean(axis=1, skipna=True)
    is_fin = df["sector"].isin(["financials", "holding"])
    df["q_score"] = quality_full.where(~is_fin, quality_fin).round(0)

    df["v_score"] = _pct_rank(stocks["earnings_yield"]).round(0)
    df["m_score"] = _pct_rank(stocks["mom_12_1"]).round(0)

    df["composite"] = df[["q_score", "v_score", "m_score"]].mean(axis=1, skipna=True).round(0)
    df["coverage"] = df[["q_score", "v_score", "m_score"]].notna().sum(axis=1)

    _cache.update(key=key, df=df)
    return df


def engine_read(symbol: str) -> dict:
    """The auto-generated evidence bullets for one company — the engine's
    read, with numbers, so the human can disagree with something concrete."""
    df = compute_signals()
    if symbol not in df.index:
        return {"scores": {}, "bullets": ["not enough history for the engine (need ~1 year)"]}
    r = df.loc[symbol]
    stocks = df[df["tier"] != "etf"]
    med_pe = float(stocks["pe"].median())

    bullets: list[str] = []
    b = bullets.append

    if r.get("sector") in ("financials", "holding"):
        b("financial-sector ruler applied: debt and cash-conversion excluded from the quality score — leverage is structural for banks and holdings, not a defect")

    # quality evidence
    if pd.notna(r["roe_avg"]):
        b(f"ROE averaged {r['roe_avg']*100:.0f}% over {int(r['fund_years'])} years"
          + (" — a good business by the >15% test" if r["roe_avg"] > 0.15 else " — below the 15% quality bar")
          + (f", but debt/equity {r['dte']:.1f} inflates it — read them together" if pd.notna(r["dte"]) and r["dte"] > 1.5 else ""))
    if pd.notna(r["cash_conv_avg"]):
        b(f"cash conversion averages {r['cash_conv_avg']:.2f} — "
          + ("profits are backed by real cash" if r["cash_conv_avg"] >= 0.9 else "profit is NOT fully converting to cash — the loudest warning in accounting"))
    if pd.notna(r["rev_growth"]) and pd.notna(r["growth_trend"]):
        trend = "accelerating" if r["growth_trend"] > 0.01 else ("decelerating" if r["growth_trend"] < -0.01 else "steady")
        b(f"revenue growth {r['rev_growth']*100:.0f}%/yr and {trend}")

    # value evidence
    if pd.notna(r["pe"]):
        rel = "above" if r["pe"] > med_pe else "below"
        b(f"P/E {r['pe']:.0f} vs universe median {med_pe:.0f} ({rel}) — implied growth ≈ {max(0.0,(0.08 - 1/r['pe']))*100:.1f}%/yr forever; judge the promise, not the number")
    else:
        b("no positive earnings — P/E is the wrong ruler here (danger zone for beginners)")

    # momentum & risk evidence
    if pd.notna(r["mom_12_1"]):
        b(f"12-1 momentum {r['mom_12_1']*100:+.0f}% ({'top' if r['m_score']>=75 else 'bottom' if r['m_score']<=25 else 'middle'} of universe) — the market has been {'rewarding' if r['mom_12_1']>0 else 'punishing'} it")
    if pd.notna(r["vol_1y"]) and pd.notna(r["max_dd_1y"]):
        b(f"risk: {r['vol_1y']*100:.0f}% volatility, {r['max_dd_1y']*100:.0f}% worst drawdown this year"
          + (f", beta {r['beta_1y']:.1f} vs world" if pd.notna(r["beta_1y"]) else "")
          + " — size positions from THESE numbers, not from hope")

    # the sharpest cross-check the engine can make alone:
    if pd.notna(r["v_score"]) and pd.notna(r["q_score"]):
        if r["v_score"] > 70 and r["q_score"] < 35:
            b("⚠ cheap AND low quality — the classic value-trap shape (Lesson 4): verify what decline the market is pricing before touching")
        elif r["v_score"] > 60 and r["q_score"] > 60:
            b("✓ quality at a reasonable price — the rare combination the evidence favors; now do the human work (thesis, margin of safety)")
        elif r["q_score"] > 70 and r["v_score"] < 30:
            b("great business, expensive price — greatness is necessary but not sufficient (Lesson 4 trap #3)")

    scores = {k: (None if pd.isna(r[k]) else int(r[k]))
              for k in ("q_score", "v_score", "m_score", "composite")}
    return {"scores": scores, "coverage": int(r["coverage"]), "bullets": bullets}
