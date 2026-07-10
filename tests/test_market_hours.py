"""Market-hours logic — provable without waiting for a bell."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from dewaag import market_hours as mh


def test_known_exchanges_have_sessions():
    for ex in ("EBR", "NYSE", "NASDAQ", "AMS"):
        st = mh.status(ex)
        assert "open" in st and "label" in st
        assert st["minutes"] >= 0


def test_next_open_skips_weekend():
    # a Saturday noon in Brussels -> next open is Monday 09:00
    sat = datetime(2026, 7, 11, 12, 0, tzinfo=ZoneInfo("Europe/Brussels"))
    nxt = mh._next_open(sat, time(9, 0))
    assert nxt.weekday() == 0  # Monday
    assert nxt.hour == 9


def test_human_readable():
    assert mh._human(90) == "1h 30m"
    assert mh._human(45) == "45m"
    assert mh._human(120) == "2h"
