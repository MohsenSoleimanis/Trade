import { useEffect, useState } from "react";
import { fmtMoney, get, Portfolio } from "../api";
import { Why } from "../components/Why";

interface SizeResult {
  ok: boolean; reason?: string; risk_budget?: number; loss_per_share?: number;
  shares?: number; investment?: number; worst_case_loss?: number;
  portfolio_value?: number; risk_pct?: number;
}

export function RiskConsole() {
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [entry, setEntry] = useState("50");
  const [wrong, setWrong] = useState("40");
  const [res, setRes] = useState<SizeResult | null>(null);

  useEffect(() => { get<Portfolio>("/api/portfolio").then(setPf).catch(() => {}); }, []);
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
