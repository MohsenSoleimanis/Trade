"""The backtest engine's honesty properties, proven.

The most important test in this whole repo is the no-lookahead test:
if changing FUTURE prices changes TODAY's selection, every backtest
result the lab ever shows is a lie.
"""

import numpy as np
import pandas as pd

from dewaag.engine.backtest import momentum_12_1, run, side_cost_pct


def make_panel(n_months=40, symbols=("AAA", "BBB", "CCC", "DDD")):
    idx = pd.date_range("2015-01-31", periods=n_months, freq="ME")
    data = {}
    for k, s in enumerate(symbols):
        drift = 0.002 * (k + 1)  # DDD strongest, AAA weakest
        data[s] = [100 * (1 + drift) ** i for i in range(n_months)]
    return pd.DataFrame(data, index=idx)


TIERS = {"AAA": "mega", "BBB": "mega", "CCC": "mega", "DDD": "mega"}


def test_momentum_picks_the_strongest():
    panel = make_panel()
    sig = momentum_12_1(panel, 20)
    assert sig.idxmax() == "DDD"
    assert sig.idxmin() == "AAA"


def test_no_lookahead():
    """Selection at month i must not change when the future changes."""
    panel_a = make_panel()
    panel_b = panel_a.copy()
    panel_b.iloc[25:] = panel_b.iloc[25:] * 37.0  # violently different future
    i = 20
    sig_a = momentum_12_1(panel_a, i)
    sig_b = momentum_12_1(panel_b, i)
    pd.testing.assert_series_equal(sig_a, sig_b)


def test_costs_make_net_below_gross():
    panel = make_panel()
    r = run(panel, TIERS, top_n=2)
    assert r["net"][-1] < r["gross"][-1]
    assert r["stats"]["total_cost_drag"] > 0


def test_stats_sane_on_rising_market():
    panel = make_panel()
    r = run(panel, TIERS, top_n=2)
    assert r["stats"]["net"]["cagr"] > 0
    assert r["stats"]["net"]["max_dd"] <= 0
    assert len(r["dates"]) == len(r["net"])


def test_small_positions_pay_proportionally_more():
    # €3 commission on a €500 slice hurts far more than on €5,000
    assert side_cost_pct("mega", 500.0) > side_cost_pct("mega", 5_000.0)


def test_survivorship_warning_travels_with_results():
    panel = make_panel()
    r = run(panel, TIERS, top_n=2)
    assert any("SURVIVORSHIP" in w for w in r["warnings"])


def test_missing_history_symbols_are_excluded_not_guessed():
    panel = make_panel()
    panel.loc[panel.index[:15], "CCC"] = np.nan  # CCC lists late
    r = run(panel, TIERS, top_n=4)  # must not crash, must not invent data
    assert r["net"][-1] > 0
