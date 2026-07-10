"""News per company — the system's eyes on the present.

Two free sources, merged and deduplicated:
  * Yahoo Finance ticker news (good US coverage)
  * Google News RSS search (crucial for Belgian names — picks up Dutch,
    French and English coverage the US feeds never see)

Honesty note (Lesson 1): news you can read is already in the price.
Its value here is CONTEXT — for you and for the agent briefs — never a
trading signal by itself. The agent's job is interpretation: does this
change the thesis, the exit, or nothing?
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from dewaag.vault import store

NEWS_DIR = store.DATA_DIR / "news"
CACHE_MINUTES = 30


def _yahoo_news(yahoo_symbol: str) -> list[dict]:
    import yfinance as yf

    out = []
    try:
        for item in (yf.Ticker(yahoo_symbol).news or [])[:12]:
            content = item.get("content", item)  # yfinance schema drift
            title = content.get("title")
            if not title:
                continue
            ts = content.get("pubDate") or content.get("providerPublishTime")
            when = str(ts)[:10] if ts else None
            link = (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else content.get("link")
            publisher = (content.get("provider") or {}).get("displayName") if isinstance(content.get("provider"), dict) else content.get("publisher")
            out.append({"title": str(title), "when": when,
                        "source": str(publisher or "yahoo"), "link": link})
    except Exception:  # noqa: BLE001 — a dead feed must never break the page
        pass
    return out


def _google_news(query: str) -> list[dict]:
    import urllib.parse
    import urllib.request

    url = ("https://news.google.com/rss/search?q="
           + urllib.parse.quote(query) + "&hl=en&gl=BE&ceid=BE:en")
    out = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DeWaag/0.1 research"})
        with urllib.request.urlopen(req, timeout=8) as r:
            root = ET.fromstring(r.read())
        for item in root.iter("item"):
            title = item.findtext("title")
            if not title:
                continue
            pub = item.findtext("pubDate") or ""
            try:
                when = datetime.strptime(pub[:16], "%a, %d %b %Y").date().isoformat()
            except ValueError:
                when = None
            out.append({"title": title, "when": when,
                        "source": (item.findtext("source") or "google news"),
                        "link": item.findtext("link")})
            if len(out) >= 10:
                break
    except Exception:  # noqa: BLE001
        pass
    return out


MACRO_QUERIES = [
    "markets geopolitics war impact",
    "ECB federal reserve interest rates",
    "oil energy prices economy",
    "climate policy economic impact",
]


def get_macro_news(force: bool = False) -> list[dict]:
    """The WORLD wire — war, central banks, energy, climate. Same honesty
    rule as company news, doubled: by the time you read a macro headline,
    every price on your screen has already voted on it. This wire exists
    so you are never SURPRISED, not so you trade it."""
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    cache = NEWS_DIR / "_MACRO.json"
    if cache.exists() and not force:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        if time.time() - payload["fetched_ts"] < CACHE_MINUTES * 60:
            return payload["items"]

    items: list[dict] = []
    for q in MACRO_QUERIES:
        items.extend(_google_news(q)[:4])
    seen, merged = set(), []
    for it in items:
        key = it["title"].lower()[:70]
        if key in seen:
            continue
        seen.add(key)
        merged.append(it)
    merged.sort(key=lambda x: x["when"] or "", reverse=True)
    merged = merged[:12]

    cache.write_text(json.dumps({
        "fetched_ts": time.time(),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": merged}, indent=1), encoding="utf-8")
    return merged


def get_news(symbol: str, force: bool = False) -> list[dict]:
    """Merged, deduped, cached ~30 min. Returns newest first."""
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    cache = NEWS_DIR / f"{symbol}.json"
    if cache.exists() and not force:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        if time.time() - payload["fetched_ts"] < CACHE_MINUTES * 60:
            return payload["items"]

    u = store.load_universe().set_index("symbol")
    if symbol not in u.index:
        return []
    yahoo, name = str(u.loc[symbol, "yahoo"]), str(u.loc[symbol, "name"])

    items = _yahoo_news(yahoo) + _google_news(f'"{name}"')
    seen, merged = set(), []
    for it in items:
        key = it["title"].lower()[:70]
        if key in seen:
            continue
        seen.add(key)
        merged.append(it)
    merged.sort(key=lambda x: x["when"] or "", reverse=True)
    merged = merged[:14]

    cache.write_text(json.dumps({
        "fetched_ts": time.time(),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": merged}, indent=1), encoding="utf-8")
    return merged
