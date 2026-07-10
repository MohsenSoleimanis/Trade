#!/usr/bin/env python3
"""
analyze.py - connect to IBKR paper (TWS) and run long/mid-term analysis on a stock.

Usage:
    python analyze.py [SYMBOL]        # default: AAPL
    python analyze.py MSFT

Requirements:
    - TWS (IBKR Desktop) running and logged into the PAPER account.
    - API enabled on port 7497 (see the message shown if the connection fails).
    - pip install ib_async pandas numpy
"""

import sys
import pandas as pd
from ib_async import IB, Stock, util

HOST, PORT, CLIENT_ID = "127.0.0.1", 7497, 11


def connect() -> IB:
    ib = IB()
    try:
        ib.connect(HOST, PORT, clientId=CLIENT_ID, timeout=12, readonly=True)
    except Exception as e:
        sys.exit(
            f"\n  xCould not connect to TWS on {HOST}:{PORT}.\n\n"
            "  In TWS:  File -> Global Configuration -> API -> Settings:\n"
            "    -check 'Enable ActiveX and Socket Clients'\n"
            "    -Socket port = 7497   (paper trading)\n"
            "    -add 127.0.0.1 to 'Trusted IPs'\n"
            "  Then make sure you are logged into the PAPER account.\n\n"
            f"  ({e})\n"
        )
    return ib


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    return 100 - 100 / (1 + gain / loss)


def main() -> None:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "AAPL").upper()
    ib = connect()

    # Delayed data works without a real-time market-data subscription.
    ib.reqMarketDataType(3)

    contract = Stock(symbol, "SMART", "USD")
    if not ib.qualifyContracts(contract):
        ib.disconnect()
        sys.exit(f"  xSymbol {symbol} not recognized by IBKR.")

    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr="2 Y",
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
    )
    if not bars:
        ib.disconnect()
        sys.exit(f"  xNo historical data returned for {symbol} (data permissions?).")

    df = util.df(bars)
    df["sma20"] = df.close.rolling(20).mean()
    df["sma50"] = df.close.rolling(50).mean()
    df["sma200"] = df.close.rolling(200).mean()
    df["rsi14"] = rsi(df.close)
    ema12 = df.close.ewm(span=12, adjust=False).mean()
    ema26 = df.close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    last = df.iloc[-1]
    price = last.close
    hi52 = df.close.tail(252).max()
    lo52 = df.close.tail(252).min()

    def ret(days: int) -> float:
        return (price / df.close.iloc[-1 - days] - 1) * 100 if len(df) > days else float("nan")

    # --- account (proves the live connection) ---
    acct = ib.accountSummary()
    netliq = next((a.value for a in acct if a.tag == "NetLiquidation"), "?")

    # --- trend reads ---
    lt_up = price > last.sma200
    golden = last.sma50 > last.sma200
    mt_up = price > last.sma50
    macd_bull = last.macd > last.macd_signal

    print(f"\n=== {symbol}  -  {last.date}  (paper acct net liq: {netliq}) ===\n")
    print(f"Price ${price:,.2f}   |   52-week ${lo52:,.2f} - ${hi52:,.2f}   "
          f"({(price / hi52 - 1) * 100:+.1f}% from high)")
    print(f"\nReturns   1M {ret(21):+5.1f}%   3M {ret(63):+5.1f}%   "
          f"6M {ret(126):+5.1f}%   1Y {ret(252):+5.1f}%\n")

    print(f"LONG-TERM (200d)   trend {'UP  ' if lt_up else 'DOWN'}   "
          f"{'golden cross (50>200)' if golden else 'death cross (50<200)'}   "
          f"SMA200 ${last.sma200:,.2f}")
    print(f"MID-TERM  (50d)    trend {'UP  ' if mt_up else 'DOWN'}   "
          f"MACD {'bullish' if macd_bull else 'bearish'}   "
          f"SMA50 ${last.sma50:,.2f}  SMA20 ${last.sma20:,.2f}")
    print(f"MOMENTUM           RSI(14) {last.rsi14:.0f}  "
          f"{'(overbought)' if last.rsi14 > 70 else '(oversold)' if last.rsi14 < 30 else ''}")

    # --- plain-English verdict ---
    if lt_up and golden and mt_up and macd_bull:
        verdict = "Aligned uptrend - long and mid-term both bullish."
    elif not lt_up and not mt_up:
        verdict = "Aligned downtrend - long and mid-term both bearish."
    elif lt_up and not mt_up:
        verdict = "Long-term up but mid-term pulling back - a dip within an uptrend."
    elif not lt_up and mt_up:
        verdict = "Long-term down but bouncing mid-term - possible relief rally, not confirmed."
    else:
        verdict = "Mixed signals - no clear trend alignment."
    print(f"\nVERDICT  {verdict}\n")

    ib.disconnect()


if __name__ == "__main__":
    main()
