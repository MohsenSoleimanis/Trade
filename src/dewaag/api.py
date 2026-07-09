"""De Waag API.

One FastAPI process serves the engine's endpoints AND the built React UI
(ui/dist, when it exists). API routes are declared first, so they always
win; the static mount at "/" catches everything else — which also lets the
hash-router UI own its own navigation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from dewaag import __version__
from dewaag.constitution import load_constitution

app = FastAPI(title="De Waag", version=__version__)

UI_DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"


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
    """The immune system's report — the Dashboard shows it before anything
    else, because a vault you can't see is a vault you won't notice breaking."""
    from dewaag.vault.quality import gate, run_checks

    findings = run_checks()
    return {
        "gate": "PASS" if gate(findings) else "FAIL",
        "findings": findings.to_dict(orient="records"),
    }


@app.get("/api/companies")
def companies() -> list[dict]:
    from dewaag.vault import store

    universe = store.load_universe()
    # one query for everyone's latest price — DuckDB over parquet is fast
    latest = store.query(
        "SELECT symbol, arg_max(close, date) AS price, MAX(date) AS last_date "
        "FROM prices GROUP BY symbol"
    ).set_index("symbol")
    out = []
    for _, row in universe.iterrows():
        sym = row["symbol"]
        price = float(latest.loc[sym, "price"]) if sym in latest.index else None
        out.append({
            "symbol": sym, "name": row["name"], "exchange": row["exchange"],
            "currency": row["currency"], "country": row["country"],
            "tier": row["tier"], "price": price,
            "last_date": str(latest.loc[sym, "last_date"])[:10] if sym in latest.index else None,
        })
    return out


@app.get("/api/company/{symbol}")
def company(symbol: str) -> dict:
    from dewaag.engine.ratios import toolkit
    from dewaag.engine.valuation import snapshot
    from dewaag.vault import store
    from dewaag.vault.fundamentals import load_fundamentals
    from dewaag.vault.quality import check_frame

    universe = store.load_universe().set_index("symbol")
    if symbol not in universe.index:
        raise HTTPException(404, f"unknown symbol {symbol}")
    profile = universe.loc[symbol].to_dict()

    prices = store.load_prices(symbol).sort_values("date")
    last = prices.iloc[-1]

    # chart series: weekly adjusted closes, last 5 years — enough to see
    # the weighing machine without shipping 5,000 points to the browser
    px = prices.copy()
    px["date"] = pd.to_datetime(px["date"])
    px = px.set_index("date")["adj_close"]
    cutoff = px.index.max() - pd.DateOffset(years=5)
    weekly = px[px.index >= cutoff].resample("W-FRI").last().dropna()
    chart = [{"date": str(d.date()), "value": round(float(v), 4)}
             for d, v in weekly.items()]

    fund = load_fundamentals(symbol)
    tk = toolkit(fund)
    latest = tk["latest"] or {}
    val = snapshot(
        price=float(last["close"]),
        net_income=latest.get("net_income"),
        shares=latest.get("shares"),
    )

    findings = check_frame(symbol, prices)

    return {
        "symbol": symbol,
        "profile": profile,
        "last_price": float(last["close"]),
        "last_date": str(last["date"]),
        "currency": profile.get("currency"),
        "chart": chart,
        "toolkit": tk,
        "valuation": val,
        "quality": findings,
        "meta": {
            "source": "yahoo (free)",
            "ingested_at": str(last["ingested_at"]),
            "note": "Free data, current-members universe (survivorship bias) — "
                    "see docs/SETUP-APIS.md for the upgrade path.",
        },
    }


@app.get("/status", response_class=HTMLResponse)
def status_page() -> str:
    """The Phase-0 boot page, kept as a dependency-free fallback."""
    c = load_constitution()
    badge = "SIGNED" if c.signed else "UNSIGNED"
    return (
        f"<html><body style='font-family:system-ui;padding:40px'>"
        f"<h1>&#9878; De Waag v{__version__}</h1>"
        f"<p>constitution: <b>{badge}</b> &middot; risk/idea {c.max_risk_per_idea_pct}% "
        f"&middot; leverage {c.leverage}</p>"
        f"<p>UI: {'built' if UI_DIST.exists() else 'not built yet — run: cd ui && npm run build'}</p>"
        f"</body></html>"
    )


# LAST: the built UI owns every path the API didn't claim.
if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
