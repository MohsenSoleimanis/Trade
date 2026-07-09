import { useEffect, useMemo, useState } from "react";
import { Company, fmtMoney, get, Portfolio } from "../api";
import { Why } from "../components/Why";

interface Preview {
  symbol: string; side: string; tier: string; currency: string;
  last: number; fill: number; shares: number; notional_eur: number;
  costs: { commission: number; half_spread: number; tob: number; total: number; total_pct: number };
  total_eur: number; fill_model: string;
}
interface OrderResult { ok: boolean; blocks?: string[]; trade?: unknown; portfolio?: Portfolio }
interface SizeResult { ok: boolean; shares?: number }

export function TradingDesk({ route }: { route: string }) {
  // #/desk/LOTB pre-selects a symbol (the Company page's Trade button)
  const preselect = route.split("/")[2] ?? "";
  const [companies, setCompanies] = useState<Company[]>([]);
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [symbol, setSymbol] = useState(preselect);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [shares, setShares] = useState("0");
  const [wrong, setWrong] = useState("");
  const [thesis, setThesis] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [result, setResult] = useState<OrderResult | null>(null);
  const [suggest, setSuggest] = useState<number | null>(null);

  const reloadPf = () => get<Portfolio>("/api/portfolio").then(setPf).catch(() => {});
  useEffect(() => {
    get<Company[]>("/api/companies").then((c) => {
      setCompanies(c);
      if (!preselect && c.length) setSymbol(c[0].symbol);
    }).catch(() => {});
    reloadPf();
  }, []);

  const sel = useMemo(() => companies.find((c) => c.symbol === symbol), [companies, symbol]);

  // live suggested size from the backwards sizer whenever the exit changes
  useEffect(() => {
    const w = parseFloat(wrong);
    if (!sel?.price || !isFinite(w) || w <= 0 || side !== "BUY") { setSuggest(null); return; }
    get<SizeResult>(`/api/size?entry=${sel.price}&wrong=${w}`)
      .then((r) => setSuggest(r.ok ? r.shares ?? null : null)).catch(() => setSuggest(null));
  }, [wrong, sel?.price, side]);

  // live cost preview
  useEffect(() => {
    const n = parseInt(shares);
    if (!symbol || !isFinite(n) || n <= 0) { setPreview(null); return; }
    get<Preview>(`/api/order/preview?symbol=${symbol}&side=${side}&shares=${n}`)
      .then(setPreview).catch(() => setPreview(null));
  }, [symbol, side, shares]);

  async function submit() {
    setResult(null);
    const body = {
      symbol, side, shares: parseInt(shares),
      thesis, wrong_price: wrong ? parseFloat(wrong) : null,
    };
    const r = await fetch("/api/order", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j: OrderResult = await r.json();
    setResult(j);
    if (j.ok) { reloadPf(); setShares("0"); setThesis(""); setWrong(""); }
  }

  const sign = sel?.currency === "USD" ? "$" : "€";

  return (
    <>
      <div className="pagehead"><h1>Trading Desk</h1>
        {pf && <span className={`badge ${pf.constitution_signed ? "ok" : "warn"}`}>{pf.constitution_signed ? "DESK OPEN" : "DESK LOCKED — CONSTITUTION UNSIGNED"}</span>}
        <span className="s">paper book · local fills · every order journaled</span>
      </div>
      <p className="pagesub">No thesis, no trade. No budget, no size. The software is calm-you, enforcing rules on excited-you.</p>

      <div className="grid2">
        <div className="card">
          <span className="k">new order</span>
          <div className="frow"><span>symbol</span>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} aria-label="symbol">
              {companies.map((c) => <option key={c.symbol} value={c.symbol}>{c.symbol} — {c.name}</option>)}
            </select></div>
          <div className="frow"><span>side</span>
            <span className="seg">
              <button className={`buy ${side === "BUY" ? "on" : ""}`} onClick={() => setSide("BUY")}>BUY</button>
              <button className={`sell ${side === "SELL" ? "on" : ""}`} onClick={() => setSide("SELL")}>SELL</button>
            </span></div>
          {side === "BUY" && (
            <>
              <div className="frow"><span>"I am wrong at…" {sign}</span>
                <input type="number" value={wrong} placeholder={sel?.price ? `e.g. ${(sel.price * 0.8).toFixed(0)} (−20%)` : ""}
                  onChange={(e) => setWrong(e.target.value)} aria-label="wrong price" /></div>
              <div className="frow"><span>thesis (required)</span>
                <textarea value={thesis} onChange={(e) => setThesis(e.target.value)}
                  placeholder="Why this, why now — and what would prove me wrong. One honest sentence minimum." /></div>
            </>
          )}
          <div className="frow"><span>shares {suggest != null && side === "BUY" && (
            <a onClick={() => setShares(String(suggest))} style={{ cursor: "pointer" }}> (sizer: {suggest})</a>)}</span>
            <input type="number" value={shares} min="0" onChange={(e) => setShares(e.target.value)} aria-label="shares" /></div>

          {preview && (
            <>
              <div className="costline"><span>simulated fill ({preview.tier})</span>
                <span className="mono">{sign}{preview.fill.toFixed(2)} × {preview.shares}</span></div>
              <div className="costline"><span>notional</span><span className="mono">{fmtMoney(preview.notional_eur, "EUR")}</span></div>
              <div className="costline"><span>commission + ½spread + TOB</span>
                <span className="mono">{preview.costs.commission.toFixed(2)} + {preview.costs.half_spread.toFixed(2)} + {preview.costs.tob.toFixed(2)} = {fmtMoney(preview.costs.total, "EUR")} ({(preview.costs.total_pct * 100).toFixed(2)}%)</span></div>
              <div className="costline"><span>{side === "BUY" ? "total cash out" : "net cash in"}</span>
                <span className="mono">{fmtMoney(preview.total_eur, "EUR")}</span></div>
            </>
          )}

          <div style={{ marginTop: 12, display: "flex", gap: 10 }}>
            <button className="btn" onClick={submit} disabled={!preview}>Submit order</button>
            {sel && <a className="btn ghost" href={`#/company/${sel.symbol}`} style={{ textDecoration: "none" }}>research first →</a>}
          </div>

          {result && !result.ok && (
            <div className="blocklist"><b>Blocked by your own rules:</b>
              <ul>{result.blocks!.map((b, i) => <li key={i}>{b}</li>)}</ul>
            </div>
          )}
          {result && result.ok && (
            <div className="okbox">Filled and journaled. The thesis you wrote is now attached to this position forever — future-you will grade it.</div>
          )}
          <Why lesson="Lessons 2 & 6">
            Costs appear BEFORE commitment because everywhere else they're invisible. The fill is simulated
            (last close + half-spread by liquidity tier) until the IBKR paper adapter takes over — same ticket, real order book.
          </Why>
        </div>

        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: "10px 14px 0" }}><span className="k">journal — last trades</span></div>
          {pf && pf.trades.length ? (
            <table className="data">
              <thead><tr><th className="static">When</th><th className="static">Order</th><th className="num static">Fill</th><th className="num static">Costs €</th></tr></thead>
              <tbody>
                {[...pf.trades].reverse().map((t, i) => (
                  <tr key={i}>
                    <td className="s mono">{t.at.slice(0, 10)}</td>
                    <td><span className={`mono ${t.side === "BUY" ? "up" : "down"}`}>{t.side}</span> {t.shares} {t.symbol}</td>
                    <td className="num">{t.fill.toFixed(2)}</td>
                    <td className="num">{t.costs_eur.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="loading" style={{ padding: "16px 14px" }}>no trades yet — the journal starts with your first order</div>
          )}
        </div>
      </div>
    </>
  );
}
