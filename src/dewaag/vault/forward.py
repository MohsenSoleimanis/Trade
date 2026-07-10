"""The forward view — what the street expects NEXT, not what happened.

Free analyst data per name: forward EPS and P/E, consensus price targets
(low/mean/high), recommendation, coverage count. Cached daily.

How to read it honestly (Lesson 1 applies twice):
  * Analyst consensus IS the market's expectation — it's largely already
    in the price. Its use is context: what growth is being promised, and
    how crowded/covered is the name (a Belgian small cap with 2 analysts
    is exactly the under-fished water Book B likes).
  * Price targets are notoriously optimistic on average. The spread
    (low vs high) is often more informative than the mean.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from dewaag.vault import store

FWD_DIR = store.DATA_DIR / "forward"
CACHE_HOURS = 20


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def get_forward(symbol: str, force: bool = False) -> dict:
    FWD_DIR.mkdir(parents=True, exist_ok=True)
    cache = FWD_DIR / f"{symbol}.json"
    if cache.exists() and not force:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        if time.time() - payload.get("fetched_ts", 0) < CACHE_HOURS * 3600:
            return payload

    import yfinance as yf

    u = store.load_universe().set_index("symbol")
    if symbol not in u.index:
        return {"available": False}
    t = yf.Ticker(str(u.loc[symbol, "yahoo"]))

    info = {}
    try:
        info = t.info or {}
    except Exception:  # noqa: BLE001
        pass
    targets = {}
    try:
        targets = t.analyst_price_targets or {}
    except Exception:  # noqa: BLE001
        pass

    out = {
        "available": True,
        "fetched_ts": time.time(),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "forward_eps": _f(info.get("forwardEps")),
        "trailing_eps": _f(info.get("trailingEps")),
        "forward_pe": _f(info.get("forwardPE")),
        "trailing_pe": _f(info.get("trailingPE")),
        "target_low": _f(targets.get("low")) or _f(info.get("targetLowPrice")),
        "target_mean": _f(targets.get("mean")) or _f(info.get("targetMeanPrice")),
        "target_high": _f(targets.get("high")) or _f(info.get("targetHighPrice")),
        "recommendation": info.get("recommendationKey"),
        "analysts": info.get("numberOfAnalystOpinions"),
    }
    # the street's implied EPS growth: forward vs trailing
    if out["forward_eps"] and out["trailing_eps"] and out["trailing_eps"] > 0:
        out["street_eps_growth"] = round(out["forward_eps"] / out["trailing_eps"] - 1, 4)
    else:
        out["street_eps_growth"] = None

    cache.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
