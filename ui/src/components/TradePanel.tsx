import { useEffect, useState } from "react";
import { get } from "../api";

// The trade panel — buy/sell directly from the chart page, like a real
// terminal. Live(ish) bid/ask polls every 15s; the same constitution gates
// apply (thesis + exit required on buys). Trading with guardrails, one page.

interface Quote { price: number; bid: number | null; ask: number | null; source: string }
interface SizeResult { ok: boolean; shares?: number; risk_budget?: number }
interface WhatIf {
  before: { vol: number; var95_eur: number | null };
  after: { vol: number; var95_eur: number | null; top_risk: string | null };
}

export function TradePanel({ symbol, currency, lastClose, initialWrong, initialThesis, onFilled }: {
  symbol: string; currency: string; lastClose: number;
  initialWrong?: number; initialThesis?: string; onFilled?: () => void;
}) {
  const [q, setQ] = useState<Quote | null>(null);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [shares, setShares] = useState("");
  const [wrong, setWrong] = useState(initialWrong ? String(initialWrong) : "");
  const [thesis, setThesis] = useState(initialThesis ?? "");
  const [suggest, setSuggest] = useState<number | null>(null);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const sign = currency === "USD" ? "$" : "€";
  const price = q?.price ?? lastClose;

  useEffect(() => {
    let alive = true;
    const poll = () => get<Record<string, Quote>>(`/api/quotes?symbols=${symbol}`)
      .then((r) => alive && r[symbol] && setQ(r[symbol])).catch(() => {});
    poll();
    const id = setInterval(poll, 15000);
    return () => { alive = false; clearInterval(id); };
  }, [symbol]);

  // sizer suggestion whenever the exit changes
  useEffect(() => {
    const w = parseFloat(wrong);
    if (!isFinite(w) || w <= 0 || side !== "BUY") { setSuggest(null); return; }
    get<SizeResult>(`/api/size?entry=${price}&wrong=${w}`)
      .then((r) => setSuggest(r.ok ? r.shares ?? null : null)).catch(() => setSuggest(null));
  }, [wrong, price, side]);

  // pre-trade risk impact (Risk Navigator's what-if) — numbers at the button
  const [whatif, setWhatif] = useState<WhatIf | null>(null);
  useEffect(() => {
    const n = parseInt(shares);
    if (!isFinite(n) || n <= 0) { setWhatif(null); return; }
    get<WhatIf>(`/api/risk/whatif?symbol=${symbol}&side=${side}&shares=${n}`)
      .then(setWhatif).catch(() => setWhatif(null));
  }, [symbol, side, shares]);

  async function submit() {
    setBusy(true); setResult(null);
    try {
      const r = await fetch("/api/order", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol, side, shares: parseInt(shares),
          thesis, wrong_price: wrong ? parseFloat(wrong) : null,
        }),
      });
      const j = await r.json();
      setResult(j.ok
        ? { ok: true, text: `filled — ${shares} ${symbol} @ ~${sign}${price.toFixed(2)}, journaled with your thesis` }
        : { ok: false, text: (j.blocks ?? ["blocked"]).join(" · ") });
      if (j.ok) onFilled?.();
    } finally { setBusy(false); }
  }

  return (
    <div className="card" style={{ minWidth: 250 }}>
      <span className="k">trade — gated, journaled</span>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", margin: "8px 0 2px" }}>
        <span className="v" style={{ fontSize: 21 }}>{sign}{price.toFixed(2)}</span>
        <span className="s mono">{q?.source === "delayed" ? "live · 15min delayed" : "last close"}</span>
      </div>
      <div className="s mono" style={{ marginBottom: 10 }}>
        bid {q?.bid ? sign + q.bid.toFixed(2) : "—"} · ask {q?.ask ? sign + q.ask.toFixed(2) : "—"}
      </div>

      <span className="seg" style={{ width: "100%", display: "flex" }}>
        <button className={`buy ${side === "BUY" ? "on" : ""}`} style={{ flex: 1 }} onClick={() => setSide("BUY")}>BUY</button>
        <button className={`sell ${side === "SELL" ? "on" : ""}`} style={{ flex: 1 }} onClick={() => setSide("SELL")}>SELL</button>
      </span>

      {side === "BUY" && (
        <>
          <div className="frow" style={{ gridTemplateColumns: "1fr" }}>
            <input type="number" placeholder={`"I am wrong at…" e.g. ${(price * 0.8).toFixed(0)}`}
              value={wrong} onChange={(e) => setWrong(e.target.value)} aria-label="exit price" />
          </div>
          <div className="frow" style={{ gridTemplateColumns: "1fr" }}>
            <textarea placeholder="thesis — why this, why now, what proves me wrong"
              value={thesis} onChange={(e) => setThesis(e.target.value)} style={{ minHeight: 46 }} />
          </div>
        </>
      )}
      <div className="frow" style={{ gridTemplateColumns: "1fr" }}>
        <input type="number" placeholder={suggest != null ? `shares (sizer says ${suggest})` : "shares"}
          value={shares} onChange={(e) => setShares(e.target.value)} aria-label="shares" />
      </div>
      {suggest != null && side === "BUY" && (
        <div className="s" style={{ margin: "2px 0 6px" }}>
          <a style={{ cursor: "pointer" }} onClick={() => setShares(String(suggest))}>use sizer: {suggest} shares (1% risk rule)</a>
        </div>
      )}

      {whatif && (
        <div style={{ margin: "6px 0 0" }}>
          <div className="costline"><span>portfolio vol</span>
            <span className="mono">{(whatif.before.vol * 100).toFixed(1)}% → <b>{(whatif.after.vol * 100).toFixed(1)}%</b></span></div>
          <div className="costline"><span>VaR95 / month</span>
            <span className="mono">€{whatif.before.var95_eur ?? 0} → <b>€{whatif.after.var95_eur ?? "—"}</b></span></div>
          {whatif.after.top_risk && (
            <div className="costline"><span>biggest risk after</span><span className="mono">{whatif.after.top_risk}</span></div>
          )}
        </div>
      )}

      <button className="btn" style={{ width: "100%", marginTop: 6 }} onClick={submit}
        disabled={busy || !shares}>{busy ? "placing…" : `${side} ${shares || "—"} ${symbol}`}</button>

      {result && (
        <div className={result.ok ? "okbox" : "blocklist"} style={{ marginTop: 8 }}>{result.text}</div>
      )}
    </div>
  );
}
