"""Corporate calendar — earnings dates and ex-dividend dates.

Finding 4 of the audit: a professional tool knows what happens next week.
Fetched from the free source per symbol, stored like everything else
(a parquet you can open), refreshed by the nightly job chain.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from dewaag.vault import store

CALENDAR_PATH = store.DATA_DIR / "calendar.parquet"


def fetch_symbol_calendar(symbol: str, yahoo_symbol: str) -> list[dict]:
    import yfinance as yf

    rows: list[dict] = []
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        cal = yf.Ticker(yahoo_symbol).calendar or {}
    except Exception:  # noqa: BLE001 — no calendar is a valid state
        return rows

    for d in cal.get("Earnings Date", []) or []:
        rows.append({"symbol": symbol, "event": "earnings",
                     "date": pd.Timestamp(d).date(), "ingested_at": stamp})
    exd = cal.get("Ex-Dividend Date")
    if exd:
        rows.append({"symbol": symbol, "event": "ex_dividend",
                     "date": pd.Timestamp(exd).date(), "ingested_at": stamp})
    return rows


def refresh_calendar() -> int:
    universe = store.load_universe()
    all_rows: list[dict] = []
    for _, r in universe.iterrows():
        if r["tier"] in ("fx",):
            continue
        all_rows.extend(fetch_symbol_calendar(r["symbol"], r["yahoo"]))
    df = pd.DataFrame(all_rows, columns=["symbol", "event", "date", "ingested_at"])
    CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CALENDAR_PATH, index=False)
    return len(df)


def upcoming(days: int = 14) -> list[dict]:
    if not CALENDAR_PATH.exists():
        return []
    df = pd.read_parquet(CALENDAR_PATH)
    if df.empty:
        return []
    today = pd.Timestamp.today().normalize()
    df["date"] = pd.to_datetime(df["date"])
    sel = df[(df["date"] >= today) & (df["date"] <= today + pd.Timedelta(days=days))]
    sel = sel.sort_values("date")
    return [{"symbol": r["symbol"], "event": r["event"], "date": str(r["date"].date()),
             "days_away": int((r["date"] - today).days)} for _, r in sel.iterrows()]
