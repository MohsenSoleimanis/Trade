"""Dividend back-adjustment — computed by us, not trusted from the source.

Why: on first ingest, the quality gates caught Yahoo's own `Adj Close`
being NEGATIVE for AB InBev's 2005–2008 history (their adjustment math
underflows on long dividend histories). Lesson learned permanently:
free sources give you raw material, never conclusions.

Method (standard back-adjustment, same idea CRSP and real vendors use):
  for each ex-dividend date d with dividend D:
      multiplier m_d = 1 − D / close(previous trading day)
  adj_close(t) = close(t) × ∏ m_d   for every ex-date AFTER t

Intuition (Lesson 1, corporate actions): on the ex-date the price drops
by the dividend without the owner losing anything — so all history BEFORE
the ex-date is scaled down, making returns computed on adj_close reflect
what an owner actually experienced. `close` stays untouched: it is what
you would really have paid on the day (order tickets use close;
return math uses adj_close).
"""

from __future__ import annotations

import pandas as pd


def compute_adjusted(frame: pd.DataFrame, dividends: pd.Series) -> pd.Series:
    """Return the adjusted-close series for a price frame.

    frame:     must have 'date' and 'close' (close = split-adjusted raw).
    dividends: pd.Series of dividend amounts indexed by ex-date.
    """
    df = frame.sort_values("date").reset_index(drop=True)
    dates = pd.to_datetime(df["date"])
    closes = df["close"].astype(float)

    factor = pd.Series(1.0, index=df.index)
    if dividends is None or len(dividends) == 0:
        return closes * factor

    div = dividends.copy()
    div.index = pd.to_datetime(div.index).tz_localize(None)

    for ex_date, amount in div.items():
        # nominal position of the ex-date (first row >= ex-date)...
        pos = int(dates.searchsorted(ex_date))
        # dividends outside our price history are skipped ENTIRELY — before
        # trying any neighbor. (Bug found the hard way: decades of pre-2005
        # dividends all landed on the first row via the pos+1 candidate,
        # crushing it by 40–70% and creating fake spikes. Range guards come
        # before cleverness.)
        if pos <= 0 or pos >= len(df):
            continue
        # ...but source ex-dates are sometimes off by one trading day
        # (found in the wild: D'Ieteren's Dec-2024 special dividend created
        # a fake +95% adjusted move). Fix: try the neighboring boundaries
        # and apply the dividend where it creates the SMALLEST artificial
        # jump in adjusted returns — i.e. where the real price drop was.
        best_pos, best_jump = None, None
        for p in (pos, pos - 1, pos + 1):
            if p <= 0 or p >= len(df):
                continue
            prev_close = float(closes.iloc[p - 1])
            if not (prev_close > 0) or float(amount) >= prev_close:
                # a dividend bigger than the share price is a data error;
                # skipping beats poisoning the entire early history
                continue
            jump = abs(float(closes.iloc[p]) / (prev_close - float(amount)) - 1.0)
            # strict '<' keeps the nominal ex-date on ties (stable choice)
            if best_jump is None or jump < best_jump:
                best_pos, best_jump = p, jump
        if best_pos is None:
            continue
        factor.iloc[:best_pos] *= 1.0 - float(amount) / float(closes.iloc[best_pos - 1])

    return closes * factor


def fetch_dividends(yahoo_symbol: str) -> pd.Series:
    import yfinance as yf  # imported here so tests never need the network

    try:
        return yf.Ticker(yahoo_symbol).dividends
    except Exception:  # noqa: BLE001 — no dividends is a valid state
        return pd.Series(dtype=float)
