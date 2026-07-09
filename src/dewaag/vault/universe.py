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
    ("AAPL",  "AAPL",    "Apple",               "NASDAQ", "USD", "US", "mega"),
    ("MSFT",  "MSFT",    "Microsoft",           "NASDAQ", "USD", "US", "mega"),
    ("NVDA",  "NVDA",    "NVIDIA",              "NASDAQ", "USD", "US", "mega"),
    ("GOOGL", "GOOGL",   "Alphabet",            "NASDAQ", "USD", "US", "mega"),
    ("AMZN",  "AMZN",    "Amazon",              "NASDAQ", "USD", "US", "mega"),
    ("META",  "META",    "Meta Platforms",      "NASDAQ", "USD", "US", "mega"),
    ("BRK-B", "BRK-B",   "Berkshire Hathaway",  "NYSE",   "USD", "US", "mega"),
    ("JPM",   "JPM",     "JPMorgan Chase",      "NYSE",   "USD", "US", "mega"),
    ("JNJ",   "JNJ",     "Johnson & Johnson",   "NYSE",   "USD", "US", "mega"),
    ("PG",    "PG",      "Procter & Gamble",    "NYSE",   "USD", "US", "mega"),
    ("KO",    "KO",      "Coca-Cola",           "NYSE",   "USD", "US", "mega"),
    ("PEP",   "PEP",     "PepsiCo",             "NASDAQ", "USD", "US", "mega"),
    ("XOM",   "XOM",     "Exxon Mobil",         "NYSE",   "USD", "US", "mega"),
    ("CVX",   "CVX",     "Chevron",             "NYSE",   "USD", "US", "mega"),
    ("UNH",   "UNH",     "UnitedHealth",        "NYSE",   "USD", "US", "mega"),
    ("V",     "V",       "Visa",                "NYSE",   "USD", "US", "mega"),
    ("MA",    "MA",      "Mastercard",          "NYSE",   "USD", "US", "mega"),
    ("HD",    "HD",      "Home Depot",          "NYSE",   "USD", "US", "mega"),
    ("MCD",   "MCD",     "McDonald's",          "NYSE",   "USD", "US", "mega"),
    ("WMT",   "WMT",     "Walmart",             "NYSE",   "USD", "US", "mega"),
    ("DIS",   "DIS",     "Walt Disney",         "NYSE",   "USD", "US", "large"),
    ("CSCO",  "CSCO",    "Cisco",               "NASDAQ", "USD", "US", "large"),
    ("IBM",   "IBM",     "IBM",                 "NYSE",   "USD", "US", "large"),
    ("CAT",   "CAT",     "Caterpillar",         "NYSE",   "USD", "US", "large"),
    ("MMM",   "MMM",     "3M",                  "NYSE",   "USD", "US", "large"),
    # --- Euronext Brussels (BEL 20 & friends — Book B home turf) ---
    ("ABI",   "ABI.BR",  "AB InBev",            "EBR", "EUR", "BE", "large"),
    ("KBC",   "KBC.BR",  "KBC Group",           "EBR", "EUR", "BE", "large"),
    ("UCB",   "UCB.BR",  "UCB",                 "EBR", "EUR", "BE", "large"),
    ("SOLB",  "SOLB.BR", "Solvay",              "EBR", "EUR", "BE", "mid"),
    ("UMI",   "UMI.BR",  "Umicore",             "EBR", "EUR", "BE", "mid"),
    ("ACKB",  "ACKB.BR", "Ackermans & v.Haaren","EBR", "EUR", "BE", "mid"),
    ("GBLB",  "GBLB.BR", "GBL",                 "EBR", "EUR", "BE", "mid"),
    ("COLR",  "COLR.BR", "Colruyt",             "EBR", "EUR", "BE", "mid"),
    ("PROX",  "PROX.BR", "Proximus",            "EBR", "EUR", "BE", "mid"),
    ("SOF",   "SOF.BR",  "Sofina",              "EBR", "EUR", "BE", "mid"),
    ("ELI",   "ELI.BR",  "Elia Group",          "EBR", "EUR", "BE", "mid"),
    ("AGS",   "AGS.BR",  "Ageas",               "EBR", "EUR", "BE", "mid"),
    ("DIE",   "DIE.BR",  "D'Ieteren",           "EBR", "EUR", "BE", "mid"),
    ("LOTB",  "LOTB.BR", "Lotus Bakeries",      "EBR", "EUR", "BE", "mid"),
    ("MELE",  "MELE.BR", "Melexis",             "EBR", "EUR", "BE", "mid"),
    ("BAR",   "BAR.BR",  "Barco",               "EBR", "EUR", "BE", "small"),
    ("KIN",   "KIN.BR",  "Kinepolis",           "EBR", "EUR", "BE", "small"),
    ("BEKB",  "BEKB.BR", "Bekaert",             "EBR", "EUR", "BE", "small"),
    ("TESB",  "TESB.BR", "Tessenderlo",         "EBR", "EUR", "BE", "small"),
    # --- The benchmark (Lesson 1: the score to beat) ---
    ("IWDA",  "IWDA.AS", "iShares MSCI World (acc)", "AMS", "EUR", "IE", "etf"),
]

COLUMNS = ["symbol", "yahoo", "name", "exchange", "currency", "country", "tier"]


def build_universe() -> pd.DataFrame:
    df = pd.DataFrame(SEED, columns=COLUMNS)
    if df["symbol"].duplicated().any():
        raise ValueError("Universe integrity: duplicate symbols in seed list.")
    return df
