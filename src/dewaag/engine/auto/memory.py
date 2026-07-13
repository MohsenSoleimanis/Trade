"""L8 memory — made readable and usable.

Every approve/reject the engine has ever seen is appended to
data/auto/decisions.jsonl (by proposals.py). That file WAS write-only —
recorded but never read back. This module reads it and turns it into
memory the engine and the human can use:

  * summarize()  — the whole track of decisions + what each has become
  * history(sym) — everything the engine remembers about one name
  * did_reject(sym) — a live check the pipeline uses to respect your "no"

Outcome grading here is honest and light: for filled trades we look up the
CURRENT price in the engine book to show unrealized P&L — did the idea work
so far? Full profit-attribution feeding L4's ML slot is the next step; this
is the memory that makes it possible.
"""

from __future__ import annotations

from dewaag.engine.auto.proposals import decision_history


def _mark_pnl() -> dict[str, dict]:
    """symbol -> {shares, pnl_eur, pnl_pct} from the engine book right now."""
    try:
        from dewaag.engine.auto.book import snapshot
        return {p["symbol"]: {"shares": p["shares"], "pnl_eur": p["pnl_eur"], "pnl_pct": p["pnl_pct"]}
                for p in snapshot()["positions"]}
    except Exception:  # noqa: BLE001
        return {}


def history(symbol: str, limit: int = 800) -> list[dict]:
    """Every decision the engine remembers about one name, newest last."""
    out = []
    for h in decision_history(limit):
        p = h.get("proposal", {})
        if p.get("symbol") != symbol:
            continue
        out.append({"at": h.get("at"), "action": h.get("action"),
                    "side": p.get("side"), "shares": p.get("shares"),
                    "outcome": h.get("outcome"), "reason": h.get("reason")})
    return out


def did_reject(symbol: str, limit: int = 800) -> bool:
    """Did the human reject a proposal on this name recently? The pipeline
    respects it — your 'no' is memory, not noise."""
    for h in reversed(decision_history(limit)):
        p = h.get("proposal", {})
        if p.get("symbol") == symbol:
            return h.get("action") == "reject"    # most-recent decision on the name
    return False


def summarize(limit: int = 800) -> dict:
    hist = decision_history(limit)
    marks = _mark_pnl()

    approved = [h for h in hist if h.get("outcome") == "filled"]
    blocked = [h for h in hist if h.get("outcome") == "blocked_by_gate"]
    rejected = [h for h in hist if h.get("action") == "reject"]

    # which strategies have actually led to approved trades so far
    strategy_usage: dict[str, int] = {}
    for h in approved:
        for k in h.get("proposal", {}).get("fired", []):
            strategy_usage[k] = strategy_usage.get(k, 0) + 1

    # per-name tally + how the still-held ones are doing
    by_symbol: dict[str, dict] = {}
    for h in hist:
        p = h.get("proposal", {})
        sym = p.get("symbol")
        if not sym:
            continue
        rec = by_symbol.setdefault(sym, {"symbol": sym, "approved": 0, "rejected": 0})
        if h.get("outcome") == "filled":
            rec["approved"] += 1
        elif h.get("action") == "reject":
            rec["rejected"] += 1
        if sym in marks:
            rec["holding_pnl_eur"] = marks[sym]["pnl_eur"]
            rec["holding_pnl_pct"] = marks[sym]["pnl_pct"]

    recent = [{"at": h.get("at"), "action": h.get("action"),
               "symbol": h.get("proposal", {}).get("symbol"),
               "side": h.get("proposal", {}).get("side"),
               "shares": h.get("proposal", {}).get("shares"),
               "outcome": h.get("outcome"), "reason": h.get("reason")}
              for h in hist[-12:]][::-1]

    return {
        "total": len(hist), "approved": len(approved),
        "blocked": len(blocked), "rejected": len(rejected),
        "strategy_usage": dict(sorted(strategy_usage.items(), key=lambda kv: -kv[1])),
        "by_symbol": sorted(by_symbol.values(), key=lambda r: -(r["approved"] + r["rejected"])),
        "recent": recent,
        "note": ("The engine remembers every decision and its reasoning. Outcomes shown are live unrealized P&L on "
                 "names still held — the raw material the L4 learning model will train on next."),
    }
