"""Engine tests — the numbers the UI shows must be provably right,
because a why-drawer explaining a wrong number teaches wrong lessons."""

import pandas as pd

from dewaag.engine.ratios import toolkit
from dewaag.engine.valuation import fair_value_per_share, snapshot


def fund_frame():
    rows = []
    for year, rev, ni, eq, debt, ocf, sh in [
        ("2023-12-31", 1000.0, 100.0, 500.0, 250.0, 110.0, 10.0),
        ("2024-12-31", 1100.0, 121.0, 550.0, 220.0, 130.0, 10.0),
    ]:
        for item, value in [("revenue", rev), ("net_income", ni), ("equity", eq),
                            ("total_debt", debt), ("operating_cf", ocf), ("shares", sh)]:
            rows.append({"symbol": "T", "item": item, "period_end": year,
                         "value": value, "source": "test", "ingested_at": "t"})
    return pd.DataFrame(rows)


def test_toolkit_five_numbers():
    tk = toolkit(fund_frame())
    latest = tk["latest"]
    assert round(latest["rev_growth"], 4) == 0.10          # 1000 -> 1100
    assert round(latest["net_margin"], 4) == 0.11          # 121 / 1100
    assert round(latest["roe"], 4) == 0.22                 # 121 / 550
    assert round(latest["debt_to_equity"], 4) == 0.40      # 220 / 550
    assert round(latest["cash_conversion"], 4) == round(130 / 121, 4)
    # first year has no previous year -> growth must be None, not 0
    assert tk["years"][0]["rev_growth"] is None


def test_valuation_decoder():
    # price 242, eps 12.1 -> P/E 20 -> implied growth = 8% - 1/20 = 3%
    s = snapshot(price=242.0, net_income=121.0, shares=10.0)
    assert round(s["eps"], 4) == 12.1
    assert round(s["pe"], 2) == 20.0
    assert round(s["implied_growth"], 4) == 0.03


def test_value_machine_matches_lesson_4():
    # Lesson 4: eps x (1+g) / (r-g); fair P/E at r=8%, g=3% is ~20
    v = fair_value_per_share(eps=10.0, rate=0.08, growth=0.03)
    assert round(v, 2) == round(10.0 * 1.03 / 0.05, 2)


def test_value_machine_refuses_broken_assumptions():
    # growth ~= rate -> no number, ever (infinity is not a price target)
    assert fair_value_per_share(eps=10.0, rate=0.08, growth=0.079) is None
    # negative earnings -> P/E and fair value are meaningless
    assert fair_value_per_share(eps=-5.0, rate=0.08, growth=0.03) is None
    s = snapshot(price=100.0, net_income=-50.0, shares=10.0)
    assert s["pe"] is None and s["implied_growth"] is None
