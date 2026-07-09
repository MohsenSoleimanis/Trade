"""Fundamentals ingestion — the raw material of Lessons 3 & 4.

Free source (yfinance) gives ~4 years of annual statements per company:
income statement, balance sheet, cash flow. Enough for the ratio toolkit
and trend arrows; the EDGAR/NBB deep history arrives in a later phase.

Storage is LONG format — one row per (item, period_end) — with the same
`ingested_at` point-in-time stamp as prices. Note the dedupe rule below:
first-seen wins, so the timestamp keeps telling the truth about when a
number became known to us. (Restatement tracking = later phase.)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from dewaag.vault import store

# our item name -> acceptable source labels, tried in order.
# yfinance labels drift between versions and markets; tolerate synonyms.
ITEMS = {
    "income": {
        "revenue": ["Total Revenue", "Operating Revenue"],
        "net_income": ["Net Income", "Net Income Common Stockholders"],
        "operating_income": ["Operating Income", "EBIT"],
    },
    "balance": {
        "equity": ["Stockholders Equity", "Common Stock Equity"],
        "total_debt": ["Total Debt"],
        "shares": ["Ordinary Shares Number", "Share Issued"],
        "cash": ["Cash And Cash Equivalents",
                 "Cash Cash Equivalents And Short Term Investments"],
    },
    "cashflow": {
        "operating_cf": ["Operating Cash Flow",
                         "Cash Flow From Continuing Operating Activities"],
        "capex": ["Capital Expenditure"],
    },
}

FUND_COLUMNS = ["symbol", "item", "period_end", "value", "source", "ingested_at"]


def fundamentals_path(symbol: str):
    return store.DATA_DIR / "fundamentals" / f"{symbol}.parquet"


def fetch_fundamentals(symbol: str, yahoo_symbol: str) -> pd.DataFrame:
    import yfinance as yf  # here so tests never need the network

    t = yf.Ticker(yahoo_symbol)
    frames = {"income": t.income_stmt, "balance": t.balance_sheet, "cashflow": t.cashflow}
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict] = []
    for group, mapping in ITEMS.items():
        df = frames.get(group)
        if df is None or df.empty:
            continue
        for item, labels in mapping.items():
            for label in labels:
                if label in df.index:
                    for period, value in df.loc[label].items():
                        if pd.notna(value):
                            rows.append({
                                "symbol": symbol, "item": item,
                                "period_end": pd.Timestamp(period).date(),
                                "value": float(value),
                                "source": "yahoo", "ingested_at": stamp,
                            })
                    break  # first matching label wins
    return pd.DataFrame(rows, columns=FUND_COLUMNS)


def ingest_symbol_fundamentals(symbol: str, yahoo_symbol: str) -> int:
    fresh = fetch_fundamentals(symbol, yahoo_symbol)
    if fresh.empty:
        raise RuntimeError("no fundamentals returned")
    path = fundamentals_path(symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_parquet(path)
        merged = pd.concat([existing, fresh], ignore_index=True)
        # first-seen wins: an unchanged number keeps its original
        # ingested_at, so "when did we know this?" stays honest.
        merged = merged.drop_duplicates(subset=["item", "period_end"], keep="first")
    else:
        merged = fresh
    merged = merged.sort_values(["item", "period_end"]).reset_index(drop=True)
    merged.to_parquet(path, index=False)
    return len(merged)


def ingest_universe_fundamentals() -> dict:
    universe = store.load_universe()
    ok, failed = [], []
    for _, row in universe.iterrows():
        if row["tier"] == "etf":
            continue  # ETFs have no statements — they're baskets (Lesson 1)
        try:
            n = ingest_symbol_fundamentals(row["symbol"], row["yahoo"])
            ok.append(row["symbol"])
            print(f"  {row['symbol']:<6} {n} facts")
        except Exception as e:  # noqa: BLE001
            failed.append((row["symbol"], str(e)[:80]))
            print(f"  {row['symbol']:<6} FAILED: {str(e)[:80]}")
    return {"ok": len(ok), "failed": failed}


def load_fundamentals(symbol: str) -> pd.DataFrame:
    path = fundamentals_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=FUND_COLUMNS)
    return pd.read_parquet(path)
