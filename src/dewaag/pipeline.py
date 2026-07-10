"""The Pipeline — the process spine (audit Finding 1, fixed).

Every idea is a card that travels explicit stages. Stage transitions have
RULES the store enforces — the process is law, like the constitution:

  INBOX     an idea exists (from screener, brief, or you)
  TRIAGE    the machine attached a dossier; you decide: advance or pass
  DIVE      you owe a thesis and an "I am wrong at" level
  DECISION  memo complete; buy or pass — both logged forever
  LIVE      a real (paper) position exists; exits armed
  CLOSED    position exited; a post-mortem grade is OWED
  PASSED    consciously rejected, with the reason kept (pass reasons are
            data about you — the bias dashboard reads them later)

Orders and the pipeline are linked: a BUY moves the symbol's card to LIVE;
a full SELL moves it to CLOSED and opens the grading task.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dewaag.vault import store

PIPELINE_PATH = store.DATA_DIR / "pipeline.json"

STAGES = ["INBOX", "TRIAGE", "DIVE", "DECISION", "LIVE", "CLOSED", "PASSED"]
FORWARD = {"INBOX": "TRIAGE", "TRIAGE": "DIVE", "DIVE": "DECISION"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> list[dict]:
    if PIPELINE_PATH.exists():
        return json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
    return []


def save(cards: list[dict]) -> None:
    PIPELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_PATH.write_text(json.dumps(cards, indent=2), encoding="utf-8")


def add_card(symbol: str, source: str = "manual", note: str = "") -> dict:
    cards = load()
    if any(c["symbol"] == symbol and c["stage"] not in ("CLOSED", "PASSED") for c in cards):
        raise ValueError(f"{symbol} already has an open card")
    card = {
        "id": uuid.uuid4().hex[:10], "symbol": symbol, "stage": "INBOX",
        "source": source, "note": note, "created": _now(),
        "thesis": "", "wrong_price": None, "pass_reason": "",
        "grade": None, "grade_note": "",
        "history": [{"at": _now(), "to": "INBOX", "why": f"added ({source})"}],
    }
    cards.append(card)
    save(cards)
    return card


def _find(cards: list[dict], card_id: str) -> dict:
    for c in cards:
        if c["id"] == card_id:
            return c
    raise KeyError(f"no card {card_id}")


def advance(card_id: str, *, thesis: str = "", wrong_price: float | None = None) -> dict:
    """Move forward one stage. The DIVE->DECISION door checks the thesis:
    process gates mirror order gates — no judgment, no advance."""
    cards = load()
    c = _find(cards, card_id)
    nxt = FORWARD.get(c["stage"])
    if not nxt:
        raise ValueError(f"cannot advance from {c['stage']}")
    if thesis:
        c["thesis"] = thesis
    if wrong_price is not None:
        c["wrong_price"] = wrong_price
    if nxt == "DECISION":
        if len(c["thesis"].strip()) < 20:
            raise ValueError("DECISION requires a written thesis (min one honest sentence)")
        if not c["wrong_price"]:
            raise ValueError("DECISION requires an 'I am wrong at…' price")
    c["stage"] = nxt
    c["history"].append({"at": _now(), "to": nxt, "why": "advanced"})
    save(cards)
    return c


def pass_card(card_id: str, reason: str) -> dict:
    cards = load()
    c = _find(cards, card_id)
    if len(reason.strip()) < 5:
        raise ValueError("a pass needs a reason — pass reasons are data about you")
    c["stage"] = "PASSED"
    c["pass_reason"] = reason
    c["history"].append({"at": _now(), "to": "PASSED", "why": reason})
    save(cards)
    return c


def grade(card_id: str, grade_value: str, note: str = "") -> dict:
    cards = load()
    c = _find(cards, card_id)
    if c["stage"] != "CLOSED":
        raise ValueError("only CLOSED cards get post-mortem grades")
    if grade_value not in ("thesis_right", "thesis_wrong", "lucky", "unlucky"):
        raise ValueError("grade must be one of: thesis_right, thesis_wrong, lucky, unlucky")
    c["grade"] = grade_value
    c["grade_note"] = note
    c["history"].append({"at": _now(), "to": "CLOSED", "why": f"graded: {grade_value}"})
    save(cards)
    return c


def on_trade(symbol: str, side: str, position_remaining: int) -> None:
    """Called by the broker after every fill — trades move cards."""
    cards = load()
    for c in cards:
        if c["symbol"] != symbol or c["stage"] in ("CLOSED", "PASSED"):
            continue
        if side == "BUY" and c["stage"] in ("INBOX", "TRIAGE", "DIVE", "DECISION"):
            c["stage"] = "LIVE"
            c["history"].append({"at": _now(), "to": "LIVE", "why": "order filled"})
        elif side == "SELL" and c["stage"] == "LIVE" and position_remaining == 0:
            c["stage"] = "CLOSED"
            c["history"].append({"at": _now(), "to": "CLOSED", "why": "position closed — post-mortem due"})
    save(cards)


def tasks() -> list[dict]:
    """What the process owes the human — surfaces on Today."""
    out = []
    for c in load():
        if c["stage"] == "CLOSED" and c["grade"] is None:
            out.append({"kind": "post_mortem", "card": c["id"], "symbol": c["symbol"],
                        "text": f"{c['symbol']} closed — grade the thesis (2 minutes, feeds your bias stats)"})
        if c["stage"] == "DECISION":
            out.append({"kind": "decision", "card": c["id"], "symbol": c["symbol"],
                        "text": f"{c['symbol']} memo complete — buy or pass, both are decisions"})
        if c["stage"] == "TRIAGE":
            out.append({"kind": "triage", "card": c["id"], "symbol": c["symbol"],
                        "text": f"{c['symbol']} dossier ready — worth an hour, or pass with a reason?"})
    return out
