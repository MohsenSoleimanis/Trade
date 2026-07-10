import { useEffect, useState } from "react";
import { get } from "../api";

interface Action {
  action: "BUY" | "SELL"; symbol: string; name: string; sector?: string;
  currency?: string; shares: number; entry: number; wrong_price: number | null;
  cost_eur?: number; position_eur?: number;
  scores?: { q_score: number | null; v_score: number | null; m_score: number | null; composite: number | null };
  reason_code: string; thesis: string; narration: string[];
}
interface Plan {
  signed: boolean; intro: string[]; sells: Action[]; buys: Action[];
  settings: { target_holdings: number; max_new_per_cycle: number; exit_pct: number; full_auto: boolean };
  equity: number; held: string[];
}

export function Autopilot() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [done, setDone] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => get<Plan>("/api/autopilot/plan").then(setPlan).catch(() => {});
  useEffect(() => { load(); }, []);

  async function approve(a: Action) {
    setBusy(a.symbol);
    try {
      const r = await fetch("/api/autopilot/execute", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: a.symbol, action: a.action, shares: a.shares, wrong_price: a.wrong_price, thesis: a.thesis }),
      });
      const j = await r.json();
      setDone((d) => ({ ...d, [a.symbol]: j.ok ? "done" : (j.blocks?.join(" · ") ?? "blocked") }));
      if (j.ok) load();
    } finally { setBusy(null); }
  }

  if (!plan) return <div className="loading">the system is thinking through today…</div>;

  const sign = (a: Action) => (a.currency === "USD" ? "$" : "€");

  return (
    <>
      <div className="pagehead"><h1>Autopilot</h1>
        <span className="s">the system runs the disciplined process and explains every number — you approve, and you learn</span>
      </div>

      <div className="qbanner warn" style={{ marginTop: 6 }}>
        <b>What this is:</b> a paper-money teacher. It runs the boring, evidence-based process you've been learning
        (quality at a fair price, sized by your 1% rule, an exit on everything) and narrates each step in plain words.
        It does <b>not</b> predict prices or promise profit. You approve every trade while you learn; nothing happens on its own.
      </div>

      {!plan.signed ? (
        <div className="card"><span className="k">locked</span>
          <p style={{ margin: "8px 0 0" }}>{plan.intro[0]} <a href="#/">Sign it on the Today page →</a></p></div>
      ) : (
        <>
          <div className="card" style={{ marginBottom: 12 }}>
            <span className="k">today's plan — in plain words</span>
            {plan.intro.map((line, i) => (
              <p key={i} style={{ margin: "6px 0 0", fontSize: 14 }}>{line}</p>
            ))}
          </div>

          {plan.sells.map((a) => <ActionCard key={a.symbol} a={a} sign={sign(a)} busy={busy === a.symbol} done={done[a.symbol]} onApprove={() => approve(a)} />)}
          {plan.buys.map((a) => <ActionCard key={a.symbol} a={a} sign={sign(a)} busy={busy === a.symbol} done={done[a.symbol]} onApprove={() => approve(a)} />)}

          {plan.sells.length === 0 && plan.buys.length === 0 && (
            <div className="card"><span className="k">no action</span>
              <p style={{ margin: "8px 0 0", fontSize: 14 }}>Nothing to do today — and that's the system working. The market rewards patience, not activity.</p></div>
          )}
        </>
      )}
    </>
  );
}

function ActionCard({ a, sign, busy, done, onApprove }: { a: Action; sign: string; busy: boolean; done?: string; onApprove: () => void }) {
  const isBuy = a.action === "BUY";
  return (
    <div className="card" style={{ marginBottom: 12, borderLeft: `3px solid ${isBuy ? "var(--accent)" : "var(--warn)"}` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <span className={`badge ${isBuy ? "ok" : "warn"}`}>{a.action}</span>
        <span className="v" style={{ fontSize: 17 }}>{a.name}</span>
        <span className="mono s">{a.symbol}</span>
        {a.scores && (
          <span className="mono s" style={{ marginLeft: "auto" }}>
            Q{a.scores.q_score ?? "–"} · V{a.scores.v_score ?? "–"} · M{a.scores.m_score ?? "–"} · Σ{a.scores.composite ?? "–"}
          </span>
        )}
      </div>

      <ol style={{ margin: "10px 0 0", paddingLeft: 20 }}>
        {a.narration.map((line, i) => <li key={i} style={{ fontSize: 14, margin: "5px 0" }}>{line}</li>)}
      </ol>

      <div className="cards" style={{ marginTop: 10 }}>
        <div className="mc"><span className="k">shares</span><span className="v" style={{ fontSize: 15 }}>{a.shares}</span></div>
        <div className="mc"><span className="k">entry</span><span className="v" style={{ fontSize: 15 }}>{sign}{a.entry.toLocaleString()}</span></div>
        <div className="mc"><span className="k">exit if wrong</span><span className="v" style={{ fontSize: 15 }}>{a.wrong_price ? sign + a.wrong_price.toLocaleString() : "—"}</span></div>
        {a.cost_eur != null && <div className="mc"><span className="k">cost</span><span className="v" style={{ fontSize: 15 }}>€{a.cost_eur.toFixed(0)}</span></div>}
      </div>

      <div style={{ marginTop: 12, display: "flex", gap: 10, alignItems: "center" }}>
        {done ? (
          <span className={`badge ${done === "done" ? "ok" : "warn"}`}>{done === "done" ? "EXECUTED ✓" : done}</span>
        ) : (
          <>
            <button className="btn" onClick={onApprove} disabled={busy}>{busy ? "placing…" : `Approve — place this ${a.action.toLowerCase()}`}</button>
            <span className="s">or ignore it; nothing happens without your click</span>
          </>
        )}
      </div>
    </div>
  );
}
