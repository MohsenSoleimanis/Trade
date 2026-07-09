# External services — what to do, and when

Nothing here is needed today. Each item tells you exactly what to do when its
phase arrives. Until then, De Waag runs 100% free and local.

---

## 1. Market data — needed: Phase 1 (nothing to sign up for)

Phase 1 starts on free sources with no accounts or keys:

- **yfinance / Stooq** — daily prices, pulled by the ingestion jobs directly.
- **SEC EDGAR** — US filings, free public API (we only set a polite `User-Agent`).
- **NBB / FSMA / Euronext** — Belgian filings and reference data, public.

**Later upgrade (optional, ~€30/month, when the Backtest Lab gets serious):**
a survivorship-bias-free history provider (EODHD or Norgate). The vault schema
is provider-agnostic — upgrading is a config change, not a rebuild.

---

## 2. Interactive Brokers — needed: Phase 3 (Trading Desk)

What you do (~30–45 min, free):

1. Go to <https://www.interactivebrokers.ie> → **Open account** (individual).
   Complete the identity verification (ID + proof of address).
   - **TIN question:** for a Belgian resident, your TIN = your **national
     register number** (rijksregisternummer / numéro national), 11 digits,
     format `YY.MM.DD-XXX.XX`. It's on the back of your eID or residence
     permit card, on any Belgian tax letter, or in MyMinfin.be / itsme.
     Tick "I have a Tax Identification Number" and enter it (digits only
     if the form rejects punctuation). Never pick a "no TIN" reason —
     that stalls the review with compliance questions.
2. While reviewing your profile, complete the **W-8BEN** form inside Account
   Management (this is what cuts US dividend tax from 30% to 15% — Lesson 2).
3. Once approved, in the IBKR portal: **Settings → Paper Trading Account** →
   enable it. You get separate paper credentials with fake money.
4. Install **IB Gateway** (lighter than TWS). Log in with the *paper*
   credentials. In its API settings: enable *ActiveX/Socket clients*,
   port **7497** (the paper port), and add `127.0.0.1` to trusted IPs.
5. Tell Claude "IBKR paper is ready" — De Waag connects via `ib_async`
   to `127.0.0.1:7497`. No keys or secrets in the repo; the gateway
   handles authentication.

**Cost: €0.** Live trading stays locked in software until the governance
criteria (Phase 7) are met — regardless of what IBKR would allow.

### Taxes — what actually happens (Belgian resident)

- **Now (paper trading):** nothing. Fake money creates no taxes, no
  declarations, no contact with any authority. The signup's tax questions
  (TIN, residency) feed CRS — the automatic yearly report every regulated
  broker on Earth files ("account exists, balance €X"). With €0 real money
  it says nothing.
- **Only if you later fund with real money** (foreign broker): three small
  duties — declare the foreign account (NBB form + a checkbox on the tax
  return), self-file TOB per trading period, declare dividends. De Waag's
  governance module (Phase 7) computes and tracks these from your own
  trade log. Alternative at that moment: a Belgian broker (zero admin,
  everything withheld — but no API). Decide then, not now.
- Rules changed in 2026 (capital gains tax) — verify current details when
  real money enters. Never skip declarations: CRS means Belgium already
  knows the account exists; the filings are small, fines are not.

---

## 3. Anthropic API (Claude) — needed: Phase 6 (Agent Floor), OPTIONAL

The Agent Floor is built with **pluggable providers**, so this key is optional:

| Mode | What it means | Cost |
|------|---------------|------|
| `session` (default now) | During working sessions, Claude (in Claude Code) reads the vault and writes agent outputs — briefs, extracted features — directly into it. | €0 |
| `mock` | Canned fixtures, used by the test suite. | €0 |
| `claude-api` | Autonomous daily runs via the Anthropic API. Same interfaces — switching is one config line. | ~€10–40/mo |

When you want autonomous mode:

1. Go to <https://console.anthropic.com> → create an account.
2. **Billing** → add a payment method → set a **monthly budget cap**
   (start with $20 — hard caps are a governance habit, not a suggestion).
3. **API Keys** → create key → copy it once.
4. In the repo root, copy `.env.example` to `.env` and paste:
   `ANTHROPIC_API_KEY=sk-ant-...`
   (`.env` is gitignored — keys never enter git history.)
5. In `config/`: set agent provider to `claude-api`. Everything else is unchanged.

---

## 4. Nothing else

No cloud hosting, no databases to rent, no licenses. If you ever want jobs to
run while your PC sleeps: a ~€5/month VPS, but that's a comfort, not a need.
