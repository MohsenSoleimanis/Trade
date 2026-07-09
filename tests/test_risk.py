"""Risk engine math — provable on synthetic data."""

import numpy as np
import pandas as pd

from dewaag.engine.risk import portfolio_vol, risk_contributions, var_es


def make_rets(n=200, vol_a=0.02, vol_b=0.04, corr=0.0, seed=7):
    rng = np.random.default_rng(seed)
    a = rng.normal(0, vol_a, n)
    b = corr * a * (vol_b / vol_a) + np.sqrt(max(0.0, 1 - corr**2)) * rng.normal(0, vol_b, n)
    idx = pd.date_range("2020-01-03", periods=n, freq="W-FRI")
    return pd.DataFrame({"A": a, "B": b}, index=idx)


def test_single_asset_vol_matches_its_own_vol():
    rets = make_rets()
    w = pd.Series({"A": 1.0})
    pv = portfolio_vol(w, rets)
    expected = float(rets["A"].std() * np.sqrt(52))
    assert abs(pv - expected) < 1e-9


def test_diversification_lowers_vol_when_uncorrelated():
    rets = make_rets(corr=0.0)
    w_half = pd.Series({"A": 0.5, "B": 0.5})
    pv = portfolio_vol(w_half, rets)
    wavg = 0.5 * rets["A"].std() * np.sqrt(52) + 0.5 * rets["B"].std() * np.sqrt(52)
    assert pv < wavg  # the free lunch, measured (Lesson 6 §4)


def test_risk_contributions_sum_to_one_and_favor_the_wild_asset():
    rets = make_rets(vol_a=0.01, vol_b=0.05, corr=0.2)
    w = pd.Series({"A": 0.5, "B": 0.5})
    rc = risk_contributions(w, rets)
    assert abs(sum(rc.values()) - 1.0) < 0.01
    # half the MONEY is in B, but far more than half the RISK:
    assert rc["B"] > 0.7


def test_var_hist_positive_and_orders_correctly():
    rets = make_rets()
    w = pd.Series({"A": 0.5, "B": 0.5})
    v = var_es(w, rets, equity=10_000)
    assert v["var95_hist"] > 0
    assert v["var99_hist"] >= v["var95_hist"]      # deeper tail, bigger loss
    assert v["es95_hist"] >= v["var95_hist"]       # ES beyond VaR by definition
