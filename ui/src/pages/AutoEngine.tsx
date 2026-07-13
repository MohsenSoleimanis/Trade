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
  layers: { code: string; name: string; role: string; status: string; detail: string; }[];
}

const RISK_COLOR: Record<string, string> = { risk_on: "var(--green)", neutral: "var(--warn)", risk_off: "var(--red)" };

interface Book {
  simulated: boolean; equity: number; cash: number; invested: number; starting: number;
  pnl_eur: number; pnl_pct: number; open_risk_eur: number; drawdown_eur: number;
  positions: { symbol: string; name: string; shares: number; currency: string; last: number; value_eur: number; pnl_eur: number; pnl_pct: number; }[];
}

export function AutoEngine() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [book, setBook] = useState<Book | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const load = (rebuild = false) => {
    setErr(null);
    get<Plan>(`/api/auto/plan${rebuild ? "?rebuild=true" : ""}`).then(setPlan).catch((e) => setErr(String(e)));
    get<Book>("/api/auto/book").then(setBook).catch(() => {});
  };
  useEffect(() => load(false), []);

  const act = async (p: Proposal, approve: boolean) => {
    setBusy(true); setFlash(null);
    try {
      const r = await post<{ ok: boolean; error?: string; execution?: { blocks?: string[] } }>(
        approve ? "/api/auto/approve" : "/api/auto/reject",
        approve ? { id: p.id } : { id: p.id, reason: "not now" });
      setFlash(r.ok ? `${approve ? "Approved" : "Rejected"} ${p.symbol} → engine book.`
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

      {/* the engine's OWN autonomous book — the correction: not your €100 account */}
      {book && (
        <div className="card" style={{ borderColor: "color-mix(in srgb, var(--blue) 40%, var(--line))" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
            <span className="k" style={{ color: "var(--blue)" }}>the engine's own book · autonomous · simulated — not your money</span>
            <span className="s">separate from your personal €100 account, on purpose</span>
          </div>
          <div style={{ display: "flex", gap: 22, flexWrap: "wrap", marginTop: 8, alignItems: "baseline" }}>
            <div>
              <span className="k">value</span>
              <span className="v" style={{ fontSize: 22 }}>€{book.equity.toLocaleString()}</span>
            </div>
            <div>
              <span className="k">track record</span>
              <span className="v" style={{ fontSize: 18, color: book.pnl_eur >= 0 ? "var(--green)" : "var(--red)" }}>
                {book.pnl_eur >= 0 ? "+" : ""}€{book.pnl_eur.toLocaleString()} ({(book.pnl_pct * 100).toFixed(2)}%)
              </span>
            </div>
            <div><span className="k">cash</span><span className="v" style={{ fontSize: 15 }}>€{book.cash.toLocaleString()}</span></div>
            <div><span className="k">invested</span><span className="v" style={{ fontSize: 15 }}>€{book.invested.toLocaleString()}</span></div>
            <div><span className="k">holdings</span><span className="v" style={{ fontSize: 15 }}>{book.positions.length}</span></div>
            <div><span className="k">start</span><span className="v" style={{ fontSize: 15 }}>€{book.starting.toLocaleString()}</span></div>
          </div>
          {book.positions.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
              {book.positions.map((p) => (
                <span key={p.symbol} className="chip" title={p.name}>
                  {p.shares}× {p.symbol} · <span style={{ color: p.pnl_eur >= 0 ? "var(--green)" : "var(--red)" }}>{p.pnl_eur >= 0 ? "+" : ""}€{p.pnl_eur.toFixed(0)}</span>
                </span>
              ))}
            </div>
          )}
          <div className="honesty" style={{ marginTop: 10 }}>
            This is the engine trading on its own — its own pre-signed charter, its own simulated capital, building a real
            track record you can judge. When you trust the record, mirror its moves into your real book by hand. Simulated
            performance is not a promise: the same signals can look good in the past and disappoint live.
          </div>
        </div>
      )}

      {/* the full spine — all ten layers, so nothing looks skipped */}
      <div className="card">
        <span className="k">the pipeline · all ten layers ran for this plan</span>
        <div className="layer-spine">
          {(plan.layers ?? []).map((L) => {
            const panel = L.status === "panel";
            const anchor = { L2: "l2", L3: "l34", L4: "l34", L5: "l5", L9: "l9" }[L.code];
            const body = (
              <>
                <span className="ls-code">{L.code}</span>
                <span className="ls-name">{L.name}<span className="ls-role"> · {L.role}</span></span>
                <span className="ls-detail">{L.detail}</span>
                <span className={`ls-dot ${panel ? "panel" : "live"}`}>{panel ? "▼ panel below" : "running"}</span>
              </>
            );
            return anchor
              ? <a key={L.code} href={`#/engine`} className="ls-row click"
                   onClick={(e) => { e.preventDefault(); document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>{body}</a>
              : <div key={L.code} className="ls-row">{body}</div>;
          })}
        </div>
      </div>

      {/* L2 regime */}
      <div id="l2" className="card">
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
        <div id="l34" className="card">
          <span className="k">L3 committee + L4 meta-brain · whose vote counts today</span>
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
        <div id="l5" className="card">
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
      <div id="l9" className="card">
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
        Every proposal stops here and waits for one human approval — approve fills it into the engine's own simulated book
        through the engine's charter (the veto is real; it just isn't waiting on your signature). Nothing here touches your
        personal account. {r.note}
      </div>
    </div>
  );
}
