"""The nightly job chain — the system that works while you sleep.

    python -m dewaag.jobs nightly

runs: ingest -> quality gate -> fundamentals (weekly) -> calendar ->
signals warm-up -> brief. Every step's outcome lands in data/jobs.json,
which the Today surface reads — you always know whether last night ran,
and a failed step blocks nothing downstream from TELLING you it failed.

Register it once with Windows Task Scheduler:
    powershell -ExecutionPolicy Bypass -File scripts\\register-scheduler.ps1
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import date, datetime, timezone

from dewaag.vault import store

JOBS_PATH = store.DATA_DIR / "jobs.json"


def _step(name: str, fn) -> dict:
    try:
        detail = fn()
        return {"name": name, "ok": True, "detail": str(detail)[:200]}
    except Exception as e:  # noqa: BLE001 — a job chain reports, never dies
        return {"name": name, "ok": False,
                "detail": f"{e} | {traceback.format_exc(limit=1)}"[:300]}


def nightly() -> dict:
    steps: list[dict] = []

    def ingest():
        from dewaag.vault.ingest import ingest_universe
        r = ingest_universe()
        if r["failed"]:
            raise RuntimeError(f"{len(r['failed'])} symbols failed: {r['failed'][:3]}")
        return f"+{r['new_rows']} rows, {r['ok']} symbols"

    def quality():
        from dewaag.vault.quality import gate, run_checks
        findings = run_checks()
        crit = int((findings["level"] == "CRITICAL").sum()) if len(findings) else 0
        if not gate(findings):
            raise RuntimeError(f"{crit} CRITICAL findings — downstream must distrust those symbols")
        return f"gate PASS ({len(findings)} warnings)"

    def fundamentals():
        # weekly is enough — statements change quarterly (Mondays)
        if date.today().weekday() != 0:
            return "skipped (runs Mondays)"
        from dewaag.vault.fundamentals import ingest_universe_fundamentals
        r = ingest_universe_fundamentals()
        return f"{r['ok']} symbols refreshed"

    def calendar():
        from dewaag.vault.calendar import refresh_calendar
        return f"{refresh_calendar()} events"

    def signals():
        from dewaag.engine.signals import compute_signals
        return f"{len(compute_signals())} symbols scored"

    def brief():
        from dewaag.engine.insights import briefing
        items = briefing()
        (store.DATA_DIR / "brief.json").write_text(
            json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "items": items}, indent=2), encoding="utf-8")
        return f"{len(items)} findings"

    def outlook():
        # warm news + street-expectation caches so the morning Stage is instant.
        # Only names you hold or track — the whole universe would hammer feeds.
        from dewaag.pipeline import load as load_cards
        from dewaag.portfolio import load_state
        from dewaag.vault.forward import get_forward
        from dewaag.vault.news import get_news
        symbols = set(load_state()["positions"]) | {c["symbol"] for c in load_cards()
                                                    if c.get("stage") not in ("CLOSED",)}
        n = 0
        for sym in sorted(symbols):
            try:
                get_news(sym, force=True)
                get_forward(sym, force=True)
                n += 1
            except Exception:  # noqa: BLE001 — one dead feed must not fail the night
                pass
        return f"{n} names warmed (news + forward)"

    for name, fn in [("ingest", ingest), ("quality gate", quality),
                     ("fundamentals", fundamentals), ("calendar", calendar),
                     ("signals", signals), ("brief", brief), ("outlook", outlook)]:
        steps.append(_step(name, fn))
        print(f"  {'OK ' if steps[-1]['ok'] else 'FAIL'} {name}: {steps[-1]['detail'][:100]}")

    result = {"last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "ok": all(s["ok"] for s in steps), "steps": steps}
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOBS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def status() -> dict:
    if JOBS_PATH.exists():
        return json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    return {"last_run": None, "ok": None, "steps": [],
            "note": "never run — register the scheduler (scripts/register-scheduler.ps1) or run: python -m dewaag.jobs nightly"}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "nightly"
    if cmd == "nightly":
        r = nightly()
        raise SystemExit(0 if r["ok"] else 1)
    print(__doc__)
