"""Macro lens — regime reads, measured sensitivities, tier-aware quality.

The sensitivity test plants a known relationship (stock = 0.8·market +
0.5·oil) in synthetic data and demands the engine dig it back out — and
report ~zero for a channel that was pure noise.
"""

import numpy as np
import pandas as pd

import dewaag.engine.macro as macro
from dewaag.vault.quality import check_frame


def _frame(dates, prices):
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "adj_close": prices,
                         "close": prices, "ingested_at": "2026-07-10"})


def _fake_store(monkeypatch):
    rng = np.random.RandomState(42)
    dates = pd.bdate_range("2022-01-03", periods=800)
    m = rng.normal(0, 0.001, len(dates))          # market factor
    oil = rng.normal(0, 0.001, len(dates))        # oil factor
    noise = rng.normal(0, 0.001, len(dates))      # gold: pure noise
    series = {
        "IWDA":  100 * np.cumprod(1 + m),
        "BRENT": 80 * np.cumprod(1 + oil),
        "GOLD":  1800 * np.cumprod(1 + noise),
        "STK":   50 * np.cumprod(1 + 0.8 * m + 0.5 * oil),
        "VIX":   np.full(len(dates), 16.0),
        "US10Y": np.full(len(dates), 4.5),
        "EURUSD": np.full(len(dates), 1.10),
    }

    def load_prices(sym):
        if sym not in series:
            raise FileNotFoundError(sym)
        return _frame(dates, series[sym])

    monkeypatch.setattr(macro.store, "load_prices", load_prices)
    return dates


def test_sensitivities_recover_planted_relationship(monkeypatch):
    _fake_store(monkeypatch)
    out = macro.sensitivities("STK")
    by = {s["channel"]: s for s in out}

    assert abs(by["IWDA"]["beta"] - 0.8) < 0.1          # the tide
    assert abs(by["BRENT"]["beta"] - 0.5) < 0.1         # planted oil link found
    assert by["BRENT"]["strength"] in ("clear", "strong")
    # noise can land at |r|~0.1 by chance in 156 weekly samples — the honest
    # claim is that it never reaches "clear", not that it is exactly zero
    assert by["GOLD"]["strength"] in ("negligible", "mild")
    assert abs(by["GOLD"]["r"]) < 0.2
    assert out[0]["channel"] == "IWDA"                   # tide always first


def test_regime_reads_are_plain_language(monkeypatch):
    _fake_store(monkeypatch)
    reads = {r["symbol"]: r["read"] for r in macro.regime()}
    assert "the market is normal" in reads["VIX"]        # 16 -> normal bucket
    assert "4.50%" in reads["US10Y"]                     # yield, not x10
    assert "$" in reads["EURUSD"]


def test_quality_spike_check_is_off_for_macro_tier():
    dates = pd.bdate_range("2024-01-01", periods=300)
    prices = np.full(len(dates), 20.0)
    prices[150] = 38.0                                   # +90% day: VIX does this
    df = _frame(dates, prices)
    today = dates[-1]

    stock_checks = {f["check"] for f in check_frame("X", df, today=today)}
    macro_checks = {f["check"] for f in check_frame("VIX", df, today=today, tier="macro")}
    assert "spike" in stock_checks                       # for a stock: data error
    assert "spike" not in macro_checks                   # for VIX: information
