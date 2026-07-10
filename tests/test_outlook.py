"""News + forward view — merge, dedup and cache logic, fully offline."""

import json

import pandas as pd

import dewaag.vault.forward as fwd
import dewaag.vault.news as news


def _fake_universe():
    return pd.DataFrame([{"symbol": "TST", "yahoo": "TST.BR", "name": "Test NV",
                          "exchange": "EBR", "currency": "EUR", "country": "BE",
                          "tier": "mid", "sector": "tech"}])


def test_news_merges_dedupes_and_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "NEWS_DIR", tmp_path)
    monkeypatch.setattr(news.store, "load_universe", _fake_universe)
    calls = {"n": 0}

    def yahoo(_):
        calls["n"] += 1
        return [{"title": "Test NV wins big contract", "when": "2026-07-09", "source": "Reuters", "link": "x"},
                {"title": "Old story", "when": "2026-07-01", "source": "Zacks", "link": "y"}]

    def google(_):
        return [{"title": "TEST NV WINS BIG CONTRACT", "when": "2026-07-09", "source": "De Tijd", "link": "z"},
                {"title": "Fresh Belgian angle", "when": "2026-07-10", "source": "De Tijd", "link": "w"}]

    monkeypatch.setattr(news, "_yahoo_news", yahoo)
    monkeypatch.setattr(news, "_google_news", google)

    items = news.get_news("TST")
    titles = [i["title"].lower() for i in items]
    assert len(items) == 3                     # duplicate headline collapsed
    assert titles[0] == "fresh belgian angle"  # newest first
    assert calls["n"] == 1

    # second call inside the cache window must not refetch
    assert len(news.get_news("TST")) == 3
    assert calls["n"] == 1
    # force bypasses the cache
    news.get_news("TST", force=True)
    assert calls["n"] == 2


def test_forward_computes_street_growth_and_survives_missing_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(fwd, "FWD_DIR", tmp_path)
    monkeypatch.setattr(fwd.store, "load_universe", _fake_universe)

    class FakeTicker:
        info = {"forwardEps": 5.5, "trailingEps": 5.0, "forwardPE": 18.0,
                "trailingPE": 20.0, "recommendationKey": "buy",
                "numberOfAnalystOpinions": 4, "targetMeanPrice": 110.0}
        analyst_price_targets = {"low": 90.0, "mean": 110.0, "high": 130.0}

    import sys
    import types
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=lambda _: FakeTicker()))

    out = fwd.get_forward("TST")
    assert out["available"] is True
    assert abs(out["street_eps_growth"] - 0.10) < 1e-9
    assert out["target_high"] == 130.0
    # cache round-trips as valid json
    assert json.loads((tmp_path / "TST.json").read_text(encoding="utf-8"))["target_low"] == 90.0

    # unknown symbol -> unavailable, never a crash
    assert fwd.get_forward("NOPE")["available"] is False
