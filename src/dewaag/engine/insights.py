"""The engine briefing — findings the machine generates BY ITSELF.

Runs every rule it knows over the whole universe and your portfolio,
and reports what it found, ordered by severity:

  ALERT   your own rules are violated (thesis broken, drawdown hot)
  FLAG    evidence patterns that demand a look (value traps, cash gaps)
  CANDIDATE evidence combinations worth research time (quality-at-a-price)
  CONTEXT market weather (breadth, benchmark drawdown)

Every finding carries its evidence and its lesson. The engine proposes;
you dispose — same law as the agents.
"""

from __future__ import annotations

import pandas as pd

from dewaag.engine.signals import compute_signals


def _f(severity: str, title: str, detail: str, symbols: list[str], lesson: str) -> dict:
    return {"severity": severity, "title": title, "detail": detail,
            "symbols": symbols, "lesson": lesson}


def briefing() -> list[dict]:
    from dewaag.portfolio import snapshot

    df = compute_signals()
    stocks = df[df["tier"] != "etf"]
    pf = snapshot()
    out: list[dict] = []

    # ---------- ALERTS: your own rules, watched by the machine ----------
    for p in pf["positions"]:
        if p["wrong_price"] and p["last"] < p["wrong_price"]:
            out.append(_f("ALERT", f"{p['symbol']}: your thesis is broken by your own rule",
                          f"price {p['last']:.2f} is below your written 'I am wrong at {p['wrong_price']:.2f}'. "
                          f"Calm-you defined this exit; the only honest moves are to sell or to rewrite the thesis in writing — not to hope.",
                          [p["symbol"]], "Lesson 6 §6"))
        elif p["wrong_price"] and p["last"] < p["wrong_price"] * 1.05:
            out.append(_f("FLAG", f"{p['symbol']}: within 5% of your exit level",
                          f"price {p['last']:.2f} vs your wrong-price {p['wrong_price']:.2f}. Decide NOW, while calm, what you'll do if it gets there.",
                          [p["symbol"]], "Lesson 6"))

    if pf["drawdown_limit_eur"]:
        used = pf["drawdown_eur"] / pf["drawdown_limit_eur"]
        if used > 0.7:
            out.append(_f("ALERT", f"drawdown at {used*100:.0f}% of your signed limit",
                          f"€{pf['drawdown_eur']:,.0f} of €{pf['drawdown_limit_eur']:,.0f}. Constitution response: smaller sizes, never faster trading.",
                          [], "Lesson 6 trap #1"))

    eur_inv = sum(p["value_eur"] for p in pf["positions"] if p["currency"] == "USD")
    if pf["invested"] > 0 and eur_inv / pf["invested"] > 0.6:
        out.append(_f("FLAG", "USD concentration — the double bet is on",
                      f"{eur_inv/pf['invested']*100:.0f}% of invested money rides the dollar as well as the stocks.",
                      [], "Lesson 2 §6"))

    # ---------- FLAGS: evidence patterns across the universe ----------
    traps = stocks[(stocks["v_score"] > 70) & (stocks["q_score"] < 35)]
    if len(traps):
        out.append(_f("FLAG", f"value-trap shape: {', '.join(traps['symbol'])}",
                      "cheap on earnings yield AND weak on quality — the market may be right about the decline. Decode before touching.",
                      list(traps["symbol"]), "Lesson 4 trap #1"))

    cash_gap = stocks[stocks["cash_conv_avg"].notna() & (stocks["cash_conv_avg"] < 0.6)]
    if len(cash_gap):
        out.append(_f("FLAG", f"profit ≠ cash: {', '.join(cash_gap['symbol'])}",
                      f"multi-year cash conversion below 0.6 — profits not turning into money. The Wirecard question applies.",
                      list(cash_gap["symbol"]), "Lesson 3 §4"))

    # ---------- CANDIDATES: where evidence aligns ----------
    qarp = stocks[(stocks["q_score"] > 60) & (stocks["v_score"] > 55)].sort_values("composite", ascending=False)
    if len(qarp):
        out.append(_f("CANDIDATE", f"quality at a reasonable price: {', '.join(qarp['symbol'].head(5))}",
                      "good businesses not priced for perfection — the evidence-favored hunting ground. Next step is human: read the statements, write a thesis, demand a margin of safety.",
                      list(qarp["symbol"].head(5)), "Lessons 4 & 7"))

    strong = stocks[(stocks["m_score"] > 80) & (stocks["q_score"] > 50)].sort_values("m_score", ascending=False)
    if len(strong):
        out.append(_f("CANDIDATE", f"quality with momentum: {', '.join(strong['symbol'].head(5))}",
                      "the market rewarding decent businesses — momentum's evidence is strongest of all factors, but mind turnover costs in Belgium (ETF form or long holds).",
                      list(strong["symbol"].head(5)), "Lesson 7"))

    # ---------- CONTEXT: the weather ----------
    breadth = float(stocks["above_200d"].mean())
    tide = "risk-on" if breadth > 0.65 else ("risk-off" if breadth < 0.35 else "mixed")
    out.append(_f("CONTEXT", f"breadth: {breadth*100:.0f}% of universe above its 200-day average ({tide})",
                  "the tide, measured. Not a prediction — exposure awareness. When breadth is extreme, correlations rise and diversification thins.",
                  [], "Lesson 5"))

    if "IWDA" in df.index:
        iwda = df.loc["IWDA"]
        if pd.notna(iwda["max_dd_1y"]) and iwda["max_dd_1y"] < -0.1:
            out.append(_f("CONTEXT", f"benchmark drew down {iwda['max_dd_1y']*100:.0f}% within the year",
                          "the market itself has been through weather — judge your own drawdown against this, not against zero.",
                          ["IWDA"], "Lesson 5"))

    order = {"ALERT": 0, "FLAG": 1, "CANDIDATE": 2, "CONTEXT": 3}
    return sorted(out, key=lambda f: order[f["severity"]])
