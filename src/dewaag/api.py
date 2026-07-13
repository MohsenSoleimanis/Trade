"""De Waag API.

API routes are declared first (they always win); the built React UI
(ui/dist) is mounted at "/" last and owns everything else.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dewaag import __version__
from dewaag.constitution import load_constitution

app = FastAPI(title="De Waag", version=__version__)

UI_DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"

# ---------------------------------------------------------------- core

@app.get("/health")
def health() -> dict:
    c = load_constitution()
    return {"status": "ok", "version": __version__, "constitution_signed": c.signed}


@app.get("/api/constitution")
def constitution() -> dict:
    c = load_constitution()
    return {"signed": c.signed, **c.model_dump(mode="json")}


@app.get("/api/vault/status")
def vault_status() -> dict:
    from dewaag.vault.store import vault_status as _status

    return _status()


@app.get("/api/vault/quality")
def vault_quality() -> dict:
    from dewaag.vault.quality import gate, run_checks

    findings = run_checks()
    return {"gate": "PASS" if gate(findings) else "FAIL",
            "findings": findings.to_dict(orient="records")}


# ------------------------------------------------------------ research

_companies_cache: dict = {"key": None, "data": None}


@app.get("/api/companies")
def companies() -> list[dict]:
    """Universe enriched with market-grade columns: day change, 1y return,
    30-day sparkline, market cap. Cached per vault-day (45 names, one query)."""
    from dewaag.vault import store
    from dewaag.vault.fundamentals import load_fundamentals

    tail = store.query(
        "SELECT symbol, date, close, adj_close FROM prices "
        "QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY date DESC) <= 260 "
        "ORDER BY symbol, date"
    )
    cache_key = str(tail["date"].max())
    if _companies_cache["key"] == cache_key:
        return _companies_cache["data"]

    universe = store.load_universe()
    out = []
    for _, row in universe.iterrows():
        sym = row["symbol"]
        if row["tier"] in ("fx", "macro"):
            continue
        t = tail[tail["symbol"] == sym]
        price = day = ret1y = mcap = None
        spark: list[float] = []
        if len(t) >= 2:
            price = float(t["close"].iloc[-1])
            day = float(t["adj_close"].iloc[-1] / t["adj_close"].iloc[-2] - 1)
            base = t["adj_close"].iloc[0]
            ret1y = float(t["adj_close"].iloc[-1] / base - 1) if base else None
            spark = [round(float(v), 3) for v in t["adj_close"].tail(22)]
            fund = load_fundamentals(sym)
            shares = fund[fund["item"] == "shares"].sort_values("period_end")
            if len(shares):
                mcap = price * float(shares["value"].iloc[-1])
        out.append({
            "symbol": sym, "name": row["name"], "exchange": row["exchange"],
            "currency": row["currency"], "country": row["country"], "tier": row["tier"],
            "price": price, "day_change": day, "ret_1y": ret1y,
            "market_cap": mcap, "spark": spark,
        })
    _companies_cache.update(key=cache_key, data=out)
    return out


@app.get("/api/company/{symbol}")
def company(symbol: str, range: str = "5y") -> dict:
    from dewaag.engine.ratios import toolkit
    from dewaag.engine.valuation import snapshot as val_snapshot
    from dewaag.vault import store
    from dewaag.vault.fundamentals import load_fundamentals
    from dewaag.vault.quality import check_frame

    universe = store.load_universe().set_index("symbol")
    if symbol not in universe.index:
        raise HTTPException(404, f"unknown symbol {symbol}")
    profile = universe.loc[symbol].to_dict()

    prices = store.load_prices(symbol).sort_values("date")
    last = prices.iloc[-1]
    prev = prices.iloc[-2] if len(prices) > 1 else last

    px = prices.copy()
    px["date"] = pd.to_datetime(px["date"])
    px = px.set_index("date")["adj_close"]
    years = {"1y": 1, "3y": 3, "5y": 5, "max": 100}.get(range, 5)
    cutoff = px.index.max() - pd.DateOffset(years=years)
    sel = px[px.index >= cutoff]
    freq = "D" if years <= 1 else "W-FRI"
    series = sel.resample(freq).last().dropna()
    chart = [{"date": str(d.date()), "value": round(float(v), 4)} for d, v in series.items()]

    yr = px[px.index >= px.index.max() - pd.DateOffset(years=1)]

    # raw OHLC + volume for the candlestick view (last ~9 months, daily) —
    # raw close, not adjusted: candles show what you'd actually have paid
    ohlc = prices.tail(190)
    candles = [{"time": str(r["date"]), "open": round(float(r["open"]), 4),
                "high": round(float(r["high"]), 4), "low": round(float(r["low"]), 4),
                "close": round(float(r["close"]), 4),
                "volume": int(r["volume"]) if pd.notna(r["volume"]) else 0}
               for _, r in ohlc.iterrows()]

    from dewaag.engine.signals import engine_read
    engine = engine_read(symbol)

    fund = load_fundamentals(symbol)
    tk = toolkit(fund)
    latest = tk["latest"] or {}
    val = val_snapshot(price=float(last["close"]),
                       net_income=latest.get("net_income"),
                       shares=latest.get("shares"))
    return {
        "symbol": symbol, "profile": profile,
        "last_price": float(last["close"]), "last_date": str(last["date"]),
        "day_change": float(last["adj_close"] / prev["adj_close"] - 1),
        "high_52w": round(float(yr.max()), 2), "low_52w": round(float(yr.min()), 2),
        "currency": profile.get("currency"), "range": range, "chart": chart,
        "candles": candles,
        "engine": engine, "toolkit": tk, "valuation": val,
        "quality": check_frame(symbol, prices),
        "meta": {
            "source": "yahoo (free)", "ingested_at": str(last["ingested_at"]),
            "note": "Free data, current-members universe (survivorship bias) — "
                    "see docs/SETUP-APIS.md for the upgrade path.",
        },
    }


@app.get("/api/company/{symbol}/outlook")
def outlook(symbol: str) -> dict:
    """The forward half of the page: live news + street expectations.
    Served separately so the Stage renders instantly and this fills in
    when the (slower, network-bound) feeds answer. Both cached on disk."""
    from dewaag.vault import store
    from dewaag.vault.forward import get_forward
    from dewaag.vault.news import get_news

    universe = store.load_universe().set_index("symbol")
    if symbol not in universe.index:
        raise HTTPException(404, f"unknown symbol {symbol}")
    tier = str(universe.loc[symbol, "tier"])

    fwd = get_forward(symbol) if tier != "etf" else {"available": False,
        "note": "an index fund has no analyst estimates — its forward view is the world economy itself"}
    news = get_news(symbol)

    from dewaag.engine.macro import sensitivities
    macro = sensitivities(symbol)

    # plain-language read of the street numbers, same voice as the engine
    bullets: list[str] = []
    if fwd.get("available") and fwd.get("target_mean"):
        n = fwd.get("analysts")
        bullets.append(
            f"{n or 'Some'} analysts cover this name — "
            + ("crowded water: hard to know something they don't." if (n or 0) >= 20
               else "thin coverage: exactly where small edges can hide." if (n or 99) <= 5
               else "moderate coverage."))
        if fwd.get("street_eps_growth") is not None:
            g = fwd["street_eps_growth"]
            bullets.append(
                f"The street expects earnings per share to move {g:+.0%} over the next year. "
                "That expectation is already in today's price — the stock moves on whether reality beats it.")
        bullets.append(
            "Price targets are opinions, and historically optimistic on average. "
            "The spread between the low and high target tells you how much analysts disagree — "
            "wide disagreement means high uncertainty, whatever the mean says.")
    return {"symbol": symbol, "forward": fwd, "news": news, "read": bullets,
            "macro": macro}


@app.get("/api/macro")
def macro() -> dict:
    """The world lens: regime (what the channel prices say now), the book's
    measured exposures, and the world wire. War/climate/rates never appear
    as predictions here — only as channels, sensitivities and rehearsals."""
    from dewaag.engine.macro import portfolio_exposures, regime
    from dewaag.vault.news import get_macro_news

    return {"regime": regime(), "book": portfolio_exposures(),
            "wire": get_macro_news(),
            "how_to_read": "Channel prices digest world news in minutes — this is the market's own summary. "
                           "Sensitivities are measured co-movement (~3y weekly, market removed), not causation. "
                           "For 'what would a shock do', the stress tab replays 2008 / COVID / 2022 on your exact book."}


# ------------------------------------------------------ the engine

@app.get("/api/signals")
def signals() -> list[dict]:
    """The whole universe, scored by the engine (quality/value/momentum/composite)."""
    import numpy as np

    from dewaag.engine.signals import compute_signals

    df = compute_signals().replace({np.nan: None})
    cols = ["symbol", "name", "country", "tier", "currency", "price",
            "ret_1m", "ret_12m", "mom_12_1", "vol_1y", "max_dd_1y", "beta_1y",
            "pe", "earnings_yield", "roe_avg", "dte", "cash_conv_avg", "rev_growth",
            "above_200d", "pos_52w", "q_score", "v_score", "m_score", "composite", "coverage"]
    return df[cols].to_dict(orient="records")


@app.get("/api/brief")
def brief() -> list[dict]:
    """The engine briefing — what the machine found on its own."""
    from dewaag.engine.insights import briefing

    return briefing()


# ------------------------------------------------------ autopilot

class AutoAction(BaseModel):
    symbol: str
    action: str
    shares: int
    wrong_price: float | None = None
    thesis: str = ""


@app.get("/api/autopilot/plan")
def autopilot_plan() -> dict:
    """The narrated plan — what the system would do, and WHY, in plain words."""
    from dewaag.autopilot import generate_plan

    return generate_plan()


@app.post("/api/autopilot/execute")
def autopilot_execute(a: AutoAction) -> dict:
    """Run one approved action through the gated executor."""
    from dewaag.autopilot import execute_action

    return execute_action(a.model_dump())


@app.post("/api/autopilot/run")
def autopilot_run() -> dict:
    """Full-auto (paper only): execute the whole plan. Off unless config allows."""
    from dewaag.autopilot import run_auto

    return run_auto()


# ------------------------------------------------------ today surface

@app.get("/api/today")
def today() -> dict:
    """The cockpit payload: jobs, alerts, calendar, brief, tasks, portfolio."""
    import json as _json

    from dewaag.engine.alerts import compute_alerts
    from dewaag.jobs import status as jobs_status
    from dewaag.pipeline import tasks as pipeline_tasks
    from dewaag.portfolio import snapshot
    from dewaag.vault.calendar import upcoming
    from dewaag.vault.store import DATA_DIR

    pf = snapshot()
    tasks = pipeline_tasks()
    c = load_constitution()
    if not c.signed:
        tasks.insert(0, {"kind": "setup", "card": None, "symbol": None,
                         "text": "Sign your Risk Constitution — the desk stays locked until the euro drawdown limit is yours, not a template's"})

    brief_path = DATA_DIR / "brief.json"
    brief = _json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else {"at": None, "items": []}

    return {
        "jobs": jobs_status(),
        "alerts": compute_alerts(),
        "calendar": upcoming(14),
        "brief": brief,
        "tasks": tasks,
        "portfolio": {"equity": pf["equity"], "pnl": pf["pnl_since_start"],
                      "drawdown_eur": pf["drawdown_eur"], "drawdown_limit_eur": pf["drawdown_limit_eur"],
                      "positions": len(pf["positions"]), "signed": pf["constitution_signed"]},
    }


# ------------------------------------------------------ pipeline

class CardAdd(BaseModel):
    symbol: str
    source: str = "manual"
    note: str = ""


class CardAdvance(BaseModel):
    thesis: str = ""
    wrong_price: float | None = None


class CardPass(BaseModel):
    reason: str


class CardGrade(BaseModel):
    grade: str
    note: str = ""


@app.get("/api/pipeline")
def pipeline_list() -> list[dict]:
    from dewaag.pipeline import load as load_cards

    return load_cards()


@app.post("/api/pipeline/add")
def pipeline_add(body: CardAdd) -> dict:
    from dewaag.pipeline import add_card

    try:
        return add_card(body.symbol.upper(), body.source, body.note)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/pipeline/{card_id}/advance")
def pipeline_advance(card_id: str, body: CardAdvance) -> dict:
    from dewaag.pipeline import advance

    try:
        return advance(card_id, thesis=body.thesis, wrong_price=body.wrong_price)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/pipeline/{card_id}/pass")
def pipeline_pass(card_id: str, body: CardPass) -> dict:
    from dewaag.pipeline import pass_card

    try:
        return pass_card(card_id, body.reason)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/pipeline/{card_id}/grade")
def pipeline_grade(card_id: str, body: CardGrade) -> dict:
    from dewaag.pipeline import grade

    try:
        return grade(card_id, body.grade, body.note)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e)) from e


# ------------------------------------------------------ constitution signing

class SignBody(BaseModel):
    max_drawdown_eur: float
    emergency_fund_months: int = 6
    strategy_statement: str = ""


@app.post("/api/constitution/sign")
def sign_constitution(body: SignBody) -> dict:
    """The onboarding fix: the constitution is signed in the product,
    with a proper flow — never again by editing YAML. Scalar fields are
    replaced in-place so the file's teaching comments survive."""
    import re
    from datetime import date as _date

    from dewaag.constitution import DEFAULT_PATH

    if body.max_drawdown_eur <= 0:
        raise HTTPException(400, "the euro drawdown limit must be a real number you chose — that's the signature")
    if body.emergency_fund_months < 3:
        raise HTTPException(400, "emergency fund below 3 months fails §4 — never invest money with a deadline")

    text = DEFAULT_PATH.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^signed_on:.*$", f'signed_on: "{_date.today().isoformat()}"', text)
    text = re.sub(r"(?m)^max_drawdown_eur:.*$", f"max_drawdown_eur: {body.max_drawdown_eur:.0f}", text)
    text = re.sub(r"(?m)^emergency_fund_months:.*$", f"emergency_fund_months: {body.emergency_fund_months}", text)
    if body.strategy_statement.strip():
        stmt = "\n".join("  " + line for line in body.strategy_statement.strip().splitlines())
        text = re.sub(r"(?ms)^strategy_statement: \|.*\Z", f"strategy_statement: |\n{stmt}\n", text)
    DEFAULT_PATH.write_text(text, encoding="utf-8")

    c = load_constitution()
    return {"signed": c.signed, "signed_on": str(c.signed_on), "max_drawdown_eur": c.max_drawdown_eur}


# ------------------------------------------------------ risk engine

@app.get("/api/risk")
def risk_report() -> dict:
    """Portfolio risk analytics: vol, VaR/ES, contributions, exposure,
    historical stress replays — the Risk Navigator/PORT layer."""
    from dewaag.engine.risk import portfolio_report

    return portfolio_report()


@app.get("/api/risk/whatif")
def risk_whatif(symbol: str, side: str, shares: int) -> dict:
    """Pre-trade what-if: how this order changes portfolio risk."""
    from dewaag.engine.risk import what_if

    try:
        return what_if(symbol, side.upper(), shares)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ------------------------------------------------------ backtest lab

class BacktestIn(BaseModel):
    strategy: str = "mom_12_1"   # mom_12_1 | equal_weight
    top_n: int = 8
    start_year: int = 2006
    capital: float = 10_000.0


@app.post("/api/backtest")
def backtest(cfg: BacktestIn) -> dict:
    from dewaag.engine.backtest import run_from_vault

    if cfg.strategy not in ("mom_12_1", "equal_weight"):
        raise HTTPException(400, "unknown strategy")
    if not (2 <= cfg.top_n <= 20):
        raise HTTPException(400, "top_n must be 2..20")
    return run_from_vault(cfg.strategy, cfg.top_n, cfg.start_year, cfg.capital)


@app.get("/api/backtest/ledger")
def backtest_ledger() -> list[dict]:
    from dewaag.engine.backtest import ledger

    return ledger()


# ------------------------------------------------- portfolio & trading

class OrderIn(BaseModel):
    symbol: str
    side: str  # BUY | SELL
    shares: int
    thesis: str = ""
    wrong_price: float | None = None


@app.get("/api/portfolio")
def portfolio() -> dict:
    from dewaag.portfolio import snapshot

    return snapshot()


# ------------------------------------------------------ agent floor

class BriefIn(BaseModel):
    symbol: str
    summary: str
    bull_case: str
    bear_case: str
    verify: str
    verdict: str
    author: str = "claude-session"
    inputs: list[str] = []


@app.get("/api/agent/brief/{symbol}")
def agent_brief(symbol: str) -> dict:
    from dewaag.agent import load_brief

    b = load_brief(symbol)
    return b or {"symbol": symbol, "missing": True}


@app.post("/api/agent/brief")
def agent_brief_save(b: BriefIn) -> dict:
    from dewaag.agent import save_brief

    try:
        return save_brief(b.symbol, b.model_dump(), author=b.author, inputs=b.inputs)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/agent/context/{symbol}")
def agent_context(symbol: str) -> dict:
    """The agent's reading desk: everything the system remembers about a name."""
    from dewaag.agent import context_pack

    return context_pack(symbol)


@app.get("/api/agent/memory")
def agent_memory(n: int = 50) -> list[dict]:
    from dewaag.agent import recall

    return recall(n)


# ------------------------------------------------------ the autonomous engine (L0–L9)

class ProposalAction(BaseModel):
    id: str
    reason: str = ""


@app.get("/api/auto/plan")
def auto_plan(rebuild: bool = False) -> dict:
    """Run the ten-layer brain (or return the last plan). Produces the ideal
    target portfolio + the concrete, gated proposals awaiting your approval."""
    from dewaag.engine.auto import proposals as store_
    from dewaag.engine.auto.pipeline import build_plan

    if not rebuild:
        cached = store_.load_plan()
        if cached:
            return cached
    return build_plan()


@app.get("/api/auto/regime")
def auto_regime() -> dict:
    """L2 only — the market weather, fast (no full pipeline)."""
    from dewaag.engine.auto.regime import classify
    from dewaag.engine.signals import compute_signals

    return classify(compute_signals())


@app.post("/api/auto/approve")
def auto_approve(a: ProposalAction) -> dict:
    """L9 — the one human touch. Routes the trade through the real gates."""
    from dewaag.engine.auto.proposals import approve

    return approve(a.id)


@app.post("/api/auto/reject")
def auto_reject(a: ProposalAction) -> dict:
    """L9 — reject a proposal; the reason becomes training data (L8 memory)."""
    from dewaag.engine.auto.proposals import reject

    return reject(a.id, a.reason)


@app.get("/api/auto/decisions")
def auto_decisions(n: int = 100) -> list[dict]:
    from dewaag.engine.auto.proposals import decision_history

    return decision_history(n)


@app.get("/api/auto/book")
def auto_book() -> dict:
    """The engine's OWN autonomous, simulated book — its track record.
    Separate from your personal account on purpose."""
    from dewaag.engine.auto.book import snapshot

    return snapshot()


@app.get("/api/auto/console")
def auto_console(rebuild: bool = False) -> dict:
    """Rich, visualizable data for every layer — the Jarvis console feed."""
    from dewaag.engine.auto.console import build_console

    return build_console(rebuild=rebuild)


@app.get("/api/forecast/{symbol}")
def forecast_symbol(symbol: str, horizon: int = 21) -> dict:
    """Honest forecast: the likely RANGE (not direction) for one instrument."""
    from dewaag.engine.auto.forecast import expected_range

    return expected_range(symbol, horizon_days=horizon)


@app.get("/api/auto/forecast")
def forecast_book(horizon: int = 21) -> dict:
    """The engine book's likely value range next month (risk, not direction)."""
    from dewaag.engine.auto.forecast import book_forecast

    return book_forecast(horizon_days=horizon)


@app.get("/api/position/{symbol}/proceeds")
def position_proceeds(symbol: str) -> dict:
    """'If I sell now, what lands in my pocket?' — the Belgian answer:
    spread + TOB + commission + 2026 capital-gains tax, as a range."""
    from dewaag.engine.taxes import sale_proceeds
    from dewaag.portfolio import _eurusd, _mark_price, load_state
    from dewaag.vault import store

    state = load_state()
    pos = state["positions"].get(symbol)
    if not pos:
        raise HTTPException(404, f"no position in {symbol}")
    u = store.load_universe().set_index("symbol")
    currency = str(u.loc[symbol, "currency"]) if symbol in u.index else "EUR"
    tier = str(u.loc[symbol, "tier"]) if symbol in u.index else "mid"
    fx = 1.0 / _eurusd() if currency == "USD" else 1.0
    return sale_proceeds(shares=pos["shares"], mark_price_native=_mark_price(symbol),
                         fx_to_eur=fx, tier=tier, avg_cost_eur=pos["avg_cost_eur"])


@app.get("/api/quotes")
def quotes(symbols: str) -> dict:
    """Delayed live quotes (via TWS when running; vault close otherwise).
    The UI polls this to stay alive: ?symbols=COLR,MELE,IWDA"""
    from dewaag.broker import get_quotes

    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:30]
    return get_quotes(syms)


@app.get("/api/broker/status")
def broker_status() -> dict:
    """Which venue fills your orders, and is it reachable. When IBKR is
    connected, also reconcile: our book of record vs the broker's truth."""
    from dewaag.broker import ibkr_status
    from dewaag.portfolio import snapshot

    st = ibkr_status()
    if st.get("connected"):
        try:
            from dewaag.broker import IB_SYMBOL, ibkr_positions

            reverse = {v: k for k, v in IB_SYMBOL.items()}
            ib_pos = {reverse.get(p["ib_symbol"], p["ib_symbol"]): p["shares"] for p in ibkr_positions()}
            ours = {p["symbol"]: p["shares"] for p in snapshot()["positions"]}
            mismatches = []
            for sym in set(ib_pos) | set(ours):
                if abs(ib_pos.get(sym, 0) - ours.get(sym, 0)) > 0.001:
                    mismatches.append({"symbol": sym, "ibkr": ib_pos.get(sym, 0), "local": ours.get(sym, 0)})
            st["mismatches"] = mismatches
        except Exception as e:  # noqa: BLE001
            st["mismatches_error"] = str(e)[:120]
    return st


@app.get("/api/order/preview")
def order_preview(symbol: str, side: str, shares: int) -> dict:
    from dewaag.portfolio import preview

    try:
        return preview(symbol, side.upper(), shares)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/order")
def place_order(order: OrderIn) -> dict:
    from dewaag.portfolio import execute

    return execute(order.symbol, order.side.upper(), order.shares,
                   thesis=order.thesis, wrong_price=order.wrong_price)


@app.get("/api/size")
def size(entry: float, wrong: float) -> dict:
    """The backwards sizing calculator — Risk Console's core."""
    from dewaag.engine.sizing import backwards_size
    from dewaag.portfolio import snapshot

    c = load_constitution()
    equity = snapshot()["equity"]
    result = backwards_size(equity, c.max_risk_per_idea_pct, entry, wrong)
    result["portfolio_value"] = equity
    result["risk_pct"] = c.max_risk_per_idea_pct
    return result


# ---------------------------------------------------------------- misc

@app.get("/status", response_class=HTMLResponse)
def status_page() -> str:
    c = load_constitution()
    badge = "SIGNED" if c.signed else "UNSIGNED"
    return (
        f"<html><body style='font-family:system-ui;padding:40px'>"
        f"<h1>&#9878; De Waag v{__version__}</h1>"
        f"<p>constitution: <b>{badge}</b> &middot; risk/idea {c.max_risk_per_idea_pct}% "
        f"&middot; leverage {c.leverage}</p>"
        f"<p>UI: {'built' if UI_DIST.exists() else 'not built — cd ui && npm run build'}</p>"
        f"</body></html>"
    )


if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
