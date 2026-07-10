#!/usr/bin/env python3
"""
scan.py — scan a watchlist for long/mid-term trend alignment, ranked best-first.

Technicals come from IBKR (TWS paper, port 7497); fundamentals from yfinance.

Usage:
    python scan.py                      # reads watchlist.txt
    python scan.py AAPL MSFT NVDA       # or pass symbols directly

Scoring (0-6, higher = stronger long+mid-term uptrend):
    +1 price above 200-day SMA      (long-term uptrend)
    +1 golden cross (50 > 200)      (long-term structure)
    +1 price above 50-day SMA       (mid-term uptrend)
    +1 MACD bullish                 (momentum)
    +1 positive 6-month return
    +1 positive 12-month return
"""

import sys
import pandas as pd
from ib_async import IB, Stock, util

try:
    import yfinance as yf
except ImportError:
    yf = None

HOST, PORT, CLIENT_ID = "127.0.0.1", 7497, 12
DEFAULT = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"]


def load_symbols() -> list[str]:
    if len(sys.argv) > 1:
        return [s.upper() for s in sys.argv[1:]]
    try:
        with open("watchlist.txt", encoding="utf-8") as f:
            syms = [ln.strip().upper() for ln in f if ln.strip() and not ln.startswith("#")]
        return syms or DEFAULT
    except FileNotFoundError:
        return DEFAULT


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    return 100 - 100 / (1 + gain / loss)


def fundamentals(sym: str) -> dict:
    if yf is None:
        return {}
    try:
        i = yf.Ticker(sym).info
        return {"pe": i.get("trailingPE"), "mcap": i.get("marketCap"),
                "div": i.get("dividendYield"), "sector": i.get("sector")}
    except Exception:
        return {}


def fmt_mcap(v) -> str:
    if not v:
        return "-"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if v >= div:
            return f"{v / div:.1f}{unit}"
    return f"{v:.0f}"


def analyze(ib: IB, sym: str) -> dict | None:
    contract = Stock(sym, "SMART", "USD")
    if not ib.qualifyContracts(contract):
        return None
    bars = ib.reqHistoricalData(contract, "", "2 Y", "1 day", "TRADES", useRTH=True)
    if not bars:
        return None

    df = util.df(bars)
    df["sma50"] = df.close.rolling(50).mean()
    df["sma200"] = df.close.rolling(200).mean()
    df["rsi14"] = rsi(df.close)
    ema12 = df.close.ewm(span=12, adjust=False).mean()
    ema26 = df.close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    last = df.iloc[-1]
    price = last.close

    def ret(days: int) -> float:
        return (price / df.close.iloc[-1 - days] - 1) * 100 if len(df) > days else float("nan")

    r6, r1y = ret(126), ret(252)
    lt_up = price > last.sma200
    golden = last.sma50 > last.sma200
    mt_up = price > last.sma50
    macd_bull = last.macd > last.signal
    score = int(sum([lt_up, golden, mt_up, macd_bull, r6 > 0, r1y > 0]))

    return {"sym": sym, "price": price, "r6": r6, "r1y": r1y, "lt": lt_up, "mt": mt_up,
            "rsi": last.rsi14, "score": score, **fundamentals(sym)}


def read_label(score: int) -> str:
    return ["Downtrend", "Weak", "Weak", "Mixed", "Constructive", "Strong", "Strong uptrend"][score]


def main() -> None:
    symbols = load_symbols()
    ib = IB()
    try:
        ib.connect(HOST, PORT, clientId=CLIENT_ID, timeout=12, readonly=True)
    except Exception as e:
        sys.exit(f"\n  x Could not connect to TWS on {HOST}:{PORT} - enable the API "
                 f"(File -> Global Configuration -> API -> Settings). ({e})\n")
    ib.reqMarketDataType(3)

    print(f"\nScanning {len(symbols)} symbols...\n")
    rows = []
    for s in symbols:
        r = analyze(ib, s)
        if r:
            rows.append(r)
            print(f"  scanned {s}")
        else:
            print(f"  skipped {s} (no data)")
    ib.disconnect()

    rows.sort(key=lambda r: (r["score"], r["r1y"] if r["r1y"] == r["r1y"] else -999), reverse=True)

    hdr = f"\n{'#':>2}  {'SYM':<6} {'PRICE':>9} {'6M%':>7} {'1Y%':>7}  {'LT':<4}{'MT':<4}{'RSI':>4}  {'P/E':>6} {'MCAP':>7} {'DIV%':>6}  {'SCORE':>5}  READ"
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(rows, 1):
        pe = f"{r['pe']:.1f}" if r.get("pe") else "-"
        div = f"{r['div']:.2f}" if r.get("div") else "-"
        print(
            f"{i:>2}  {r['sym']:<6} {r['price']:>9,.2f} {r['r6']:>+7.1f} {r['r1y']:>+7.1f}  "
            f"{'UP' if r['lt'] else 'dn':<4}{'UP' if r['mt'] else 'dn':<4}{r['rsi']:>4.0f}  "
            f"{pe:>6} {fmt_mcap(r.get('mcap')):>7} {div:>6}  {r['score']:>5}  {read_label(r['score'])}"
        )
    print("\nRanked best-first by trend alignment. LT=long-term(200d)  MT=mid-term(50d).\n")


if __name__ == "__main__":
    main()
