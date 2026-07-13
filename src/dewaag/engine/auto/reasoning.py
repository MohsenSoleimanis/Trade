"""Per-decision reasoning — the deterministic evidence AND the news.

Every proposal carries one of these. It is NOT a black box: it lists the
exact deterministic signals behind the call (which strategies fired and
their scores, the regime, the valuation/quality read, the macro channel,
the risk sizing) and — separately and honestly labelled — the news and
calendar CONTEXT.

News is context, never a buy signal (Lesson 1: a headline you can read is
already in the price). Its job here is so you are never surprised, and so
imminent event-risk (earnings in a few days) is flagged before you approve.
"""

from __future__ import annotations


def _sizing_note(p: dict) -> str:
    if p.get("tier") == "etf":
        return "Basket core — you accumulate it, so no single-name stop and no per-idea risk budget applies."
    wrong, stop = p.get("wrong_price"), p.get("stop_pct")
    if wrong:
        return (f"Risk-sized backwards: exit if it falls to {wrong} (−{stop}%); shares chosen so the worst-case "
                f"loss is ~1% of the book — conviction never enters the size (constitution §1).")
    return "Risk-sized to the per-idea budget."


def build_reasoning(p: dict, regime: dict, mem_hist: list[dict] | None = None) -> dict:
    """p = a proposal dict already built. Returns a structured reasoning."""
    from dewaag.engine.auto.strategies import by_key
    sym = p["symbol"]
    names = by_key()

    # ---- deterministic evidence ----
    strategies = [{"name": names[k].name, "why": names[k].edge}
                  for k in p.get("fired", []) if k in names]

    evidence: list[str] = []
    macro_line = None
    if p.get("tier") == "etf":
        evidence.append("A whole-market basket — it is diversification itself, so it has no single-company thesis to check.")
    else:
        try:
            from dewaag.engine.signals import engine_read
            evidence = [b for b in engine_read(sym).get("bullets", [])][:4]
        except Exception:  # noqa: BLE001
            evidence = []
        try:
            from dewaag.engine.macro import sensitivities
            sens = [s for s in sensitivities(sym) if s["channel"] != "IWDA" and s.get("strength") not in ("negligible", "—")]
            if sens:
                macro_line = sens[0]["so_what"]
        except Exception:  # noqa: BLE001
            macro_line = None

    deterministic = {
        "regime": regime.get("label", ""),
        "strategies": strategies,
        "conviction": p.get("score"),
        "confidence": p.get("confidence"),
        "evidence": evidence,
        "macro": macro_line,
        "sizing": _sizing_note(p),
    }

    # ---- news + calendar CONTEXT (not a signal) ----
    headlines, event = [], None
    try:
        from dewaag.vault.news import get_news
        headlines = [{"when": n.get("when"), "title": n.get("title"), "source": n.get("source"), "link": n.get("link")}
                     for n in get_news(sym)[:3]]
    except Exception:  # noqa: BLE001
        headlines = []
    try:
        from dewaag.vault.calendar import upcoming
        ev = [e for e in upcoming(10) if e["symbol"] == sym]
        if ev:
            e0 = ev[0]
            event = f"{e0['event']} in {e0['days_away']} day(s) — binary event risk; consider waiting until after."
    except Exception:  # noqa: BLE001
        event = None

    news = {"headlines": headlines, "event": event,
            "note": "Context, not a signal — news you can read is already in the price. Here so you're not surprised."}

    # ---- memory: what the engine remembers about this name ----
    prior = mem_hist if mem_hist is not None else []
    memory = {"prior": prior[-4:],
              "note": ("You rejected this name before — the engine keeps proposing the best idea, but flags your past 'no'."
                       if any(h.get("action") == "reject" for h in prior) else
                       ("Held before / acted on before." if prior else "First time the engine has proposed this name."))}

    # ---- one-paragraph summary ----
    strat_txt = ", ".join(s["name"] for s in strategies) or "the blended committee"
    summary = (f"{sym}: in a {deterministic['regime'].lower()} regime, {strat_txt} rate it "
               f"{p.get('score', '?')}/100 with {int((p.get('confidence') or 0)*100)}% confidence. "
               f"{_sizing_note(p)}"
               + (f" ⚠ Event: {event}" if event else "")
               + (" This is a systematic proposal — approve only if you also accept the thesis and the news."))

    return {"deterministic": deterministic, "news": news, "memory": memory, "summary": summary}
