import { useEffect, useState } from "react";
import { fmtMoney, get, Portfolio } from "../api";
import { Why } from "../components/Why";

const fmtPctS = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

interface SizeResult {
  ok: boolean; reason?: string; risk_budget?: number; loss_per_share?: number;
  shares?: number; investment?: number; worst_case_loss?: number;
  portfolio_value?: number; risk_pct?: number;
}

interface RiskReport {
  empty: boolean; equity: number; note?: string;
  portfolio_vol?: number | null; weighted_avg_vol?: number | null; diversification_gain?: number | null;
  invested_weight?: number; cash_weight?: number;
  var?: { horizon: string; var95_parametric: number; var95_hist: number; var99_hist: number; es95_hist: number | null };
  contributions?: Record<string, number>;
  exposure?: { currency: Record<string, number>; country: Record<string, number>; tier: Record<string, number> };
  stress?: { scenario: string; portfolio_return: number; loss_eur: number; coverage: number }[];
  caveat?: string;
}

export function RiskConsole() {
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [entry, setEntry] = useState("50");
  const [wrong, setWrong] = useState("40");
  const [res, setRes] = useState<SizeResult | null>(null);
  const [rr, setRr] = useState<RiskReport | null>(null);

  useEffect(() => {
    get<Portfolio>("/api/portfolio").then(setPf).catch(() => {});
    get<RiskReport>("/api/risk").then(setRr).catch(() => {});
  }, []);
  useEffect(() => {
    const e = parseFloat(entry), w = parseFloat(wrong);
    if (!isFinite(e) || !isFinite(w) || e <= 0) { setRes(null); return; }
    get<SizeResult>(`/api/size?entry=${e}&wrong=${w}`).then(setRes).catch(() => setRes(null));
  }, [entry, wrong]);

  const dd = pf?.drawdown_eur ?? 0;
  const ddLim = pf?.drawdown_limit_eur ?? 0;
  const riskShare = pf ? pf.open_risk_eur / (pf.equity || 1) : 0;

  return (
    <>
      <div className="pagehead"><h1>Risk Console</h1>
        {pf && <span className={`badge ${pf.constitution_signed ? "ok" : "warn"}`}>{pf.constitution_signed ? "SIGNED" : "UNSIGNED"}</span>}
      </div>
      <p className="pagesub">The only lever you fully control. Sizes come from the risk budget — conviction is not an input anywhere on this page.</p>

      {rr && !rr.empty && (
        <>
          <div className="cards" style={{ marginBottom: 12 }}>
            <div className="card">
              <span className="k">portfolio volatility</span>
              <span className="v">{fmtPctS(rr.portfolio_vol)}</span>
              <div className="s">holdings alone would be {fmtPctS(rr.weighted_avg_vol)} — diversification saves {fmtPctS(rr.diversification_gain)}</div>
            </div>
            <div className="card">
              <span className="k">VaR 95 · 1 month</span>
              <span className="v">€{rr.var?.var95_hist?.toLocaleString() ?? "—"}</span>
              <div className="s">from actual history · parametric says €{rr.var?.var95_parametric?.toLocaleString()} — when they disagree, trust the fatter tail</div>
            </div>
            <div className="card">
              <span className="k">expected shortfall 95</span>
              <span className="v">€{rr.var?.es95_hist?.toLocaleString() ?? "—"}</span>
              <div className="s">average loss WHEN the bad 5% happens · VaR99 €{rr.var?.var99_hist?.toLocaleString()}</div>
            </div>
            <div className="card">
              <span className="k">invested / cash</span>
              <span className="v">{fmtPctS(rr.invested_weight)} / {fmtPctS(rr.cash_weight)}</span>
              <div className="s">of €{rr.equity.toLocaleString()} equity</div>
            </div>
          </div>

          <div className="grid2" style={{ marginBottom: 12 }}>
            <div className="card">
              <span className="k">where the risk lives — contribution to portfolio risk</span>
              {Object.entries(rr.contributions ?? {}).sort((a, b) => b[1] - a[1]).map(([sym, c]) => (
                <div key={sym} className="costline">
                  <span className="mono">{sym}</span>
                  <span style={{ flex: 1, margin: "0 12px" }}><div className="meter" style={{ margin: 0 }}><div style={{ width: `${Math.min(100, c * 100)}%` }} /></div></span>
                  <span className="mono">{(c * 100).toFixed(0)}%</span>
                </div>
              ))}
              <Why lesson="Lesson 6 §4">Money weight ≠ risk weight: one wild position can carry most of the portfolio's risk. This is Risk Navigator's drill-down, computed from your holdings' covariance.</Why>
            </div>
            <div className="card">
              <span className="k">stress replays — your weights through real history</span>
              {(rr.stress ?? []).map((s, i) => (
                <div key={i} className="costline">
                  <span style={{ flex: 1 }}>{s.scenario}{s.coverage < 1 && <span className="s"> ({(s.coverage * 100).toFixed(0)}% covered)</span>}</span>
                  <span className="mono down">−€{Math.abs(s.loss_eur).toLocaleString()} ({(s.portfolio_return * 100).toFixed(0)}%)</span>
                </div>
              ))}
              <div className="s" style={{ marginTop: 8 }}>{rr.caveat}</div>
              <Why lesson="Lessons 5 & 6">Bloomberg PORT calls this scenario analysis: your CURRENT portfolio pushed through 2008, COVID and 2022. Ask the only question that matters: could you watch that euro number and not sell?</Why>
            </div>
          </div>

          <div className="cards" style={{ marginBottom: 12 }}>
            {(["currency", "country", "tier"] as const).map((k) => (
              <div className="card" key={k}>
                <span className="k">exposure by {k}</span>
                {Object.entries(rr.exposure?.[k] ?? {}).map(([key, w]) => (
                  <div key={key} className="costline"><span className="mono">{key}</span><span className="mono">{(w * 100).toFixed(0)}%</span></div>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
      {rr && rr.empty && (
        <div className="card" style={{ marginBottom: 12 }}>
          <span className="k">portfolio risk</span>
          <p style={{ margin: "6px 0 0", fontSize: 13 }}>{rr.note} Once positions exist, this page shows volatility, VaR, risk contributions, exposures and stress replays of 2008/COVID/2022 on your actual weights.</p>
        </div>
      )}

      <div className="grid2">
        <div className="card">
          <span className="k">the backwards sizer — lesson 6 §3</span>
          <div className="frow"><span>entry price</span>
            <input type="number" value={entry} min="0" step="0.5" onChange={(e) => setEntry(e.target.value)} aria-label="entry price" /></div>
          <div className="frow"><span>"I am wrong at…"</span>
            <input type="number" value={wrong} min="0" step="0.5" onChange={(e) => setWrong(e.target.value)} aria-label="wrong price" /></div>

          {res && res.ok && (
            <>
              <div className="costline"><span>portfolio value</span><span className="mono">{fmtMoney(res.portfolio_value!, "EUR")}</span></div>
              <div className="costline"><span>risk budget ({res.risk_pct}%)</span><span className="mono">{fmtMoney(res.risk_budget!, "EUR")}</span></div>
              <div className="costline"><span>loss per share</span><span className="mono">{res.loss_per_share!.toFixed(2)}</span></div>
              <div className="costline"><span>max shares · investment</span>
                <span className="mono"><b>{res.shares}</b> · {fmtMoney(res.investment!, "EUR")}</span></div>
              <div className="okbox">Worst planned case: <b>−{fmtMoney(res.worst_case_loss!, "EUR")}</b> = your budget. Painful, survivable, planned — you can be wrong many times in a row and still be in the game.</div>
            </>
          )}
          {res && !res.ok && <div className="blocklist">{res.reason}</div>}
          <Why lesson="Lesson 6">Budget ÷ loss-per-share = shares. Wilder exits automatically shrink positions — that's the method protecting you from your own excitement. These numbers pre-fill the Trading Desk ticket.</Why>
        </div>

        <div className="card">
          <span className="k">exposure &amp; drawdown</span>
          <div className="costline"><span>equity</span><span className="mono">{pf ? fmtMoney(pf.equity, "EUR") : "…"}</span></div>
          <div className="costline"><span>invested / cash</span>
            <span className="mono">{pf ? `${fmtMoney(pf.invested, "EUR")} / ${fmtMoney(pf.cash, "EUR")}` : "…"}</span></div>
          <div className="costline"><span>open risk (sum to "wrong")</span>
            <span className="mono">{pf ? `${fmtMoney(pf.open_risk_eur, "EUR")} (${(riskShare * 100).toFixed(1)}%)` : "…"}</span></div>

          <span className="k" style={{ marginTop: 14 }}>drawdown vs your signed limit</span>
          <div className="meter"><div className={ddLim && dd / ddLim > 0.7 ? "hot" : ""}
            style={{ width: `${ddLim ? Math.min(100, (dd / ddLim) * 100) : 0}%` }} /></div>
          <div className="s">
            {ddLim
              ? `€${dd.toLocaleString()} of €${ddLim.toLocaleString()} — ${dd / ddLim > 0.7 ? "approaching the line you drew while calm. Re-read your constitution before any new position." : "comfortable."}`
              : "no euro limit set — the constitution is unsigned, and this meter is blind."}
          </div>
          <Why lesson="Lesson 6, trap #1">Drawdown is measured in euros, not percent, against the number you signed — because your behavior runs on euros. When this meter runs hot, the correct response is smaller sizes, never faster trading.</Why>

          {pf && pf.positions.length > 0 && (
            <>
              <span className="k" style={{ marginTop: 14 }}>per-position risk</span>
              {pf.positions.map((p) => (
                <div key={p.symbol} className="costline">
                  <span className="mono">{p.symbol} <span className="s">wrong @ {p.wrong_price ?? "—"}</span></span>
                  <span className="mono">{fmtMoney(p.value_eur, "EUR")}</span>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </>
  );
}
