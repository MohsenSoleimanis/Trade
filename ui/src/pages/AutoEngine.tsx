import { useEffect, useState } from "react";
import { get, post } from "../api";

// The Autonomous Engine — the ten-layer brain, made visible. Regime (L2),
// the committee's regime-weighted vote (L3+L4), the ideal target book (L5),
// and the proposals waiting at the one gate you touch (L9).

interface Pick { symbol: string; name?: string; weight: number; score: number; confidence: number; fired: string[]; }
interface Proposal {
  id: string; symbol: string; name: string; side: string; shares: number;
  price: number; currency: string; tier: string; status: string; blocks?: string[];
  wrong_price?: number; stop_pct?: number; est_cost_eur?: number; notional_eur?: number;
  score?: number; confidence?: number; fired?: string[]; rationale?: string; reason?: string;
}
interface Plan {
  as_of: string;
  regime: { label: string; risk: string; gross_target: number; tags: string[]; drivers: string[]; vix: number | null; note: string; };
  allocator: { weights: Record<string, number>; table: Record<string, { name: string; prior: number; fit: number; weight: number; favored: string[] }>; method: string; };
  targets: { picks: Pick[]; invested: number; cash: number; note: string; };
  proposals: Proposal[];
  book: { equity: number; cash: number; signed: boolean; };
  executable_note: string;
}

const RISK_COLOR: Record<string, string> = { risk_on: "var(--green)", neutral: "var(--warn)", risk_off: "var(--red)" };

export function AutoEngine() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const load = (rebuild = false) => {
    setErr(null);
    get<Plan>(`/api/auto/plan${rebuild ? "?rebuild=true" : ""}`).then(setPlan).catch((e) => setErr(String(e)));
  };
  useEffect(() => load(false), []);

  const act = async (p: Proposal, approve: boolean) => {
    setBusy(true); setFlash(null);
    try {
      const r = await post<{ ok: boolean; error?: string; execution?: { blocks?: string[] } }>(
        approve ? "/api/auto/approve" : "/api/auto/reject",
        approve ? { id: p.id } : { id: p.id, reason: "not now" });
      setFlash(r.ok ? `${approve ? "Approved" : "Rejected"} ${p.symbol}.`
        : `Blocked: ${r.error ?? r.execution?.blocks?.[0] ?? "gate refused"}`);
      load(false);
    } catch (e) { setFlash(String(e)); } finally { setBusy(false); }
  };

  if (err) return <div className="loading">engine error: {err}</div>;
  if (!plan) return <div className="loading">running the ten layers…</div>;
  const r = plan.regime;
  const topW = Object.entries(plan.allocator.weights).sort((a, b) => b[1] - a[1]);

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", display: "grid", gap: 12 }}>
      {/* header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 10 }}>
        <div>
          <span className="k" style={{ color: "var(--blue)" }}>THE AUTONOMOUS ENGINE</span>
          <h1 style={{ fontSize: 22, marginTop: 4 }}>Ten layers decide. You approve.</h1>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {flash && <span className="s" style={{ color: "var(--muted)" }}>{flash}</span>}
          <button className="btn ghost" disabled={busy} onClick={() => load(true)}>↻ re-run brain</button>
        </div>
      </div>

      {/* L2 regime */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
          <span className="k">L2 · market weather</span>
          <span className="mono s">as of {plan.as_of.slice(0, 16).replace("T", " ")}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 6, flexWrap: "wrap" }}>
          <span style={{ fontSize: 20, fontWeight: 750, color: RISK_COLOR[r.risk] ?? "var(--ink)" }}>{r.label}</span>
          <span className="mono s">deploy dial {(r.gross_target * 100).toFixed(0)}%</span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {r.tags.map((t) => <span key={t} className="chip">{t.replace("_", "-")}</span>)}
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          {r.drivers.map((d, i) => (
            <div key={i} className="s" style={{ padding: "2px 0", color: "var(--muted)" }}>· {d}</div>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 12 }} className="engine-cols">
        {/* L3+L4 allocator */}
        <div className="card">
          <span className="k">L3+L4 · whose vote counts today</span>
          <div className="s" style={{ margin: "4px 0 10px", color: "var(--muted)" }}>{plan.allocator.method}</div>
          {topW.map(([key, w]) => {
            const meta = plan.allocator.table[key];
            const pct = (w / Math.max(...topW.map((x) => x[1]))) * 100;
            return (
              <div key={key} style={{ marginBottom: 9 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                  <span>{meta?.name ?? key}{meta?.fit && meta.fit > 1.05 ? <span style={{ color: "var(--green)" }}> ▲ favored</span> : meta?.fit && meta.fit < 0.95 ? <span style={{ color: "var(--muted)" }}> ▽</span> : null}</span>
                  <span className="mono">{(w * 100).toFixed(1)}%</span>
                </div>
                <div style={{ height: 5, background: "var(--surface-2)", borderRadius: 3, marginTop: 3, overflow: "hidden" }}>
                  <div style={{ width: `${pct}%`, height: "100%", background: "var(--blue)" }} />
                </div>
              </div>
            );
          })}
        </div>

        {/* L5 target portfolio */}
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span className="k">L5 · the ideal target book</span>
            <span className="mono s">invested {(plan.targets.invested * 100).toFixed(0)}% · cash {(plan.targets.cash * 100).toFixed(0)}%</span>
          </div>
          <table className="data" style={{ marginTop: 6 }}>
            <thead><tr><th className="static">name</th><th className="num static">weight</th><th className="num static">score</th><th className="num static">conf</th><th className="static">strategies</th></tr></thead>
            <tbody>
              {plan.targets.picks.map((p) => (
                <tr key={p.symbol}>
                  <td><a href={`#/w/${p.symbol}`} style={{ color: "var(--ink)" }}>{p.symbol}</a></td>
                  <td className="num mono">{(p.weight * 100).toFixed(1)}%</td>
                  <td className="num mono">{p.score.toFixed(0)}</td>
                  <td className="num mono">{(p.confidence * 100).toFixed(0)}%</td>
                  <td className="s">{p.fired.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="honesty" style={{ marginTop: 8 }}>{plan.targets.note}</div>
        </div>
      </div>

      {/* L9 proposals */}
      <div className="card">
        <span className="k">L9 · proposals waiting for you</span>
        <div className={`qbanner ${plan.book.signed ? "warn" : "crit"}`} style={{ margin: "8px 0", padding: "7px 11px" }}>
          {plan.executable_note}
        </div>
        {plan.proposals.length === 0 && (
          <div className="s" style={{ color: "var(--muted)" }}>
            No concrete trades on the current book — the engine's opinion is the target book above. At this size the honest
            action is accumulating a world core; the picks become executable as the account grows.
          </div>
        )}
        {plan.proposals.map((p) => (
          <div key={p.id} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "12px 14px", marginTop: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
              <span style={{ fontWeight: 700 }}>
                <span className="mono" style={{ color: p.side === "BUY" ? "var(--green)" : "var(--red)" }}>{p.side}</span> {p.shares} {p.symbol}
                <span className="s" style={{ color: "var(--muted)" }}> · {p.name}</span>
              </span>
              <span className={`chip`} style={{ color: p.status === "pending" ? "var(--green)" : p.status === "blocked" ? "var(--warn)" : "var(--muted)" }}>{p.status}</span>
            </div>
            {p.rationale && <div className="s" style={{ margin: "6px 0", color: "var(--muted)" }}>{p.rationale}</div>}
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12 }} className="mono">
              {p.notional_eur != null && <span>notional €{p.notional_eur.toFixed(0)}</span>}
              {p.wrong_price != null && <span>wrong at {p.wrong_price} (−{p.stop_pct}%)</span>}
              {p.est_cost_eur != null && <span>cost €{p.est_cost_eur.toFixed(2)}</span>}
              {p.confidence != null && <span>conf {(p.confidence * 100).toFixed(0)}%</span>}
            </div>
            {p.blocks && p.blocks.length > 0 && (
              <div className="s" style={{ color: "var(--warn)", marginTop: 6 }}>gate: {p.blocks[0]}</div>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button className="btn" disabled={busy || p.status === "blocked"} onClick={() => act(p, true)}>✓ Approve</button>
              <button className="btn ghost" disabled={busy} onClick={() => act(p, false)}>✕ Reject</button>
            </div>
          </div>
        ))}
      </div>

      <div className="honesty">
        The engine cannot place an order. Every proposal stops here and waits for one human approval — approve routes it
        through the same constitution gates as a manual trade; nothing bypasses the veto. {r.note}
      </div>
    </div>
  );
}
