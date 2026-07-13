"""The Autonomous Engine — L2 regime, L3 committee, L4 allocator,
L5 construction, L9 proposals. Fully offline: synthetic signals frame,
fake constitution and book. No network, no vault.
"""

import numpy as np
import pandas as pd
import pytest

from dewaag.constitution import Constitution
from dewaag.engine.auto import regime as regime_mod
from dewaag.engine.auto.allocator import allocate
from dewaag.engine.auto.construct import build_targets
from dewaag.engine.auto.strategies import committee_scores


def _signals(n=30, seed=1):
    rng = np.random.RandomState(seed)
    tiers = ["mega", "large", "mid", "small"]
    rows = []
    for i in range(n):
        rows.append({
            "symbol": f"S{i:02d}", "name": f"Name {i}", "country": "BE" if i % 3 else "US",
            "tier": tiers[i % 4], "currency": "EUR" if i % 2 else "USD",
            "sector": "tech" if i % 5 else "financials",
            "price": float(rng.uniform(10, 200)),
            "ret_1m": float(rng.uniform(-0.1, 0.1)),
            "mom_12_1": float(rng.uniform(-0.3, 0.5)),
            "vol_1y": float(rng.uniform(0.12, 0.55)),
            "max_dd_1y": float(rng.uniform(-0.5, -0.05)),
            "dist_200d": float(rng.uniform(-0.2, 0.3)),
            "above_200d": bool(rng.rand() > 0.5),
            "beta_1y": float(rng.uniform(0.3, 1.8)),
            "earnings_yield": float(rng.uniform(0.01, 0.12)),
            "rev_growth": float(rng.uniform(-0.05, 0.25)),
            "growth_trend": float(rng.uniform(-0.05, 0.05)),
            "q_score": float(rng.uniform(0, 100)),
            "v_score": float(rng.uniform(0, 100)),
            "m_score": float(rng.uniform(0, 100)),
        })
    return pd.DataFrame(rows).set_index("symbol", drop=False)


def _constitution():
    return Constitution(owner="T", signed_on="2026-07-13", max_risk_per_idea_pct=1.0,
                        max_position_pct=10.0, max_drawdown_eur=1500, emergency_fund_months=6,
                        leverage=0, require_thesis=True, min_years_before_strategy_change=5)


def test_regime_gross_dial_tracks_risk(monkeypatch):
    df = _signals()

    def fake_series(sym):
        idx = pd.date_range("2022-01-01", periods=260, freq="D")
        if sym == "IWDA":
            return pd.Series(np.linspace(80, 120, 260), index=idx)   # clear uptrend
        if sym == "VIX":
            return pd.Series(np.full(260, 12.0), index=idx)          # calm
        if sym == "US10Y":
            return pd.Series(np.full(260, 4.0), index=idx)
        return None

    monkeypatch.setattr(regime_mod, "_series", fake_series)
    # force breadth high
    df["above_200d"] = True
    r = regime_mod.classify(df)
    assert r["risk"] == "risk_on"
    assert r["gross_target"] == 0.95
    assert "bull" in r["tags"] and "low_vol" in r["tags"]


def test_committee_every_strategy_votes_and_scores_are_bounded():
    df = _signals()
    votes = committee_scores(df)
    assert votes.shape[0] == len(df)                      # every stock scored
    assert votes.shape[1] == 9                            # nine committee members
    finite = votes.to_numpy(dtype=float)
    finite = finite[~np.isnan(finite)]
    assert finite.min() >= 0 and finite.max() <= 100


def test_allocator_tilts_weight_toward_favored_strategies():
    df = _signals()
    risk_off = {"tags": ["risk_off", "bear", "high_vol"]}
    risk_on = {"tags": ["risk_on", "bull", "low_vol"]}
    w_off = allocate(df, risk_off)["weights"]
    w_on = allocate(df, risk_on)["weights"]
    # low-vol & defensive should carry MORE weight in a storm than in clear skies
    assert w_off["lowvol"] > w_on["lowvol"]
    assert w_off["defensive"] > w_on["defensive"]
    # trend & momentum should carry LESS in a storm
    assert w_off["trend"] < w_on["trend"]
    assert abs(sum(w_on.values()) - 1.0) < 1e-6           # weights normalize


def test_construction_respects_caps_and_no_leverage():
    df = _signals()
    regime = {"tags": ["risk_on", "bull"], "gross_target": 0.95}
    alloc = allocate(df, regime)
    targets = build_targets(df, alloc["blended"], regime, max_position_pct=10.0)

    assert targets["picks"], "expected at least one pick"
    total = sum(p["weight"] for p in targets["picks"])
    assert total <= 0.95 + 1e-6                           # never over the gross dial
    assert total <= 1.0                                   # never leveraged
    assert all(p["weight"] <= 0.10 + 1e-6 for p in targets["picks"])  # single-name cap
    assert len(targets["picks"]) <= 15


def test_core_satellite_holds_a_basket_core_exempt_from_the_cap():
    df = _signals()
    # inject a world-core basket the engine should hold as the foundation
    core = {"symbol": "WEBN", "name": "World basket", "country": "IE", "tier": "etf",
            "currency": "EUR", "sector": "etf", "price": 12.8, "ret_1m": 0.01,
            "mom_12_1": 0.12, "vol_1y": 0.14, "max_dd_1y": -0.1, "dist_200d": 0.05,
            "above_200d": True, "beta_1y": 1.0, "earnings_yield": np.nan, "rev_growth": np.nan,
            "growth_trend": np.nan, "q_score": np.nan, "v_score": np.nan, "m_score": 60.0}
    df = pd.concat([df, pd.DataFrame([core]).set_index("symbol", drop=False)])

    regime = {"tags": ["risk_on", "bull"], "gross_target": 0.95, "risk": "risk_on"}
    alloc = allocate(df, regime)
    targets = build_targets(df, alloc["blended"], regime, max_position_pct=10.0)

    core_picks = [p for p in targets["picks"] if p.get("is_core")]
    sats = [p for p in targets["picks"] if not p.get("is_core")]
    assert len(core_picks) == 1 and core_picks[0]["symbol"] == "WEBN"
    assert core_picks[0]["weight"] > 0.10               # core is exempt from the single-name cap
    assert all(p["weight"] <= 0.10 + 1e-6 for p in sats)  # satellites still capped
    total = sum(p["weight"] for p in targets["picks"])
    assert total <= 1.0                                   # never leveraged (the hard law)
    assert total <= 0.95 + 0.01                           # ~= the gross dial, within rounding


def test_pipeline_proposals_blocked_when_unsigned(monkeypatch):
    from dewaag.engine.auto import pipeline

    df = _signals()
    unsigned = Constitution(owner="T", signed_on=None, max_risk_per_idea_pct=1.0,
                            max_position_pct=10.0, max_drawdown_eur=0, emergency_fund_months=6,
                            leverage=0, require_thesis=True, min_years_before_strategy_change=5)
    snap = {"equity": 100000.0, "cash": 100000.0, "positions": [], "constitution_signed": False}

    monkeypatch.setattr(regime_mod, "_series", lambda s: None)      # no macro -> neutral regime
    monkeypatch.setattr("dewaag.portfolio.to_eur", lambda amt, cur: amt)

    plan = pipeline.build_plan(signals_df=df, snap=snap, constitution=unsigned, persist=False)
    assert plan["proposals"], "a big book should generate buy proposals"
    assert all(p["side"] != "BUY" or p["status"] == "blocked" for p in plan["proposals"])
    assert "unsigned" in plan["executable_note"].lower()


def test_pipeline_signed_book_clears_some_proposals(monkeypatch):
    from dewaag.engine.auto import pipeline

    df = _signals()
    snap = {"equity": 100000.0, "cash": 100000.0, "positions": [], "constitution_signed": True}
    monkeypatch.setattr(regime_mod, "_series", lambda s: None)
    monkeypatch.setattr("dewaag.portfolio.to_eur", lambda amt, cur: amt)

    plan = pipeline.build_plan(signals_df=df, snap=snap, constitution=_constitution(), persist=False)
    buys = [p for p in plan["proposals"] if p["side"] == "BUY"]
    assert buys, "expected buy proposals on a large signed book"
    assert any(p["status"] == "pending" for p in buys)             # some clear the gate
    for p in buys:
        assert p["wrong_price"] < p["price"]                       # every buy has a stop below entry
        assert 8.0 <= p["stop_pct"] <= 30.0


def test_engine_book_fills_approved_buy_and_blocks_bad_sell(tmp_path, monkeypatch):
    from dewaag.engine.auto import book as bk

    monkeypatch.setattr(bk, "ENGINE_BOOK_PATH", tmp_path / "engine_book.json")
    monkeypatch.setattr(bk, "STARTING_CAPITAL", 100_000.0)   # scale-independent for this test
    monkeypatch.setattr(bk, "_last_close", lambda s: 100.0)
    monkeypatch.setattr("dewaag.portfolio.to_eur", lambda amt, cur: amt)
    fake = pd.DataFrame([{"symbol": "TST", "yahoo": "TST", "name": "Test", "exchange": "EBR",
                          "currency": "EUR", "country": "BE", "tier": "mid", "sector": "tech"}]
                        ).set_index("symbol", drop=False)
    monkeypatch.setattr(bk.store, "load_universe", lambda: fake)

    # a well-formed BUY: 50 sh @ ~100, stop at 90 -> risk 50*10 = 500 <= 1% of 100k
    buy = {"symbol": "TST", "side": "BUY", "shares": 50, "price": 100.0, "tier": "mid",
           "currency": "EUR", "wrong_price": 90.0, "rationale": "a valid systematic thesis for the test"}
    r = bk.execute_proposal(buy)
    assert r["ok"], r.get("blocks")
    snap = bk.snapshot()
    assert snap["cash"] < 100_000 and len(snap["positions"]) == 1

    # selling more than held is refused, not silently clamped
    bad_sell = {"symbol": "TST", "side": "SELL", "shares": 999, "price": 100.0,
                "tier": "mid", "currency": "EUR", "rationale": "exit"}
    r2 = bk.execute_proposal(bad_sell)
    assert r2["ok"] is False
