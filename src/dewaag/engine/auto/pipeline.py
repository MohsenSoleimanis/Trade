"""L8 — The autonomy loop: run L0 → L9 and emit a plan of proposals.

This is the orchestrator. It threads the whole brain together and produces,
per proposed trade, a finished card that stops at the approval gate. It also
computes the ideal TARGET portfolio (capital-independent) so the engine's
opinion is visible even on an account too small to act on all of it.

Deliberately NOT anchored to any account size: build_plan computes the ideal
shape first, then the concrete trades for whatever book actually exists.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from dewaag.engine.auto import proposals as prop_store
from dewaag.engine.auto.allocator import allocate
from dewaag.engine.auto.construct import build_targets
from dewaag.engine.auto.regime import classify
from dewaag.engine.auto.strategies import by_key


# one-way costs above this fraction of the trade mean it's not worth doing —
# the fee eats the edge. Such tilts are skipped until the book grows.
MAX_COST_RATIO = 0.015


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stop_fraction(vol_1y: float | None) -> float:
    """A volatility-scaled 'I am wrong' distance. Wild names get a wider
    stop (so normal noise doesn't knock you out); calm names a tighter one.
    Bounded 8%–30%."""
    if vol_1y is None or vol_1y != vol_1y or vol_1y <= 0:
        return 0.20
    monthly = float(vol_1y) / (12 ** 0.5)
    return max(0.08, min(0.30, 1.5 * monthly))


def _rationale(sym: str, pick: dict, regime: dict) -> str:
    names = by_key()
    fired = ", ".join(names[k].name for k in pick.get("fired", []) if k in names) or "the blended committee"
    return (f"{sym}: {regime['label'].lower()} regime; {fired} rank it {pick['score']:.0f}/100 "
            f"with {int(pick['confidence']*100)}% committee confidence. Sized by risk, capped by the constitution. "
            f"This is a systematic proposal — approve only if you also accept the thesis.")


def _propose_trades(targets: dict, snap: dict, signals_df: pd.DataFrame,
                    constitution) -> list[dict]:
    from dewaag.engine.auto.book import ENGINE_COMMISSION_EUR, HALF_SPREAD
    from dewaag.engine.costs import estimate
    from dewaag.engine.sizing import gate_order
    from dewaag.portfolio import to_eur

    equity = float(snap.get("equity", 0.0)) or 0.0
    held_eur = {p["symbol"]: p["value_eur"] for p in snap.get("positions", [])}
    held_shares = {p["symbol"]: p["shares"] for p in snap.get("positions", [])}
    target_syms = {p["symbol"] for p in targets["picks"]}
    risk_budget = equity * constitution.max_risk_per_idea_pct / 100.0   # §1: euros at risk per idea

    proposals: list[dict] = []
    skipped: list[dict] = []

    # BUYS / ADDS toward the target shape
    for pick in targets["picks"]:
        sym = pick["symbol"]
        if sym not in signals_df.index:
            continue
        row = signals_df.loc[sym]
        price = float(row["price"])
        currency = str(row["currency"])
        tier = str(row["tier"])
        price_eur = to_eur(price, currency)
        if price_eur <= 0:
            continue

        # price the fill EXACTLY as execution will (last close + half-spread),
        # and gate on that — so a proposal shown as "pending" can never be
        # rejected on approval by a few cents of spread.
        fill = price * (1 + HALF_SPREAD.get(tier, 0.004))
        target_eur = pick["weight"] * equity
        delta_eur = target_eur - held_eur.get(sym, 0.0)
        weight_shares = int(delta_eur // to_eur(fill, currency))

        if tier == "etf":
            # a broad basket core has no single-name stop and no per-idea risk
            # budget — it IS the diversification; you accumulate it, not exit it.
            wrong = None
            stop = 0.0
            shares = weight_shares
        else:
            # a stock is bounded by BOTH the target weight (L5) AND the per-idea
            # risk budget (L6): a 10% position with a 20% stop is 2% risk, and
            # the risk rule wins — take the smaller of the two share counts.
            stop = _stop_fraction(row.get("vol_1y"))
            wrong = round(price * (1 - stop), 4)
            loss_per_share_eur = to_eur(fill - wrong, currency)
            risk_shares = int(risk_budget // loss_per_share_eur) if loss_per_share_eur > 0 else 0
            shares = min(weight_shares, risk_shares)
        if shares < 1:
            continue

        pos_after = to_eur(fill * (held_shares.get(sym, 0) + shares), currency)
        blocks = gate_order(constitution, portfolio_value=equity,
                            position_value_after=pos_after, shares=shares,
                            entry=fill, wrong_price=wrong,
                            thesis=_rationale(sym, pick, {"label": ""}), side="BUY", tier=tier)
        notional_eur = to_eur(fill * shares, currency)
        costs = estimate(tier, notional_eur, commission=ENGINE_COMMISSION_EUR)

        # COST-EFFICIENCY FILTER: don't propose a trade too small to be worth it.
        # At a small book size a €20 stock nibble pays more in fees than it can
        # earn — so it's skipped (and shown as skipped), not silently bought red.
        cost_ratio = costs["total"] / notional_eur if notional_eur else 1.0
        if cost_ratio > MAX_COST_RATIO:
            skipped.append({"symbol": sym, "name": str(row["name"]), "notional_eur": round(notional_eur, 2),
                            "cost_pct": round(cost_ratio * 100, 1),
                            "reason": f"too small to trade cost-effectively — fees would be {cost_ratio*100:.1f}% of the buy"})
            continue

        proposals.append({
            "id": f"{sym}-BUY-{_now()}",
            "symbol": sym, "name": str(row["name"]), "side": "BUY",
            "shares": shares, "price": round(price, 4), "currency": currency, "tier": tier,
            "target_weight": pick["weight"], "score": pick["score"],
            "confidence": pick["confidence"], "fired": pick["fired"],
            "wrong_price": wrong, "stop_pct": round(stop * 100, 1),
            "est_cost_eur": costs["total"], "notional_eur": round(notional_eur, 2),
            "status": "blocked" if blocks else "pending",
            "blocks": blocks,
        })

    # EXITS — holdings the brain no longer wants
    for sym, shares in held_shares.items():
        if sym in target_syms or shares <= 0:
            continue
        row = signals_df.loc[sym] if sym in signals_df.index else None
        price = float(row["price"]) if row is not None else 0.0
        currency = str(row["currency"]) if row is not None else "EUR"
        tier = str(row["tier"]) if row is not None else "mid"
        costs = estimate(tier, to_eur(price * shares, currency)) if price else {"total": 0.0}
        proposals.append({
            "id": f"{sym}-SELL-{_now()}",
            "symbol": sym, "name": str(row["name"]) if row is not None else sym, "side": "SELL",
            "shares": int(shares), "price": round(price, 4), "currency": currency, "tier": tier,
            "target_weight": 0.0, "reason": "no longer in the target portfolio for this regime",
            "est_cost_eur": costs["total"], "notional_eur": round(to_eur(price * shares, currency), 2),
            "status": "pending", "blocks": [],
            "rationale": f"Exit {sym}: it fell out of the target book for the current regime.",
        })

    # attach the real rationale (needs the regime label) to buys
    return proposals, skipped


def _layer_summary(signals_df, regime, alloc, targets, proposals, snap, constitution) -> list[dict]:
    """One visible status line per layer L0-L9 — so the whole brain is on
    screen and nothing looks skipped. Every layer runs on every plan; the
    ones without their own rich panel still report here."""
    from dewaag.engine.auto.strategies import STOCK_TIERS, STRATEGIES
    from dewaag.vault import store

    try:
        total_universe = len(store.load_universe())
        last_date = str(store.vault_status().get("last_date", "?"))
    except Exception:  # noqa: BLE001
        total_universe, last_date = len(signals_df), "?"
    n_stocks = int(signals_df["tier"].isin(STOCK_TIERS).sum())

    try:
        from dewaag.engine.auto.proposals import decision_history
        n_decisions = len(decision_history(1000))
    except Exception:  # noqa: BLE001
        n_decisions = 0

    pending = [p for p in proposals if p["status"] == "pending"]
    top_strat = max(alloc["weights"].items(), key=lambda kv: kv[1])[0] if alloc["weights"] else "—"
    top_name = alloc["table"].get(top_strat, {}).get("name", top_strat)

    return [
        {"code": "L0", "name": "Data fabric", "role": "the senses",
         "status": "live", "detail": f"{total_universe} instruments in the universe · vault current to {last_date}"},
        {"code": "L1", "name": "Feature engine", "role": "understanding",
         "status": "live", "detail": f"{n_stocks} stocks turned into factor portraits (value, quality, momentum, risk, macro)"},
        {"code": "L2", "name": "Regime", "role": "the weather brain",
         "status": "panel", "detail": f"{regime['label']} · deploy dial {int(regime['gross_target']*100)}%"},
        {"code": "L3", "name": "Alpha committee", "role": f"{len(STRATEGIES)} strategies vote",
         "status": "panel", "detail": f"{len(STRATEGIES)} independent strategies scored every stock 0-100"},
        {"code": "L4", "name": "Meta-brain", "role": "whose vote counts",
         "status": "panel", "detail": f"loudest voice this regime: {top_name}. ML meta-learner is the reserved v2 slot."},
        {"code": "L5", "name": "Construction", "role": "the architect",
         "status": "panel", "detail": f"{len(targets['picks'])} names, {int(targets['invested']*100)}% invested, sized by risk & capped"},
        {"code": "L6", "name": "Risk & constitution veto", "role": "the un-overridable law",
         "status": "live", "detail": (f"signed · risk/idea {constitution.max_risk_per_idea_pct}% · position cap {constitution.max_position_pct}% · leverage {constitution.leverage}"
                                       if snap.get("constitution_signed") else "UNSIGNED — the veto holds every trade (this is why L9 is empty)")},
        {"code": "L7", "name": "Execution", "role": "the hands",
         "status": "live", "detail": "cheapest-fill + Belgian TOB/commission modeled on every proposal below (cost shown per card)"},
        {"code": "L8", "name": "Autonomy loop + memory", "role": "the life of the system",
         "status": "live", "detail": f"ran the full pipeline just now · {n_decisions} past decisions remembered (feed the L4 ML slot)"},
        {"code": "L9", "name": "Approval gate", "role": "the one door you touch",
         "status": "panel", "detail": f"{len(proposals)} proposal(s), {len(pending)} awaiting your approval"},
    ]


def build_plan(signals_df: pd.DataFrame | None = None, snap: dict | None = None,
               constitution=None, persist: bool = True) -> dict:
    """Run the whole brain. Deps are injectable for testing."""
    if signals_df is None:
        from dewaag.engine.signals import compute_signals
        signals_df = compute_signals()
    # DEFAULT to the engine's OWN autonomous book + its pre-signed charter —
    # not the personal €100 account. The engine is its own trader; it must be
    # able to act and build a track record without waiting on your signature.
    if constitution is None:
        from dewaag.engine.auto.book import engine_constitution
        constitution = engine_constitution()
    if snap is None:
        from dewaag.engine.auto.book import snapshot as engine_snapshot
        snap = engine_snapshot()

    regime = classify(signals_df)                                   # L2
    alloc = allocate(signals_df, regime)                            # L3 + L4
    targets = build_targets(signals_df, alloc["blended"], regime,   # L5
                            constitution.max_position_pct)

    proposals, skipped = _propose_trades(targets, snap, signals_df, constitution)  # L6/L7/L9

    # attach the full reasoning to every proposal: deterministic signals +
    # news CONTEXT + this name's memory. Read the decision log ONCE.
    from dewaag.engine.auto.memory import history as mem_history
    from dewaag.engine.auto.reasoning import build_reasoning
    for p in proposals:
        if p["side"] == "BUY":
            pick = next((x for x in targets["picks"] if x["symbol"] == p["symbol"]), None)
            if pick:
                p["rationale"] = _rationale(p["symbol"], pick, regime)
        try:
            p["reasoning"] = build_reasoning(p, regime, mem_history(p["symbol"]))
        except Exception:  # noqa: BLE001 — reasoning must never break a plan
            p["reasoning"] = None

    plan = {
        "as_of": _now(),
        "regime": regime,
        "allocator": {"weights": alloc["weights"], "table": alloc["table"], "method": alloc["method"]},
        "targets": targets,
        "proposals": proposals,
        "skipped": skipped,
        "book": {"equity": snap.get("equity"), "cash": snap.get("cash"),
                 "signed": snap.get("constitution_signed", False)},
        "executable_note": _executable_note(snap, proposals, skipped),
        "layers": _layer_summary(signals_df, regime, alloc, targets, proposals, snap, constitution),
    }
    if persist:
        prop_store.save_plan(plan)
    return plan


def _executable_note(snap: dict, proposals: list[dict], skipped: list[dict] | None = None) -> str:
    skip_txt = ""
    if skipped:
        names = ", ".join(s["symbol"] for s in skipped[:4])
        skip_txt = (f" {len(skipped)} smaller tilt(s) skipped ({names}) — too small to trade cost-effectively at "
                    "this book size; they return as the account grows.")
    if not snap.get("constitution_signed", False):
        return ("The constitution is unsigned, so every proposal is held at the gate — this is the veto (L6) "
                "working exactly as designed. Sign it to let the gate evaluate trades on their merits." + skip_txt)
    ready = [p for p in proposals if p["status"] == "pending"]
    if not ready:
        return ("No proposal is executable on the current book (size and caps) — the engine's opinion is the "
                "target portfolio above; the honest action at this size is accumulating a world core." + skip_txt)
    return f"{len(ready)} proposal(s) cleared the gate and are waiting for your approval.{skip_txt}"
