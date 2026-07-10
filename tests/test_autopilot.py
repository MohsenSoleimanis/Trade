"""Autopilot must obey the constitution and narrate honestly."""

import dewaag.autopilot as ap


def test_config_defaults_safe():
    cfg = ap.load_config()
    assert cfg["full_auto"] is False          # never auto by default
    assert cfg["target_holdings"] >= 1
    assert 0.10 <= cfg["exit_pct"] <= 0.40


def test_run_auto_refuses_when_full_auto_off(monkeypatch):
    monkeypatch.setattr(ap, "load_config", lambda: {"full_auto": False, "target_holdings": 5, "max_new_per_cycle": 1, "exit_pct": 0.2})
    r = ap.run_auto()
    assert r["ran"] is False
    assert "full_auto is off" in r["reason"]


def test_narration_explains_scores_in_words():
    assert "top third" in ap._explain_quality(80)
    assert "bottom third" in ap._explain_quality(10)
    assert "cheaper" in ap._explain_value(80)
    assert "punishing" in ap._explain_momentum(10)
    assert "rewarding" in ap._explain_momentum(90)


def test_plan_runs_against_the_real_vault_and_narrates():
    """Smoke test on the real vault: a signed constitution yields a plan whose
    every action carries a plain-language narration and an armed exit."""
    plan = ap.generate_plan()
    assert "intro" in plan and len(plan["intro"]) >= 1
    for act in plan["sells"] + plan["buys"]:
        assert act["narration"] and all(isinstance(s, str) for s in act["narration"])
        assert act["action"] in ("BUY", "SELL")
        if act["action"] == "BUY":
            assert act["wrong_price"] and act["wrong_price"] < act["entry"]  # exit always below entry
            assert act["shares"] >= 1
