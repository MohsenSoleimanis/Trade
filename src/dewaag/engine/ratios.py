"""Lesson 3's five-number toolkit, computed per year from the vault.

Every function here is pure: fundamentals frame in, numbers out.
The UI's why-drawers explain each number; this module only computes.
"""

from __future__ import annotations

import pandas as pd


def _wide(fund: pd.DataFrame) -> pd.DataFrame:
    """long (item, period_end, value) -> wide: one row per fiscal year."""
    if fund.empty:
        return pd.DataFrame()
    wide = fund.pivot_table(index="period_end", columns="item", values="value")
    return wide.sort_index()


def toolkit(fund: pd.DataFrame) -> dict:
    """The five numbers (plus raw ingredients) for each available year.

    Returns {"years": [ {period, revenue, rev_growth, net_margin, roe,
    debt_to_equity, cash_conversion, net_income, equity, shares}, ... ],
    "latest": <last year's dict>} — oldest first, so the UI can draw trends.
    """
    wide = _wide(fund)
    if wide.empty:
        return {"years": [], "latest": None}

    years: list[dict] = []
    prev_revenue = None
    for period, row in wide.iterrows():
        revenue = row.get("revenue")
        net_income = row.get("net_income")
        equity = row.get("equity")
        total_debt = row.get("total_debt")
        operating_cf = row.get("operating_cf")
        shares = row.get("shares")

        def ratio(a, b):
            if pd.isna(a) or pd.isna(b) or not b:
                return None
            return float(a) / float(b)

        year = {
            "period": str(pd.Timestamp(period).date()),
            "revenue": None if pd.isna(revenue) else float(revenue),
            "net_income": None if pd.isna(net_income) else float(net_income),
            "equity": None if pd.isna(equity) else float(equity),
            "shares": None if pd.isna(shares) else float(shares),
            # growth: this year vs previous (needs two years)
            "rev_growth": ratio(revenue - prev_revenue, prev_revenue)
            if prev_revenue and not pd.isna(revenue) else None,
            "net_margin": ratio(net_income, revenue),
            "roe": ratio(net_income, equity),
            "debt_to_equity": ratio(total_debt, equity),
            # profit is an opinion, cash is a fact — the lie detector:
            "cash_conversion": ratio(operating_cf, net_income),
        }
        years.append(year)
        prev_revenue = None if pd.isna(revenue) else float(revenue)

    return {"years": years, "latest": years[-1] if years else None}
