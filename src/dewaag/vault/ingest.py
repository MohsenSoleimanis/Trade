"""Layer 1 ingestion — daily prices from free sources (yfinance).

Two design rules, both from the curriculum:

1. POINT-IN-TIME: every row carries `ingested_at` — when this fact entered
   the vault. For prices this seems pedantic; for fundamentals (Phase 2+)
   it is the difference between an honest backtest and a lying one, so the
   discipline starts here, on day one, on every table.

2. IDEMPOTENT: running ingest twice must never duplicate or corrupt data.
   Jobs that can't be safely re-run don't survive contact with real life
   (crashed laptops, flaky wifi, Euronext holidays).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from dewaag.vault import store
from dewaag.vault.universe import build_universe

START_DATE = "2005-01-01"  # ~20 years: enough to include 2008 — never
                           # trust a dataset that only remembers bull markets.

PRICE_COLUMNS = [
    "symbol", "date", "open", "high", "low", "close", "adj_close",
    "volume", "source", "ingested_at",
]


def _normalize(symbol: str, raw: pd.DataFrame) -> pd.DataFrame:
    """yfinance frame -> our schema. Keeps BOTH close and adj_close:
    close is what you'd have paid (order tickets), adj_close folds in
    splits/dividends (return calculations). Mixing them up is the classic
    silent corruption from Lesson 1 — so both live in the vault, named."""
    df = raw.reset_index()
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={"index": "date"})
    keep = df[["date", "open", "high", "low", "close", "adj_close", "volume"]].copy()
    keep["date"] = pd.to_datetime(keep["date"]).dt.date
    keep = keep.dropna(subset=["close"])
    keep.insert(0, "symbol", symbol)
    keep["source"] = "yahoo"
    keep["ingested_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return keep[PRICE_COLUMNS]


def fetch_yahoo(yahoo_symbol: str, start: str) -> pd.DataFrame:
    import yfinance as yf  # imported here so tests never need the network

    raw = yf.download(
        yahoo_symbol, start=start, auto_adjust=False,
        progress=False, multi_level_index=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"no data returned for {yahoo_symbol}")
    return raw


def ingest_symbol(symbol: str, yahoo_symbol: str, start: str = START_DATE) -> int:
    """Fetch (incrementally), merge, dedupe by date, write. Returns new rows."""
    path = store.price_path(symbol)
    existing = pd.read_parquet(path) if path.exists() else None
    fetch_from = start
    if existing is not None and len(existing):
        last = pd.to_datetime(existing["date"]).max()
        fetch_from = (last - pd.Timedelta(days=5)).strftime("%Y-%m-%d")  # small
        # overlap on purpose: re-fetching a few days self-heals partial rows.

    fresh = _normalize(symbol, fetch_yahoo(yahoo_symbol, fetch_from))
    if existing is not None:
        merged = pd.concat([existing, fresh], ignore_index=True)
        merged = merged.drop_duplicates(subset=["date"], keep="last")  # idempotent
    else:
        merged = fresh
    merged = merged.sort_values("date").reset_index(drop=True)

    # We compute our own dividend adjustment (see adjust.py: the source's
    # adj column proved broken). Recomputed over the FULL merged history on
    # every ingest, because each new dividend rescales all older rows.
    from dewaag.vault.adjust import compute_adjusted, fetch_dividends

    merged["adj_close"] = compute_adjusted(merged, fetch_dividends(yahoo_symbol))
    new_rows = len(merged) - (len(existing) if existing is not None else 0)
    store.ensure_dirs()
    merged.to_parquet(path, index=False)
    return max(new_rows, 0)


def ingest_universe(start: str = START_DATE) -> dict:
    """Ingest every universe symbol. Failures are collected, not fatal —
    one bad ticker must never block the other forty (ops rule of thumb)."""
    universe = build_universe()
    store.save_universe(universe)
    ok, failed, total_new = [], [], 0
    for _, row in universe.iterrows():
        try:
            n = ingest_symbol(row["symbol"], row["yahoo"], start)
            ok.append(row["symbol"])
            total_new += n
            print(f"  {row['symbol']:<6} +{n} rows")
        except Exception as e:  # noqa: BLE001 — log-and-continue is the point
            failed.append((row["symbol"], str(e)[:90]))
            print(f"  {row['symbol']:<6} FAILED: {str(e)[:90]}")
    return {"ok": len(ok), "failed": failed, "new_rows": total_new}
