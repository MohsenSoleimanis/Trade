"""The macro lens — how the world reaches your companies.

You cannot forecast a war, a pandemic or a climate shock. What you CAN do
is what professionals do instead of forecasting:

  1. Watch the CHANNELS. Shocks reach a company through traded prices —
     oil, the dollar, interest rates, market fear (VIX), gold. Those
     prices digest the world's news within minutes (Lesson 1), so the
     regime read below is a news summary written by the market itself.
  2. MEASURE each name's sensitivity to each channel from its own
     history (weekly co-movement, market effect removed). Measured,
     not opined — and labeled as co-movement, never causation.
  3. AGGREGATE to the book: "if oil jumps 10%, my portfolio historically
     moves about X%." Exposure you know about before the shock is risk;
     exposure you discover during the shock is a surprise.
  4. REPLAY history instead of predicting: the stress engine already
     runs your exact book through 2008, COVID and 2022 (a war + energy
     + inflation year — the closest thing to a rehearsal that exists).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dewaag.vault import store

# channel -> (name, kind). kind "pct" = % change; "pts" = change in yield
# points (Yahoo's ^TNX arrives as the yield itself: 4.55 = 4.55%).
CHANNELS: dict[str, tuple[str, str]] = {
    "EURUSD": ("euro vs dollar", "pct"),
    "BRENT":  ("oil (energy / war)", "pct"),
    "GOLD":   ("gold (crisis hedge)", "pct"),
    "US10Y":  ("interest rates (US 10y)", "pts"),
    "VIX":    ("market fear (VIX)", "pct"),
}
# a plain-language shock size per channel, for the "so what" line
SHOCK = {"EURUSD": 0.05, "BRENT": 0.10, "GOLD": 0.10, "US10Y": 0.5, "VIX": 0.25}


def _weekly(symbol: str) -> pd.Series | None:
    try:
        df = store.load_prices(symbol).sort_values("date")
    except FileNotFoundError:
        return None
    s = df.set_index(pd.to_datetime(df["date"]))["adj_close"].astype(float)
    return s.resample("W-FRI").last().dropna()


def _change(symbol: str, level: pd.Series) -> pd.Series:
    kind = CHANNELS[symbol][1]
    return level.diff().dropna() if kind == "pts" else level.pct_change().dropna()


# ---------- 1. the regime: what the channels say right now ----------

def regime() -> list[dict]:
    out = []
    for sym, (label, kind) in CHANNELS.items():
        s = _weekly(sym)
        if s is None or len(s) < 16:
            continue
        level = float(s.iloc[-1])
        chg_1m = float(s.iloc[-1] / s.iloc[-5] - 1) if len(s) >= 5 else None
        chg_3m = float(s.iloc[-1] / s.iloc[-14] - 1) if len(s) >= 14 else None
        row = {"symbol": sym, "label": label, "level": round(level, 2),
               "chg_1m": None if chg_1m is None else round(chg_1m, 4),
               "chg_3m": None if chg_3m is None else round(chg_3m, 4)}
        if sym == "VIX":
            mood = ("calm" if level < 15 else "normal" if level < 20
                    else "nervous" if level < 30 else "stressed")
            row["read"] = f"VIX {level:.0f} — the market is {mood}."
        elif sym == "US10Y":
            row["read"] = f"US 10y yield {level:.2f}% — the price of money; when it rises, long-duration valuations compress."
        elif sym == "BRENT":
            row["read"] = f"Brent ${level:.0f}" + (f", {chg_3m:+.0%} in 3 months" if chg_3m is not None else "") + " — the channel wars and energy shocks arrive through."
        elif sym == "GOLD":
            row["read"] = f"Gold {'' if chg_3m is None else f'{chg_3m:+.0%} in 3 months'} — rising gold usually means the world is buying insurance."
        else:
            row["read"] = f"€1 = ${level:.2f}" + (f", {chg_3m:+.0%} in 3 months" if chg_3m is not None else "") + " — every USD position is also this bet."
        out.append(row)
    return out


# ---------- 2. per-name sensitivities, market effect removed ----------

def sensitivities(symbol: str, years: int = 3) -> list[dict]:
    stock = _weekly(symbol)
    market = _weekly("IWDA")
    if stock is None or market is None:
        return []
    cutoff = stock.index.max() - pd.DateOffset(years=years)
    r_s = stock[stock.index >= cutoff].pct_change().dropna()
    r_m = market.pct_change().dropna()

    idx = r_s.index.intersection(r_m.index)
    if len(idx) < 52:
        return []
    r_s, r_m = r_s[idx], r_m[idx]
    beta_m = float(np.cov(r_s, r_m)[0, 1] / np.var(r_m)) if float(np.var(r_m)) else 0.0
    resid = r_s - beta_m * r_m   # what the name does BEYOND the tide

    out = [{"channel": "IWDA", "label": "world equities (the tide)",
            "beta": round(beta_m, 2), "r": None, "strength": "—",
            "so_what": f"a −10% world market week ≈ {-10 * beta_m:+.1f}% for this name, before anything specific."}]
    for sym in CHANNELS:
        if sym == "IWDA":
            continue
        level = _weekly(sym)
        if level is None:
            continue
        x = _change(sym, level)
        j = resid.index.intersection(x.index)
        if len(j) < 52:
            continue
        a, b = resid[j].to_numpy(), x[j].to_numpy()
        if float(np.var(b)) == 0:
            continue
        beta = float(np.cov(a, b)[0, 1] / np.var(b))
        r = float(np.corrcoef(a, b)[0, 1])
        strength = ("negligible" if abs(r) < 0.10 else "mild" if abs(r) < 0.25
                    else "clear" if abs(r) < 0.45 else "strong")
        shock = SHOCK[sym]
        impact = beta * shock
        unit = f"+{shock:.1f}pt" if CHANNELS[sym][1] == "pts" else f"+{shock:.0%}"
        out.append({"channel": sym, "label": CHANNELS[sym][0],
                    "beta": round(beta, 3), "r": round(r, 2), "strength": strength,
                    "so_what": f"{unit} {CHANNELS[sym][0].split(' (')[0]} historically ≈ {impact:+.1%} here (beyond the market move)."})
    # strongest links first; the tide always stays on top
    return [out[0]] + sorted(out[1:], key=lambda d: -abs(d["r"] or 0))


# ---------- 3. the whole book ----------

def portfolio_exposures() -> dict:
    from dewaag.portfolio import snapshot

    snap = snapshot()
    if not snap["positions"]:
        return {"positions": 0, "note": "empty book — your only macro exposure is the euro in your pocket.", "channels": []}

    weights = {p["symbol"]: p["value_eur"] / snap["equity"] for p in snap["positions"]}
    agg: dict[str, float] = {}
    for sym, w in weights.items():
        for s in sensitivities(sym):
            agg[s["channel"]] = agg.get(s["channel"], 0.0) + w * s["beta"]

    channels = []
    for ch, beta in agg.items():
        label = "world equities (the tide)" if ch == "IWDA" else CHANNELS[ch][0]
        shock = 0.10 if ch == "IWDA" else SHOCK[ch]
        unit = f"+{shock:.1f}pt" if ch != "IWDA" and CHANNELS[ch][1] == "pts" else f"{'-' if ch == 'IWDA' else '+'}{shock:.0%}"
        channels.append({"channel": ch, "label": label, "beta": round(beta, 3),
                         "so_what": f"{unit} {label.split(' (')[0]} ≈ {beta * shock * (-1 if ch == 'IWDA' else 1):+.1%} on your equity."})
    channels.sort(key=lambda d: -abs(d["beta"]))
    return {"positions": len(weights), "invested_weight": round(sum(weights.values()), 3),
            "channels": channels,
            "note": "measured weekly co-movement over ~3y, market effect removed — exposure, not prophecy."}
