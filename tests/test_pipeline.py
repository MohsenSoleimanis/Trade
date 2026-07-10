"""The process spine's rules are law — tested like the constitution."""

import pytest

import dewaag.pipeline as pl


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(pl, "PIPELINE_PATH", tmp_path / "pipeline.json")


def test_card_travels_the_happy_path():
    c = pl.add_card("LOTB", source="screener")
    assert c["stage"] == "INBOX"
    c = pl.advance(c["id"])                       # -> TRIAGE
    c = pl.advance(c["id"])                       # -> DIVE
    c = pl.advance(c["id"], thesis="quality compounder, cash conversion 1.2, priced fairly at last",
                   wrong_price=9000.0)            # -> DECISION
    assert c["stage"] == "DECISION"
    assert len(c["history"]) == 4


def test_decision_door_demands_thesis_and_exit():
    c = pl.add_card("MELE")
    pl.advance(c["id"]); pl.advance(c["id"])      # -> DIVE
    with pytest.raises(ValueError, match="thesis"):
        pl.advance(c["id"])                       # no thesis -> blocked
    with pytest.raises(ValueError, match="wrong at"):
        pl.advance(c["id"], thesis="a long enough thesis about why this is a buy")


def test_no_duplicate_open_cards():
    pl.add_card("KIN")
    with pytest.raises(ValueError, match="already"):
        pl.add_card("KIN")


def test_pass_needs_a_reason_and_is_terminal():
    c = pl.add_card("ABI")
    with pytest.raises(ValueError):
        pl.pass_card(c["id"], "no")
    c = pl.pass_card(c["id"], "value-trap shape: cheap but margins deteriorating")
    assert c["stage"] == "PASSED"
    # a passed card frees the symbol for a future idea
    pl.add_card("ABI")


def test_trades_move_cards_and_open_post_mortems():
    c = pl.add_card("BAR")
    pl.advance(c["id"]); pl.advance(c["id"])
    pl.advance(c["id"], thesis="event: undervalued on divestment news, market asleep", wrong_price=10.0)
    pl.on_trade("BAR", "BUY", position_remaining=10)
    assert pl.load()[0]["stage"] == "LIVE"
    pl.on_trade("BAR", "SELL", position_remaining=0)
    assert pl.load()[0]["stage"] == "CLOSED"
    tasks = pl.tasks()
    assert any(t["kind"] == "post_mortem" for t in tasks)
    pl.grade(pl.load()[0]["id"], "thesis_right", "exit hit target")
    assert not any(t["kind"] == "post_mortem" for t in pl.tasks())


def test_grades_are_from_the_honest_vocabulary():
    c = pl.add_card("TESB")
    pl.on_trade("TESB", "BUY", 5)
    pl.on_trade("TESB", "SELL", 0)
    with pytest.raises(ValueError):
        pl.grade(c["id"], "genius")   # not an option. lucky is an option.
