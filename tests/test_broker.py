"""Broker plumbing — everything testable without a live gateway."""

import pytest

import dewaag.broker as br
import dewaag.portfolio as pf


def test_default_config_is_local_simulator():
    cfg = br.load_broker_config()
    assert cfg["provider"] in ("paper_local", "ibkr")
    assert cfg["ibkr"]["port"] == 7497  # the PAPER port, never 7496


def test_contract_mapping_brussels_and_class_shares():
    spec = br.contract_spec("ABI")
    assert spec == {"symbol": "ABI", "exchange": "SMART",
                    "primaryExchange": "ENEXT.BE", "currency": "EUR"}
    assert br.contract_spec("BRK-B")["symbol"] == "BRK B"
    assert br.contract_spec("MSFT")["primaryExchange"] == "NASDAQ"
    with pytest.raises(ValueError):
        br.contract_spec("EURUSD")  # reference series are not tradable


def test_offline_gateway_refuses_orders_never_simulates(tmp_path, monkeypatch):
    """provider=ibkr + gateway down -> explicit refusal. Silent fallback to
    the simulator would mean not knowing which venue filled you."""
    monkeypatch.setattr(pf, "PORTFOLIO_PATH", tmp_path / "p.json")
    monkeypatch.setattr(pf, "_starting_cash", lambda: 10_000.0)
    monkeypatch.setattr(pf, "_last_close", lambda s: 100.0)
    monkeypatch.setattr(pf, "_eurusd", lambda: 1.0)

    import pandas as pd
    fake = pd.DataFrame([{"symbol": "TST", "yahoo": "TST", "name": "T", "exchange": "EBR",
                          "currency": "EUR", "country": "BE", "tier": "mega", "sector": "tech"}]
                        ).set_index("symbol", drop=False)
    monkeypatch.setattr(pf.store, "load_universe", lambda: fake)

    from dewaag.constitution import Constitution
    monkeypatch.setattr(pf, "load_constitution", lambda: Constitution(
        owner="T", signed_on="2026-07-10", max_risk_per_idea_pct=1.0, max_position_pct=10.0,
        max_drawdown_eur=1500, emergency_fund_months=6, leverage=0,
        require_thesis=True, min_years_before_strategy_change=5))

    import dewaag.broker as broker_mod
    monkeypatch.setattr(broker_mod, "load_broker_config",
                        lambda: {"provider": "ibkr", "ibkr": {"host": "127.0.0.1", "port": 7497, "client_id": 7}})
    monkeypatch.setattr(broker_mod, "gateway_available", lambda *a, **k: False)

    r = pf.execute("TST", "BUY", 5, thesis="a perfectly good thesis for testing venues", wrong_price=80.0)
    assert r["ok"] is False
    assert any("gateway is offline" in b for b in r["blocks"])
