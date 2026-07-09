# De Waag ⚖️

**A personal quant workstation** — research platform, risk engine, backtest lab,
paper-trading desk and AI research floor, for the US and Belgian markets.

*"De Waag" — the weigh house — is the old Flemish building where merchants
weighed goods before trading them. This system weighs before it trades.*

> **Honest frame:** this is the class of software real firms build and sell
> (research + order/risk management + backtesting) — scaled to one owner.
> It promises better decisions, enforced discipline and honest measurement.
> It does not promise predictions. Nothing sane does.

## The rules this system enforces

Everything is gated by [`config/risk-constitution.yaml`](config/risk-constitution.yaml) —
the machine-readable version of the owner's signed Risk Constitution (Curriculum, Lesson 6):

1. Position sizes are computed **backwards from a risk budget** (≤ 1–2% per idea) — never from conviction.
2. No position exceeds its hard cap. No order without a written thesis.
3. Drawdown is tracked **in euros** against the owner's signed limit.
4. **Leverage is zero.** The code refuses to load a constitution that says otherwise.
5. Live trading stays locked until pre-registered paper-trading criteria are met.

## Architecture (short version)

```
React UI  →  FastAPI  →  Deterministic Engine  →  Data Vault (DuckDB + Parquet)
                              ↓ gated by                    ↑ features & briefs only
                    risk-constitution.yaml            Agent Floor (Claude API)
                              ↓
                        IBKR (paper)
```

Full design: [`docs/SYSTEM-BLUEPRINT.html`](docs/SYSTEM-BLUEPRINT.html).
The curriculum that explains every decision lives in [`docs/curriculum/`](docs/curriculum/).

## Quickstart

```powershell
# one-time setup
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
cd ui; npm install; npm run build; cd ..

# fill the vault (free data, ~3 min)
.venv\Scripts\python -m dewaag.vault ingest
.venv\Scripts\python -m dewaag.vault fundamentals
.venv\Scripts\python -m dewaag.vault check

# run the tests
.venv\Scripts\pytest

# start the app
.venv\Scripts\python -m uvicorn dewaag.api:app --port 8420
# → open http://localhost:8420
```

UI development with hot reload: `cd ui && npm run dev` (proxies to the API on 8420).

## Build phases

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Foundation: repo, config system, constitution, boot page | ✅ this commit |
| 1 | Data Vault (Layers 0–1): universe, prices, point-in-time schema | ✅ |
| 2 | Research Workbench: React UI, ratios toolkit, valuation decoder | ✅ |
| 3 | Risk Console + Trading Desk (IBKR paper) | — |
| 4 | Backtest Lab: honest engine + experiment ledger | — |
| 5 | Screener + Book A signals | — |
| 6 | Agent Floor: filings, briefs, literature sweeps | — |
| 7 | Governance: monitoring, kill criteria, attribution | — |
