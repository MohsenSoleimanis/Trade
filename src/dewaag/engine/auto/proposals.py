"""L9 — The approval gate + the memory it feeds.

The pipeline (L8) writes a plan of proposals here. This module is the ONE
place a human enters the loop: approve a trade (it goes through the real
gates and fills) or reject it (with a reason). Both are recorded — your
rejections are training data for L4's future ML slot: the system learns
what you will never hold.

Nothing here bypasses anything. approve() calls portfolio.execute(), which
re-runs the full constitution gates. The gate cannot be talked past.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from dewaag.vault import store

AUTO_DIR = store.DATA_DIR / "auto"
PLAN_PATH = AUTO_DIR / "plan.json"
DECISIONS_PATH = AUTO_DIR / "decisions.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_plan(plan: dict) -> None:
    AUTO_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def load_plan() -> dict | None:
    if PLAN_PATH.exists():
        return json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    return None


def _record(entry: dict) -> None:
    AUTO_DIR.mkdir(parents=True, exist_ok=True)
    with DECISIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _find(plan: dict, proposal_id: str) -> dict | None:
    for p in plan.get("proposals", []):
        if p["id"] == proposal_id:
            return p
    return None


def approve(proposal_id: str) -> dict:
    """Human said yes. Route the trade through the real execution gates."""
    plan = load_plan()
    if not plan:
        return {"ok": False, "error": "no active plan"}
    p = _find(plan, proposal_id)
    if not p:
        return {"ok": False, "error": f"unknown proposal {proposal_id}"}
    if p.get("status") == "approved":
        return {"ok": False, "error": "already approved"}

    from dewaag.portfolio import execute
    result = execute(p["symbol"], p["side"], p["shares"],
                     thesis=p.get("rationale", ""), wrong_price=p.get("wrong_price"))

    p["status"] = "approved" if result.get("ok") else "rejected_by_gate"
    p["executed_at"] = _now()
    p["gate_result"] = {"ok": result.get("ok"), "blocks": result.get("blocks")}
    save_plan(plan)
    _record({"at": _now(), "action": "approve", "proposal": p,
             "outcome": "filled" if result.get("ok") else "blocked_by_gate",
             "blocks": result.get("blocks")})
    return {"ok": result.get("ok", False), "proposal": p, "execution": result}


def reject(proposal_id: str, reason: str = "") -> dict:
    """Human said no. The reason is the most valuable training signal we get."""
    plan = load_plan()
    if not plan:
        return {"ok": False, "error": "no active plan"}
    p = _find(plan, proposal_id)
    if not p:
        return {"ok": False, "error": f"unknown proposal {proposal_id}"}
    p["status"] = "rejected"
    p["rejected_at"] = _now()
    p["reject_reason"] = reason
    save_plan(plan)
    _record({"at": _now(), "action": "reject", "proposal": p, "reason": reason})
    return {"ok": True, "proposal": p}


def decision_history(limit: int = 100) -> list[dict]:
    if not DECISIONS_PATH.exists():
        return []
    lines = DECISIONS_PATH.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(x) for x in lines[-limit:]]
