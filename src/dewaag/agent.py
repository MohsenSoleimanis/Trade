"""The Agent Floor — session mode, with MEMORY.

Three ideas, all enforced here:

1. AGENTS READ THE RECORD. `context_pack(symbol)` assembles everything the
   system remembers about a name — position, every past trade with its
   thesis, the pipeline card and its full stage history, the engine's
   quantitative read, calendar events, data-quality state, and any prior
   agent brief. This is what "the agent knows" — no hidden state.

2. AGENTS WRITE WITH PROVENANCE. Briefs land in data/agent/briefs/ with
   author, timestamp and the list of inputs used. An unattributed opinion
   is not research.

3. THE FLOOR HAS A MEMORY. data/agent/memory.jsonl is an append-only log
   of observations ("wrote first COLR brief", "user passed on ABI because…")
   that future sessions — and future autonomous agents — recall before
   acting. Session mode today (Claude works the floor during sessions);
   claude-api mode later reads and writes the exact same stores.

Governance unchanged: agents produce briefs and features. They never
touch orders — the constitution gates don't know agents exist.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from dewaag.vault import store

AGENT_DIR = store.DATA_DIR / "agent"
BRIEFS_DIR = AGENT_DIR / "briefs"
MEMORY_PATH = AGENT_DIR / "memory.jsonl"

BRIEF_SECTIONS = ["summary", "bull_case", "bear_case", "verify", "verdict"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------- briefs

def save_brief(symbol: str, sections: dict, *, author: str = "claude-session",
               inputs: list[str] | None = None) -> dict:
    missing = [s for s in BRIEF_SECTIONS if not sections.get(s)]
    if missing:
        raise ValueError(f"brief incomplete — missing {missing}: a one-sided brief is a pitch, not research")
    brief = {"symbol": symbol, "at": _now(), "author": author,
             "inputs": inputs or [], "sections": {k: sections[k] for k in BRIEF_SECTIONS}}
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    (BRIEFS_DIR / f"{symbol}.json").write_text(json.dumps(brief, indent=2), encoding="utf-8")
    remember("brief_written", f"research brief for {symbol} by {author}", symbol=symbol)
    return brief


def load_brief(symbol: str) -> dict | None:
    p = BRIEFS_DIR / f"{symbol}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def list_briefs() -> list[dict]:
    if not BRIEFS_DIR.exists():
        return []
    out = []
    for p in sorted(BRIEFS_DIR.glob("*.json")):
        b = json.loads(p.read_text(encoding="utf-8"))
        out.append({"symbol": b["symbol"], "at": b["at"], "author": b["author"]})
    return out


# ------------------------------------------------------------- memory

def remember(kind: str, text: str, symbol: str | None = None) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": _now(), "kind": kind, "symbol": symbol, "text": text}) + "\n")


def recall(n: int = 50, symbol: str | None = None) -> list[dict]:
    if not MEMORY_PATH.exists():
        return []
    rows = [json.loads(line) for line in MEMORY_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    if symbol:
        rows = [r for r in rows if r.get("symbol") == symbol]
    return rows[-n:]


# ------------------------------------------------------------- context

def context_pack(symbol: str) -> dict:
    """Everything the system remembers about one name — the agent's reading
    desk, and the honest answer to 'what do you know and how do you know it'."""
    from dewaag.engine.signals import compute_signals, engine_read
    from dewaag.pipeline import load as load_cards
    from dewaag.portfolio import load_state
    from dewaag.vault.calendar import upcoming
    from dewaag.vault.quality import check_frame

    state = load_state()
    position = state["positions"].get(symbol)
    trades = [t for t in state["trades"] if t["symbol"] == symbol]
    cards = [c for c in load_cards() if c["symbol"] == symbol]

    sig_row = None
    df = compute_signals()
    if symbol in df.index:
        r = df.loc[symbol]
        sig_row = {k: (None if r[k] != r[k] else (float(r[k]) if hasattr(r[k], "item") or isinstance(r[k], float) else r[k]))
                   for k in ("price", "sector", "pe", "roe_avg", "dte", "cash_conv_avg",
                             "rev_growth", "mom_12_1", "vol_1y", "max_dd_1y",
                             "q_score", "v_score", "m_score", "composite")}

    try:
        prices = store.load_prices(symbol).sort_values("date")
        quality = check_frame(symbol, prices)
    except FileNotFoundError:
        quality = [{"level": "CRITICAL", "check": "missing", "detail": "no price history"}]

    # the forward half of the desk: news + street expectations. Cached on
    # disk; a dead network yields empty/unavailable, never a crashed brief.
    from dewaag.engine.macro import regime, sensitivities
    from dewaag.vault.forward import get_forward
    from dewaag.vault.news import get_news

    return {
        "symbol": symbol,
        "as_of": _now(),
        "position": position,
        "trades": trades,                       # every fill, with thesis, forever
        "pipeline": cards,                      # stage history incl. pass reasons
        "engine": engine_read(symbol),
        "signals": sig_row,
        "calendar": [e for e in upcoming(30) if e["symbol"] == symbol],
        "news": get_news(symbol),               # what is happening NOW
        "forward": get_forward(symbol),         # what the street expects NEXT
        "macro": {"regime": regime(),           # how the WORLD reaches this name
                  "sensitivities": sensitivities(symbol)},
        "quality": quality,
        "brief": load_brief(symbol),
        "agent_memory": recall(20, symbol=symbol),
    }
