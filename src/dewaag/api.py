"""De Waag API — Phase 0.

One FastAPI process serves everything: the engine's endpoints and (for now)
a minimal status page. The real React UI arrives in Phase 2; this page exists
so that from the very first commit, `uvicorn dewaag.api:app` boots something
you can open, see, and verify.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from dewaag import __version__
from dewaag.constitution import load_constitution

app = FastAPI(title="De Waag", version=__version__)

MODULES = [
    ("Dashboard", "phase 7"),
    ("Research", "phase 2"),
    ("Screener", "phase 5"),
    ("Risk Console", "phase 3"),
    ("Trading Desk", "phase 3"),
    ("Backtest Lab", "phase 4"),
    ("Agent Floor", "phase 6"),
]


@app.get("/health")
def health() -> dict:
    """Liveness + the one governance fact every caller may need."""
    c = load_constitution()
    return {"status": "ok", "version": __version__, "constitution_signed": c.signed}


@app.get("/api/constitution")
def constitution() -> dict:
    c = load_constitution()
    return {"signed": c.signed, **c.model_dump(mode="json")}


@app.get("/api/vault/status")
def vault_status() -> dict:
    """Phase 1: vault health for the UI — a vault you can't see is a vault
    you won't notice breaking."""
    from dewaag.vault.store import vault_status as _status

    return _status()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    c = load_constitution()
    badge = (
        '<span class="badge ok">SIGNED</span>'
        if c.signed
        else '<span class="badge warn">UNSIGNED — fill config/risk-constitution.yaml</span>'
    )
    rows = "".join(
        f'<div class="ln"><span>{name}</span><span class="mono">{status}</span></div>'
        for name, status in MODULES
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>De Waag</title>
<style>
  :root {{ --bg:#F6F8F6; --surface:#fff; --ink:#1B2420; --muted:#5A6963;
    --line:#DCE3DE; --accent:#1E6B52; --accent-soft:#E3EFE9; --warn:#9C4A3C; --warn-soft:#F6E9E6; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#121815; --surface:#1A211D; --ink:#E7EDEA; --muted:#96A49D;
      --line:#2B342F; --accent:#5CBB95; --accent-soft:#1E3229; --warn:#CE8478; --warn-soft:#33211D; }} }}
  body {{ background:var(--bg); color:var(--ink); font:16px/1.65 "Segoe UI",system-ui,sans-serif;
    margin:0; padding:60px 20px; }}
  .card {{ max-width:560px; margin:0 auto; background:var(--surface); border:1px solid var(--line);
    border-radius:10px; padding:28px 32px; }}
  h1 {{ font-family:Cambria,Georgia,serif; font-size:28px; margin:0 0 2px; }}
  .sub {{ color:var(--muted); font-size:14px; margin-bottom:20px; }}
  .badge {{ font:700 11px Consolas,monospace; padding:2px 10px; border-radius:10px; }}
  .badge.ok {{ background:var(--accent-soft); color:var(--accent); }}
  .badge.warn {{ background:var(--warn-soft); color:var(--warn); }}
  .ln {{ display:flex; justify-content:space-between; padding:7px 0; border-bottom:1px dashed var(--line);
    font-size:14.5px; }}
  .ln:last-child {{ border-bottom:none; }}
  .mono {{ font-family:Consolas,monospace; font-size:12.5px; color:var(--muted); }}
  .law {{ background:var(--accent-soft); border-radius:6px; padding:10px 14px; font-size:13.5px; margin-top:18px; }}
</style></head><body>
<div class="card">
  <h1>&#9878; De Waag <span class="mono">v{__version__}</span></h1>
  <div class="sub">Phase 0 — foundation. Constitution: {badge}</div>
  {rows}
  <div class="law">Risk per idea &le; {c.max_risk_per_idea_pct}% &middot; position cap {c.max_position_pct}%
  &middot; leverage {c.leverage} &middot; drawdown limit &euro;{c.max_drawdown_eur:,.0f}
  &middot; owner: {c.owner}</div>
</div>
</body></html>"""
