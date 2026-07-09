"""The engine's claims must be provable — a wrong 'evidence bullet'
teaches wrong lessons with machine confidence, the worst kind."""

import numpy as np
import pandas as pd

from dewaag.engine import signals as sig


def make_price_series(n=600, drift=0.0005, start=100.0, seed_wiggle=0.003):
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    vals = [start]
    for i in range(1, n):
        vals.append(vals[-1] * (1 + drift + seed_wiggle * np.sin(i / 7)))
    return pd.Series(vals, index=idx)


def test_momentum_12_1_excludes_last_month():
    s = make_price_series()
    out = sig._price_block(s, None)
    expected = float(s.iloc[-21] / s.iloc[-252] - 1)
    assert abs(out["mom_12_1"] - expected) < 1e-9


def test_price_block_risk_numbers_sane():
    s = make_price_series()
    out = sig._price_block(s, None)
    assert out["vol_1y"] is not None and 0 < out["vol_1y"] < 1
    assert out["max_dd_1y"] <= 0
    assert out["pos_52w"] is None or 0 <= out["pos_52w"] <= 1


def test_beta_of_benchmark_against_itself_is_one():
    s = make_price_series()
    out = sig._price_block(s, s)
    assert abs(out["beta_1y"] - 1.0) < 1e-6


def test_pct_rank_leaves_missing_missing():
    col = pd.Series([1.0, 2.0, None, 4.0])
    r = sig._pct_rank(col)
    assert pd.isna(r.iloc[2])          # missing stays missing — no silent fills
    assert r.iloc[3] == 100.0          # best of the non-missing
