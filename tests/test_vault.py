"""Vault tests — no network required anywhere.

The quality checks are pure functions over frames, so the immune system
itself is tested with synthetic data: a clean history must pass, and each
disease (spike, gap, negative price) must be caught.
"""

import pandas as pd

from dewaag.vault.quality import check_frame, gate
from dewaag.vault.universe import COLUMNS, build_universe


def make_frame(n=300, spike_at=None, gap_days=None, negative_at=None):
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    prices = pd.Series([100.0 + 0.05 * i for i in range(n)])
    if spike_at is not None:
        prices.iloc[spike_at:] *= 1.9  # a +90% day
    if negative_at is not None:
        prices.iloc[negative_at] = -1.0
    df = pd.DataFrame(
        {
            "symbol": "TEST",
            "date": dates.date,
            "open": prices, "high": prices, "low": prices,
            "close": prices, "adj_close": prices,
            "volume": 1_000_000, "source": "test", "ingested_at": "t",
        }
    )
    if gap_days is not None:
        # carve a hole in the middle of the history
        mid = dates[n // 2]
        df = df[~((pd.to_datetime(df["date"]) > mid)
                  & (pd.to_datetime(df["date"]) <= mid + pd.Timedelta(days=gap_days)))]
    return df


def levels(findings):
    return {(f["check"], f["level"]) for f in findings}


def test_universe_integrity():
    df = build_universe()
    assert list(df.columns) == COLUMNS
    assert df["symbol"].is_unique
    assert len(df) >= 40
    assert (df["yahoo"].str.len() > 0).all()
    # both markets present — the two-book design starts in Layer 0
    assert (df["country"] == "BE").sum() >= 15
    assert (df["country"] == "US").sum() >= 20


def test_clean_frame_passes():
    findings = check_frame("TEST", make_frame())
    assert findings == []


def test_spike_detected_as_critical():
    findings = check_frame("TEST", make_frame(spike_at=150))
    assert ("spike", "CRITICAL") in levels(findings)


def test_gap_detected():
    findings = check_frame("TEST", make_frame(gap_days=40))
    assert any(c == "gap" for c, _ in levels(findings))


def test_negative_price_is_critical_and_fails_gate():
    findings = check_frame("TEST", make_frame(negative_at=100))
    assert ("nonpositive", "CRITICAL") in levels(findings)
    assert gate(pd.DataFrame(findings)) is False


def test_empty_frame_is_critical():
    findings = check_frame("TEST", make_frame(n=300).iloc[0:0])
    assert ("empty", "CRITICAL") in levels(findings)


def test_dividend_adjustment_math():
    """One €2 dividend on a €100 stock: all history BEFORE the ex-date is
    scaled by (1 - 2/100) = 0.98; the ex-date and after stay unscaled."""
    from dewaag.vault.adjust import compute_adjusted

    frame = make_frame(n=10)
    frame["close"] = 100.0
    ex_date = pd.Timestamp(frame["date"].iloc[5])
    dividends = pd.Series([2.0], index=[ex_date])

    adj = compute_adjusted(frame, dividends)
    assert (adj.iloc[:5].round(6) == 98.0).all()
    assert (adj.iloc[5:].round(6) == 100.0).all()


def test_dividends_before_history_are_ignored():
    """Regression: JPM has decades of dividends BEFORE our 2005 history.
    A boundary bug once applied all of them to the first row, crushing it
    by ~65% and creating a fake 58% spike. Out-of-range dividends must
    change nothing — not even via the ex-date alignment candidates."""
    from dewaag.vault.adjust import compute_adjusted

    frame = make_frame(n=10)
    frame["close"] = 100.0
    old = pd.Timestamp(frame["date"].iloc[0]) - pd.Timedelta(days=365)
    dividends = pd.Series([1.0] * 40, index=[old - pd.Timedelta(days=90 * i) for i in range(40)])

    adj = compute_adjusted(frame, dividends)
    assert (adj == 100.0).all()


def test_adjustment_skips_impossible_dividend():
    """A dividend larger than the share price is a data error and must be
    ignored, not allowed to poison the whole early history (the ABI bug)."""
    from dewaag.vault.adjust import compute_adjusted

    frame = make_frame(n=10)
    frame["close"] = 100.0
    ex_date = pd.Timestamp(frame["date"].iloc[5])
    dividends = pd.Series([150.0], index=[ex_date])  # impossible

    adj = compute_adjusted(frame, dividends)
    assert (adj == 100.0).all()
