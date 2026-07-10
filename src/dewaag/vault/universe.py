"""Layer 0 — the universe: what exists, where it trades, how liquid it is.

Why a curated seed list instead of 'everything'? Because Lesson 2 taught
that liquidity decides how you may trade a name. The `tier` column encodes
that: the Risk Console will later cap position sizes and force limit orders
based on it. Small starter universe = every row is a name we can reason about.
"""

from __future__ import annotations

import pandas as pd

# symbol, yahoo ticker, name, exchange, currency, country, tier
# tiers: mega (trade freely) > large > mid (limit orders) > small (limit orders,
# tiny sizes, auction-aware) > etf (the benchmark & core holdings)
SEED = [
    # --- US mega/large caps (Book A training ground) ---
    ("AAPL",  "AAPL",    "Apple",               "NASDAQ", "USD", "US", "mega", "tech"),
    ("MSFT",  "MSFT",    "Microsoft",           "NASDAQ", "USD", "US", "mega", "tech"),
    ("NVDA",  "NVDA",    "NVIDIA",              "NASDAQ", "USD", "US", "mega", "tech"),
    ("GOOGL", "GOOGL",   "Alphabet",            "NASDAQ", "USD", "US", "mega", "tech"),
    ("AMZN",  "AMZN",    "Amazon",              "NASDAQ", "USD", "US", "mega", "consumer"),
    ("META",  "META",    "Meta Platforms",      "NASDAQ", "USD", "US", "mega", "tech"),
    ("BRK-B", "BRK-B",   "Berkshire Hathaway",  "NYSE",   "USD", "US", "mega", "financials"),
    ("JPM",   "JPM",     "JPMorgan Chase",      "NYSE",   "USD", "US", "mega", "financials"),
    ("JNJ",   "JNJ",     "Johnson & Johnson",   "NYSE",   "USD", "US", "mega", "healthcare"),
    ("PG",    "PG",      "Procter & Gamble",    "NYSE",   "USD", "US", "mega", "staples"),
    ("KO",    "KO",      "Coca-Cola",           "NYSE",   "USD", "US", "mega", "staples"),
    ("PEP",   "PEP",     "PepsiCo",             "NASDAQ", "USD", "US", "mega", "staples"),
    ("XOM",   "XOM",     "Exxon Mobil",         "NYSE",   "USD", "US", "mega", "energy"),
    ("CVX",   "CVX",     "Chevron",             "NYSE",   "USD", "US", "mega", "energy"),
    ("UNH",   "UNH",     "UnitedHealth",        "NYSE",   "USD", "US", "mega", "healthcare"),
    ("V",     "V",       "Visa",                "NYSE",   "USD", "US", "mega", "financials"),
    ("MA",    "MA",      "Mastercard",          "NYSE",   "USD", "US", "mega", "financials"),
    ("HD",    "HD",      "Home Depot",          "NYSE",   "USD", "US", "mega", "consumer"),
    ("MCD",   "MCD",     "McDonald's",          "NYSE",   "USD", "US", "mega", "consumer"),
    ("WMT",   "WMT",     "Walmart",             "NYSE",   "USD", "US", "mega", "staples"),
    ("DIS",   "DIS",     "Walt Disney",         "NYSE",   "USD", "US", "large", "media"),
    ("CSCO",  "CSCO",    "Cisco",               "NASDAQ", "USD", "US", "large", "tech"),
    ("IBM",   "IBM",     "IBM",                 "NYSE",   "USD", "US", "large", "tech"),
    ("CAT",   "CAT",     "Caterpillar",         "NYSE",   "USD", "US", "large", "industrials"),
    ("MMM",   "MMM",     "3M",                  "NYSE",   "USD", "US", "large", "industrials"),
    # --- Euronext Brussels (BEL 20 & friends — Book B home turf) ---
    ("ABI",   "ABI.BR",  "AB InBev",            "EBR", "EUR", "BE", "large", "staples"),
    ("KBC",   "KBC.BR",  "KBC Group",           "EBR", "EUR", "BE", "large", "financials"),
    ("UCB",   "UCB.BR",  "UCB",                 "EBR", "EUR", "BE", "large", "healthcare"),
    ("SOLB",  "SOLB.BR", "Solvay",              "EBR", "EUR", "BE", "mid", "materials"),
    ("UMI",   "UMI.BR",  "Umicore",             "EBR", "EUR", "BE", "mid", "materials"),
    ("ACKB",  "ACKB.BR", "Ackermans & v.Haaren","EBR", "EUR", "BE", "mid", "holding"),
    ("GBLB",  "GBLB.BR", "GBL",                 "EBR", "EUR", "BE", "mid", "holding"),
    ("COLR",  "COLR.BR", "Colruyt",             "EBR", "EUR", "BE", "mid", "staples"),
    ("PROX",  "PROX.BR", "Proximus",            "EBR", "EUR", "BE", "mid", "telecom"),
    ("SOF",   "SOF.BR",  "Sofina",              "EBR", "EUR", "BE", "mid", "holding"),
    ("ELI",   "ELI.BR",  "Elia Group",          "EBR", "EUR", "BE", "mid", "utilities"),
    ("AGS",   "AGS.BR",  "Ageas",               "EBR", "EUR", "BE", "mid", "financials"),
    ("DIE",   "DIE.BR",  "D'Ieteren",           "EBR", "EUR", "BE", "mid", "consumer"),
    ("LOTB",  "LOTB.BR", "Lotus Bakeries",      "EBR", "EUR", "BE", "mid", "staples"),
    ("MELE",  "MELE.BR", "Melexis",             "EBR", "EUR", "BE", "mid", "tech"),
    ("BAR",   "BAR.BR",  "Barco",               "EBR", "EUR", "BE", "small", "tech"),
    ("KIN",   "KIN.BR",  "Kinepolis",           "EBR", "EUR", "BE", "small", "media"),
    ("BEKB",  "BEKB.BR", "Bekaert",             "EBR", "EUR", "BE", "small", "industrials"),
    ("TESB",  "TESB.BR", "Tessenderlo",         "EBR", "EUR", "BE", "small", "materials"),
    # --- The benchmark (Lesson 1: the score to beat) ---
    ("IWDA",  "IWDA.AS", "iShares MSCI World (acc)", "AMS", "EUR", "IE", "etf", "etf"),
    ("WEBN",  "WEBN.DE", "Amundi Prime All-Country World (acc)", "XETRA", "EUR", "IE", "etf", "etf"),
    # --- FX: the double bet must be priced, not ignored (Lesson 2 §6) ---
    ("EURUSD", "EURUSD=X", "EUR/USD", "FX", "USD", "FX", "fx", "fx"),
    # --- Macro channels: war/climate/rates reach a company THROUGH these
    #     traded prices. We don't forecast shocks — we measure exposure to
    #     the channels that transmit them. Never tradable here. ---
    ("VIX",   "^VIX", "VIX — market fear index",          "MACRO", "USD", "US",    "macro", "macro"),
    ("BRENT", "BZ=F", "Brent crude — energy/war channel", "MACRO", "USD", "WORLD", "macro", "macro"),
    ("GOLD",  "GC=F", "Gold — crisis-hedge channel",      "MACRO", "USD", "WORLD", "macro", "macro"),
    ("US10Y", "^TNX", "US 10y yield — rates channel",     "MACRO", "USD", "US",    "macro", "macro"),
]

COLUMNS = ["symbol", "yahoo", "name", "exchange", "currency", "country", "tier", "sector"]


def build_universe() -> pd.DataFrame:
    df = pd.DataFrame(SEED, columns=COLUMNS)
    if df["symbol"].duplicated().any():
        raise ValueError("Universe integrity: duplicate symbols in seed list.")
    return df
