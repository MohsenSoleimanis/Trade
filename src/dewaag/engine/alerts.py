"""The alert engine — the system that taps your shoulder (Finding 2, fixed).

Alerts are computed facts, not opinions: exit levels crossed, earnings
approaching on names you hold or research, drawdown near your signed
limit, data gate failures. Each carries what to do about it.
"""

from __future__ import annotations

import pandas as pd


def compute_alerts() -> list[dict]:
    from dewaag.pipeline import load as load_cards
    from dewaag.portfolio import snapshot
    from dewaag.vault.calendar import upcoming

    out: list[dict] = []
    pf = snapshot()

    # 1. exit levels — your own written rules, watched by the machine
    for p in pf["positions"]:
        if not p["wrong_price"]:
            continue
        if p["last"] <= p["wrong_price"]:
            out.append({"level": "ACT", "symbol": p["symbol"],
                        "text": f"{p['symbol']} at {p['last']:.2f} — BELOW your exit {p['wrong_price']:.2f}. "
                                f"Your own rule says sell or rewrite the thesis in writing. Hope is not a stage."})
        elif p["last"] <= p["wrong_price"] * 1.05:
            out.append({"level": "WATCH", "symbol": p["symbol"],
                        "text": f"{p['symbol']} within 5% of your exit ({p['last']:.2f} vs {p['wrong_price']:.2f}) — decide your response now, while calm."})

    # 2. drawdown vs the signed limit
    if pf["drawdown_limit_eur"]:
        used = pf["drawdown_eur"] / pf["drawdown_limit_eur"]
        if used >= 1.0:
            out.append({"level": "ACT", "symbol": None,
                        "text": f"Drawdown €{pf['drawdown_eur']:,.0f} has REACHED your signed limit. Constitution response: reduce, don't trade faster."})
        elif used > 0.7:
            out.append({"level": "WATCH", "symbol": None,
                        "text": f"Drawdown at {used*100:.0f}% of your limit (€{pf['drawdown_eur']:,.0f} of €{pf['drawdown_limit_eur']:,.0f})."})

    # 3. earnings proximity on names you hold or are researching
    held = {p["symbol"] for p in pf["positions"]}
    researching = {c["symbol"] for c in load_cards() if c["stage"] in ("TRIAGE", "DIVE", "DECISION")}
    for ev in upcoming(10):
        if ev["event"] != "earnings":
            continue
        if ev["symbol"] in held:
            out.append({"level": "WATCH", "symbol": ev["symbol"],
                        "text": f"{ev['symbol']} reports earnings in {ev['days_away']}d — you HOLD it. Decide your stance before the number, not after."})
        elif ev["symbol"] in researching:
            out.append({"level": "INFO", "symbol": ev["symbol"],
                        "text": f"{ev['symbol']} reports in {ev['days_away']}d — it's in your pipeline; the print will move your thesis."})

    # 4. data gate
    try:
        from dewaag.vault.quality import gate, run_checks
        findings = run_checks()
        if not gate(findings):
            bad = findings[findings["level"] == "CRITICAL"]["symbol"].unique()
            out.append({"level": "ACT", "symbol": None,
                        "text": f"DATA GATE FAILED: {', '.join(bad)} quarantined — numbers on those names are not trustworthy today."})
    except Exception:  # noqa: BLE001
        out.append({"level": "WATCH", "symbol": None, "text": "quality checks could not run — treat all data as unverified."})

    order = {"ACT": 0, "WATCH": 1, "INFO": 2}
    return sorted(out, key=lambda a: order[a["level"]])
