"""The console payload — rich, visualizable data for every layer L0-L9.

The engine page used to show one text line per layer. This assembles the
real numbers behind each layer so the UI can render them as live
instruments (gauges, bars, donuts, a track-record curve) — a stranger
should be able to look at it and understand what the machine is doing.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_console(rebuild: bool = False) -> dict:
    from dewaag.engine.auto.allocator import allocate
    from dewaag.engine.auto.book import engine_constitution
    from dewaag.engine.auto.book import snapshot as book_snap
    from dewaag.engine.auto.construct import build_targets
    from dewaag.engine.auto.proposals import decision_history, load_plan
    from dewaag.engine.auto.regime import classify
    from dewaag.engine.auto.strategies import STOCK_TIERS, STRATEGIES, committee_scores
    from dewaag.engine.signals import compute_signals
    from dewaag.vault import store

    signals = compute_signals()
    uni = store.load_universe()
    c = engine_constitution()
    regime = classify(signals)
    votes = committee_scores(signals)
    alloc = allocate(signals, regime)
    targets = build_targets(signals, alloc["blended"], regime, c.max_position_pct)
    book = book_snap()

    plan = None if rebuild else load_plan()
    if not plan:
        from dewaag.engine.auto.pipeline import build_plan
        plan = build_plan()
    proposals = plan.get("proposals", [])

    stocks = signals[signals["tier"].isin(STOCK_TIERS)]

    # ---- L0 data fabric: how healthy is the raw feed? ----
    vs = store.vault_status()
    last_date = str(vs.get("last_date", "?"))
    try:
        fresh_days = (date.today() - date.fromisoformat(last_date)).days
    except Exception:  # noqa: BLE001
        fresh_days = None
    try:
        from dewaag.vault.quality import run_checks
        q = run_checks()
        qcrit = int((q["level"] == "CRITICAL").sum()) if len(q) else 0
        qwarn = int((q["level"] == "WARN").sum()) if len(q) else 0
    except Exception:  # noqa: BLE001
        qcrit = qwarn = 0
    l0 = {
        "total": int(len(uni)),
        "by_tier": {k: int(v) for k, v in uni["tier"].value_counts().items()},
        "by_country": {k: int(v) for k, v in uni["country"].value_counts().head(6).items()},
        "last_date": last_date, "fresh_days": fresh_days,
        "quality": {"critical": qcrit, "warn": qwarn, "ok": qcrit == 0},
    }

    # ---- L1 feature engine: which names lead each factor? ----
    def leaders(col: str) -> list[dict]:
        s = stocks[["symbol", col]].dropna().sort_values(col, ascending=False).head(3)
        return [{"symbol": str(r["symbol"]), "v": round(float(r[col]), 0)} for _, r in s.iterrows()]
    l1 = {
        "stocks_scored": int(len(stocks)),
        "leaders": {"quality": leaders("q_score"), "value": leaders("v_score"), "momentum": leaders("m_score")},
        "avg_coverage": round(float(signals["coverage"].mean()), 1) if "coverage" in signals else None,
    }

    # ---- L3 committee: each strategy's conviction + top pick ----
    strat_rows = []
    for stg in STRATEGIES:
        col = votes[stg.key].dropna()
        if not len(col):
            continue
        top = col.sort_values(ascending=False)
        strat_rows.append({
            "key": stg.key, "name": stg.name, "edge": stg.edge,
            "conviction": round(float(top.head(5).mean()), 0),
            "top": str(top.index[0]), "weight": alloc["weights"].get(stg.key),
        })
    l3 = {"strategies": strat_rows}

    # ---- L4 meta-brain: weights + how confident across names ----
    confs = [b["confidence"] for b in alloc["blended"].values()]
    l4 = {
        "weights": alloc["weights"], "table": alloc["table"], "method": alloc["method"],
        "confidence": {
            "high": sum(1 for x in confs if x >= 0.7),
            "medium": sum(1 for x in confs if 0.4 <= x < 0.7),
            "low": sum(1 for x in confs if x < 0.4),
        },
    }

    # ---- L5 construction: the target book (core-satellite) ----
    l5 = {"picks": targets["picks"], "invested": targets["invested"],
          "cash": targets["cash"], "gross": targets["gross_target"],
          "core_symbol": targets.get("core_symbol"), "core_weight": targets.get("core_weight")}

    # ---- L6 risk & veto: exposures of the target book + charter ----
    tw = {p["symbol"]: p["weight"] for p in targets["picks"]}
    country_exp: dict[str, float] = {}
    tier_exp: dict[str, float] = {}
    for sym, w in tw.items():
        ctry = str(signals.loc[sym, "country"]); ti = str(signals.loc[sym, "tier"])
        country_exp[ctry] = country_exp.get(ctry, 0.0) + w
        tier_exp[ti] = tier_exp.get(ti, 0.0) + w
    l6 = {
        "charter": {"risk_per_idea": c.max_risk_per_idea_pct, "position_cap": c.max_position_pct,
                    "leverage": c.leverage, "max_drawdown_eur": c.max_drawdown_eur, "signed": True},
        "country_exposure": {k: round(v, 3) for k, v in sorted(country_exp.items(), key=lambda x: -x[1])},
        "tier_exposure": {k: round(v, 3) for k, v in sorted(tier_exp.items(), key=lambda x: -x[1])},
        "largest_position": round(max(tw.values()), 3) if tw else 0.0,
        "names": len(tw),
        "drawdown_eur": book["drawdown_eur"], "open_risk_eur": book["open_risk_eur"],
    }

    # ---- L7 execution: the cost model ----
    from dewaag.engine.costs import estimate
    l7 = {
        "half_spread_pct": {"mega": 0.02, "large": 0.05, "mid": 0.20, "small": 0.60, "etf": 0.03},
        "tob_pct": {"share": 0.35, "etf": 0.12}, "commission_eur": 3.0,
        "sample_10k": estimate("mid", 10_000.0),
        "build_cost_eur": round(sum(p.get("est_cost_eur", 0) for p in proposals), 2),
    }

    # ---- L8 autonomy loop: the track record ----
    l8 = {
        "equity_history": book["equity_history"], "equity": book["equity"],
        "pnl_eur": book["pnl_eur"], "pnl_pct": book["pnl_pct"], "starting": book["starting"],
        "holdings": len(book["positions"]), "decisions": len(decision_history(1000)),
        "last_run": plan.get("as_of"),
    }

    # ---- L9 approval gate ----
    pend = [p for p in proposals if p["status"] == "pending"]
    l9 = {"total": len(proposals), "pending": len(pend), "proposals": proposals}

    return {
        "as_of": _now(), "regime": regime, "book": book,
        "layers": {"l0": l0, "l1": l1, "l2": regime, "l3": l3, "l4": l4,
                   "l5": l5, "l6": l6, "l7": l7, "l8": l8, "l9": l9},
    }
