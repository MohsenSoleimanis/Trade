"""Trading gates and sizing — the laws must hold under fire.

These tests use a signed test constitution and a monkeypatched market,
so they run offline and never touch the real portfolio file.
"""

import pytest

import dewaag.portfolio as pf
from dewaag.constitution import Constitution
from dewaag.engine.sizing import backwards_size, gate_order


def signed(**over):
    base = dict(owner="T", signed_on="2026-07-09", max_risk_per_idea_pct=1.0,
                max_position_pct=10.0, max_drawdown_eur=1500,
                emergency_fund_months=6, leverage=0, require_thesis=True,
                min_years_before_strategy_change=5)
    base.update(over)
    return Constitution(**base)


def test_backwards_sizing_lesson_6_example():
    # €10k portfolio, 1.5% risk, entry €50, wrong at €40 -> 15 shares, €750
    r = backwards_size(10_000, 1.5, entry=50, wrong_price=40)
    assert r["shares"] == 15
    assert r["investment"] == 750.0
    assert r["worst_case_loss"] == 150.0


def test_sizing_rejects_wrong_above_entry():
    r = backwards_size(10_000, 1.0, entry=50, wrong_price=60)
    assert r["ok"] is False


def test_unsigned_constitution_locks_the_desk():
    c = signed(max_drawdown_eur=0)  # undecided euros = unsigned (Lesson 6 trap #1)
    blocks = gate_order(c, portfolio_value=10_000, position_value_after=500,
                        shares=10, entry=50, wrong_price=40, thesis="x" * 30, side="BUY")
    assert any("UNSIGNED" in b for b in blocks)


def test_gates_block_oversized_risk_and_position():
    c = signed()
    # risk: 100 shares x €10 loss = €1,000 >> 1% of €10k (€100)
    blocks = gate_order(c, portfolio_value=10_000, position_value_after=5_000,
                        shares=100, entry=50, wrong_price=40, thesis="x" * 30, side="BUY")
    assert any("budget" in b for b in blocks)
    assert any("cap" in b for b in blocks)  # €5,000 > 10% of €10k


def test_gates_require_thesis_but_never_block_sells():
    c = signed()
    blocks = gate_order(c, portfolio_value=10_000, position_value_after=500,
                        shares=10, entry=50, wrong_price=40, thesis="", side="BUY")
    assert any("thesis" in b for b in blocks)
    assert gate_order(c, portfolio_value=10_000, position_value_after=0,
                      shares=10, entry=50, wrong_price=None, thesis="", side="SELL") == []


def test_paper_execute_roundtrip(tmp_path, monkeypatch):
    """BUY then SELL through the local paper broker: cash falls by costs,
    the position appears and disappears, the journal remembers the thesis."""
    monkeypatch.setattr(pf, "PORTFOLIO_PATH", tmp_path / "portfolio.json")
    monkeypatch.setattr(pf, "_starting_cash", lambda: 10_000.0)
    monkeypatch.setattr(pf, "_last_close", lambda s: 100.0)
    monkeypatch.setattr(pf, "_eurusd", lambda: 1.0)

    import pandas as pd
    fake_universe = pd.DataFrame(
        [{"symbol": "TST", "yahoo": "TST", "name": "Test Co", "exchange": "EBR",
          "currency": "EUR", "country": "BE", "tier": "mega"}]).set_index("symbol", drop=False)
    monkeypatch.setattr(pf.store, "load_universe", lambda: fake_universe)
    monkeypatch.setattr(pf, "load_constitution", lambda: signed())
    # pin the venue to the local simulator so the unit test never reaches TWS
    import dewaag.broker as broker_mod
    monkeypatch.setattr(broker_mod, "load_broker_config",
                        lambda: {"provider": "paper_local", "ibkr": {"host": "127.0.0.1", "port": 7497, "client_id": 7}})

    r = pf.execute("TST", "BUY", 5, thesis="testing the machine end to end, long enough", wrong_price=80.0)
    assert r["ok"], r.get("blocks")
    assert r["portfolio"]["positions"][0]["shares"] == 5
    assert r["portfolio"]["cash"] < 10_000 - 5 * 100  # price + costs

    r2 = pf.execute("TST", "SELL", 5)
    assert r2["ok"]
    assert r2["portfolio"]["positions"] == []
    assert len(r2["portfolio"]["trades"]) == 2
    assert "testing the machine" in r2["portfolio"]["trades"][0]["thesis"]


def test_no_cash_no_leverage(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "PORTFOLIO_PATH", tmp_path / "portfolio.json")
    monkeypatch.setattr(pf, "_starting_cash", lambda: 10_000.0)
    monkeypatch.setattr(pf, "_last_close", lambda s: 5_000.0)
    monkeypatch.setattr(pf, "_eurusd", lambda: 1.0)
    import pandas as pd
    fake_universe = pd.DataFrame(
        [{"symbol": "TST", "yahoo": "TST", "name": "Test Co", "exchange": "EBR",
          "currency": "EUR", "country": "BE", "tier": "mega"}]).set_index("symbol", drop=False)
    monkeypatch.setattr(pf.store, "load_universe", lambda: fake_universe)
    monkeypatch.setattr(pf, "load_constitution", lambda: signed(max_position_pct=10.0))

    # 3 x €5,000 = €15,000 > €10,000 cash -> blocked (and also over the cap)
    r = pf.execute("TST", "BUY", 3, thesis="x" * 30, wrong_price=4000.0)
    assert r["ok"] is False
    assert any("cash" in b or "cap" in b for b in r["blocks"])


def test_etf_core_exempt_from_stock_cap_but_stocks_are_not():
    """§2 caps single-company risk; a 1,500-company basket is the
    diversification itself. ETFs get a 60% core ceiling instead."""
    c = signed()
    stock_blocks = gate_order(c, portfolio_value=10_000, position_value_after=3_000,
                              shares=10, entry=300, wrong_price=270, thesis="x" * 30,
                              side="BUY", tier="mega")
    assert any("cap" in b for b in stock_blocks)
    etf_blocks = gate_order(c, portfolio_value=10_000, position_value_after=3_000,
                            shares=25, entry=120, wrong_price=108, thesis="core holding " * 3,
                            side="BUY", tier="etf")
    assert not any("cap" in b for b in etf_blocks)
