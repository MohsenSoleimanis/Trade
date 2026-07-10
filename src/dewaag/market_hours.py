"""Market-hours awareness — so you always know if an order will fill.

Regular trading hours only; auctions and public holidays are a known
simplification (a US-holiday Monday will read 'open' here). Enough to
answer the two questions that matter before you click: is this tradeable
right now, and if not, when does it open?
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# exchange -> (timezone, open, close) in local market time
SESSIONS: dict[str, tuple[str, time, time]] = {
    "EBR": ("Europe/Brussels", time(9, 0), time(17, 30)),
    "AMS": ("Europe/Amsterdam", time(9, 0), time(17, 30)),
    "XETRA": ("Europe/Berlin", time(9, 0), time(17, 30)),
    "NASDAQ": ("America/New_York", time(9, 30), time(16, 0)),
    "NYSE": ("America/New_York", time(9, 30), time(16, 0)),
}


def _human(minutes: float) -> str:
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h {m}m"
    return f"{h}h" if h else f"{m}m"


def _next_open(now: datetime, open_t: time) -> datetime:
    cand = now.replace(hour=open_t.hour, minute=open_t.minute, second=0, microsecond=0)
    if cand <= now:
        cand += timedelta(days=1)
    while cand.weekday() >= 5:  # skip Saturday/Sunday
        cand += timedelta(days=1)
    return cand


def status(exchange: str) -> dict:
    tz_name, open_t, close_t = SESSIONS.get(exchange, SESSIONS["NYSE"])
    now = datetime.now(ZoneInfo(tz_name))
    is_open = now.weekday() < 5 and open_t <= now.time() < close_t
    if is_open:
        close_dt = now.replace(hour=close_t.hour, minute=close_t.minute, second=0, microsecond=0)
        mins = (close_dt - now).total_seconds() / 60
        label = f"open · closes in {_human(mins)}"
    else:
        nxt = _next_open(now, open_t)
        mins = (nxt - now).total_seconds() / 60
        label = f"closed · opens in {_human(mins)}"
    return {"exchange": exchange, "open": is_open, "minutes": int(mins), "label": label}
