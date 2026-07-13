import { useEffect, useMemo, useState } from "react";
import { get, post } from "../api";
import "../console.css";

// THE ENGINE DESK — a professional trading interface. Opens on your money:
// positions, P&L, and the orders to act on. The engine's internals live in
// their own tab, for when you want to see WHY — not in your face.

interface Position { symbol: string; name: string; tier: string; shares: number; currency: string;
  last: number; value_eur: number; cost_eur: number; pnl_eur: number; pnl_pct: number; }
interface Trade { at: string; symbol: string; side: string; shares: number; fill: number; currency: string;
  costs_eur: number; total_eur: number; realized_eur?: number | null; }
interface Book {
  equity: number; cash: number; invested: number; starting: number; pnl_eur: number; pnl_pct: number;
  realized_pnl: number; unrealized_pnl: number; drawdown_eur: number;
  positions: Position[]; trades: Trade[];
}
interface Reasoning {
  deterministic: { regime: string; strategies: { name: string }[]; conviction?: number; confidence?: number; evidence: string[]; macro?: string | null; sizing: string };
  news: { headlines: { when: string | null; title: string; source: string; link?: string | null }[]; event?: string | null; note: string };
  memory: { prior: { at?: string; action?: string; side?: string; shares?: number; outcome?: string; reason?: string }[]; note: string };
  summary: string;
}
interface Proposal {
  id: string; symbol: string; name: string; side: string; shares: number; price: number; currency: string;
  tier: string; status: string; wrong_price?: number; stop_pct?: number; est_cost_eur?: number;
  notional_eur?: number; confidence?: number; target_weight?: number; blocks?: string[]; reasoning?: Reasoning;
}
interface Memory { total: number; approved: number; rejected: number; blocked: number;
  strategy_usage: Record<string, number>; recent: { at?: string; action?: string; symbol?: string; side?: string; shares?: number; outcome?: string; reason?: string }[]; note: string; }
interface Data {
  as_of: string; regime: { label: string; risk: string; gross_target: number; drivers: string[] };
  book: Book; memory: Memory;
  layers: {
    l4: { weights: Record<string, number>; table: Record<string, { name: string }> };
    l5: { picks: { symbol: string; weight: number; is_core?: boolean }[]; invested: number; core_symbol?: string | null };
    l9: { proposals: Proposal[]; pending: number };
  };
}

const eur = (n: number, d = 0) => "€" + n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const pnlc = (n: number) => (n > 0 ? "up" : n < 0 ? "down" : "flat");
const sign = (n: number, d = 0) => (n >= 0 ? "+" : "") + eur(n, d);
type Tab = "portfolio" | "orders" | "activity" | "engine";

export function EngineConsole() {
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("portfolio");
  const [sort, setSort] = useState<{ k: keyof Position; dir: 1 | -1 }>({ k: "value_eur", dir: -1 });

  const load = (rebuild = false) => {
    setErr(null);
    get<Data>(`/api/auto/console${rebuild ? "?rebuild=true" : ""}`).then(setD).catch((e) => setErr(String(e)));
  };
  useEffect(() => load(false), []);

  const act = async (p: Proposal, approve: boolean) => {
    setBusy(true); setFlash(null);
    try {
      const r = await post<{ ok: boolean; error?: string; execution?: { blocks?: string[] } }>(
        approve ? "/api/auto/approve" : "/api/auto/reject", approve ? { id: p.id } : { id: p.id, reason: "not now" });
      setFlash(r.ok ? `${approve ? "Filled" : "Rejected"} ${p.side} ${p.shares} ${p.symbol}.`
        : `Not filled: ${r.error ?? r.execution?.blocks?.[0] ?? "gate refused"}`);
      load(false);
    } catch (e) { setFlash(String(e)); } finally { setBusy(false); }
  };

  const positions = useMemo(() => {
    if (!d) return [];
    const arr = [...d.book.positions];
    arr.sort((a, b) => (a[sort.k] < b[sort.k] ? -1 : a[sort.k] > b[sort.k] ? 1 : 0) * sort.dir);
    return arr;
  }, [d, sort]);

  if (err) return <div className="dk"><div className="dk-empty">desk offline: {err}</div></div>;
  if (!d) return <div className="dk"><div className="dk-empty">loading the desk…</div></div>;
  const b = d.book;
  const pending = d.layers.l9.proposals.filter((p) => p.status === "pending");
  const th = (k: keyof Position, label: string, left = false) => (
    <th className={`${left ? "l" : ""} sortable`} onClick={() => setSort((s) => ({ k, dir: s.k === k && s.dir === -1 ? 1 : -1 }))}>
      {label}{sort.k === k ? (sort.dir === -1 ? " ↓" : " ↑") : ""}
    </th>
  );

  return (
    <div className="dk">
      <div className="dk-top">
        <div className="brand">Engine Desk<span>autonomous · simulated · €1,000 book</span></div>
        <div className="right">
          <span>as of {d.as_of.slice(11, 16)} UTC</span>
          <button className="dk-refresh" disabled={busy} onClick={() => load(true)}>↻ re-run engine</button>
        </div>
      </div>

      {/* account summary — the money, first */}
      <div className="dk-acct">
        <div className="cell hero">
          <div className="lab">Equity</div>
          <div className="val">{eur(b.equity, 2)}</div>
          <div className={`sub ${pnlc(b.pnl_eur)}`}>{sign(b.pnl_eur, 2)} · {(b.pnl_pct * 100).toFixed(2)}% all-time</div>
        </div>
        <div className="cell"><div className="lab">Cash</div><div className="val mono">{eur(b.cash, 2)}</div></div>
        <div className="cell"><div className="lab">Invested</div><div className="val mono">{eur(b.invested, 2)}</div></div>
        <div className="cell"><div className="lab">Open P&amp;L</div><div className={`val mono ${pnlc(b.unrealized_pnl)}`}>{sign(b.unrealized_pnl, 2)}</div></div>
        <div className="cell"><div className="lab">Realized P&amp;L</div><div className={`val mono ${pnlc(b.realized_pnl)}`}>{sign(b.realized_pnl, 2)}</div></div>
        <div className="cell"><div className="lab">Positions</div><div className="val mono">{b.positions.length}</div></div>
      </div>

      <div className="dk-tabs">
        <button className={`dk-tab ${tab === "portfolio" ? "on" : ""}`} onClick={() => setTab("portfolio")}>Portfolio<span className="cnt">{b.positions.length}</span></button>
        <button className={`dk-tab ${tab === "orders" ? "on" : ""}`} onClick={() => setTab("orders")}>Orders<span className="cnt">{pending.length}</span></button>
        <button className={`dk-tab ${tab === "activity" ? "on" : ""}`} onClick={() => setTab("activity")}>Activity<span className="cnt">{b.trades.length}</span></button>
        <button className={`dk-tab ${tab === "engine" ? "on" : ""}`} onClick={() => setTab("engine")}>Engine</button>
      </div>

      {flash && <div className="dk-flash">{flash}</div>}

      {/* ---------------- PORTFOLIO ---------------- */}
      {tab === "portfolio" && (
        <div className="dk-tblwrap">
          {positions.length === 0 ? (
            <div className="dk-empty">No positions yet. Go to <b>Orders</b> and approve the engine's proposals —
              they fill here and your P&amp;L starts tracking.</div>
          ) : (
            <table className="dk-tbl">
              <thead><tr>
                {th("symbol", "Symbol", true)}{th("shares", "Qty")}
                <th>Avg cost</th>{th("last", "Last")}{th("value_eur", "Mkt value")}
                {th("pnl_eur", "Open P&L")}{th("pnl_pct", "P&L %")}<th>Weight</th>
              </tr></thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.symbol}>
                    <td className="l"><span className="sym">{p.symbol}</span> <span className="nm">{p.name}</span></td>
                    <td className="mono">{p.shares}</td>
                    <td className="mono">{eur(p.cost_eur / p.shares, 2)}</td>
                    <td className="mono">{p.last.toFixed(2)} <span className="nm">{p.currency === "USD" ? "$" : "€"}</span></td>
                    <td className="mono">{eur(p.value_eur, 2)}</td>
                    <td className={`mono ${pnlc(p.pnl_eur)}`}>{sign(p.pnl_eur, 2)}</td>
                    <td className={`mono ${pnlc(p.pnl_eur)}`}>{(p.pnl_pct * 100).toFixed(2)}%</td>
                    <td className="mono">{((p.value_eur / b.equity) * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr>
                <td className="l">TOTAL · {positions.length} positions</td><td /><td /><td />
                <td className="mono">{eur(b.invested, 2)}</td>
                <td className={`mono ${pnlc(b.unrealized_pnl)}`}>{sign(b.unrealized_pnl, 2)}</td>
                <td /><td className="mono">{((b.invested / b.equity) * 100).toFixed(0)}%</td>
              </tr></tfoot>
            </table>
          )}
        </div>
      )}

      {/* ---------------- ORDERS ---------------- */}
      {tab === "orders" && (
        <div className="dk-tblwrap">
          {d.layers.l9.proposals.length === 0 ? (
            <div className="dk-empty">No orders right now — the engine already holds its target book, or the regime says
              hold. Hit <b>↻ re-run engine</b> after the next market move.</div>
          ) : d.layers.l9.proposals.map((p) => (
            <div className="dk-order" key={p.id}>
              <div className="row1">
                <span className={`dk-badge ${p.side.toLowerCase()}`}>{p.side}</span>
                <span className="big">{p.shares} {p.symbol}</span>
                <span className="nm">{p.name}</span>
                {p.tier === "etf" && <span className="dk-badge core">basket core</span>}
                <span className="spacer" />
                <span className="nm mono">{p.status}</span>
              </div>
              <div className="facts">
                {p.notional_eur != null && <span>notional <b>{eur(p.notional_eur, 0)}</b></span>}
                <span>est. price <b>{p.price.toFixed(2)} {p.currency === "USD" ? "$" : "€"}</b></span>
                {p.wrong_price != null ? <span>stop <b>{p.wrong_price} (−{p.stop_pct}%)</b></span> : <span>stop <b>none (basket)</b></span>}
                {p.est_cost_eur != null && <span>cost <b>€{p.est_cost_eur.toFixed(2)}</b></span>}
                {p.confidence != null && <span>conviction <b>{(p.confidence * 100).toFixed(0)}%</b></span>}
              </div>
              {p.blocks && p.blocks.length > 0 && <div className="dk-gate">gate: {p.blocks[0]}</div>}
              {p.reasoning && <Reason r={p.reasoning} />}
              <div className="acts">
                <button className="dk-approve" disabled={busy || p.status !== "pending"} onClick={() => act(p, true)}>✓ Approve</button>
                <button className="dk-reject" disabled={busy} onClick={() => act(p, false)}>Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---------------- ACTIVITY (trade blotter) ---------------- */}
      {tab === "activity" && (
        <div className="dk-tblwrap">
          {b.trades.length === 0 ? (
            <div className="dk-empty">No trades yet — your buys and sells will appear here, with the realized profit or
              loss on every sell.</div>
          ) : (
            <table className="dk-tbl">
              <thead><tr>
                <th className="l">Date</th><th className="l">Side</th><th className="l">Symbol</th>
                <th>Qty</th><th>Price</th><th>Value</th><th>Cost</th><th>Realized P&amp;L</th>
              </tr></thead>
              <tbody>
                {[...b.trades].reverse().map((t, i) => (
                  <tr key={i}>
                    <td className="l mono nm">{t.at.slice(0, 16).replace("T", " ")}</td>
                    <td className="l"><span className={`dk-badge ${t.side.toLowerCase()}`}>{t.side}</span></td>
                    <td className="l sym">{t.symbol}</td>
                    <td className="mono">{t.shares}</td>
                    <td className="mono">{t.fill.toFixed(2)} {t.currency === "USD" ? "$" : "€"}</td>
                    <td className="mono">{eur(t.total_eur, 2)}</td>
                    <td className="mono nm">€{t.costs_eur.toFixed(2)}</td>
                    <td className={`mono ${t.realized_eur != null ? pnlc(t.realized_eur) : "flat"}`}>
                      {t.realized_eur != null ? sign(t.realized_eur, 2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr>
                <td className="l">REALIZED (closed trades)</td><td /><td /><td /><td /><td /><td />
                <td className={`mono ${pnlc(b.realized_pnl)}`}>{sign(b.realized_pnl, 2)}</td>
              </tr></tfoot>
            </table>
          )}
        </div>
      )}

      {/* ---------------- ENGINE (the internals, secondary) ---------------- */}
      {tab === "engine" && <EngineInternals d={d} />}

      <div className="dk-note">
        This is the engine's own simulated book — not your money — building a track record you can judge. Simulated
        performance is not a promise; no system reliably beats the market. Your personal account is separate. Approving
        an order fills it here through the engine's risk charter (the veto is real, never bypassed).
      </div>
    </div>
  );
}

function EngineInternals({ d }: { d: Data }) {
  const w = Object.entries(d.layers.l4.weights).sort((a, b) => b[1] - a[1]);
  const wmax = Math.max(...w.map((x) => x[1]));
  const picks = d.layers.l5.picks;
  const pmax = Math.max(...picks.map((p) => p.weight), 0.1);
  const su = Object.entries(d.memory.strategy_usage);
  return (
    <div className="dk-grid">
      <div className="dk-card">
        <h3>Regime — the market weather</h3>
        <div className="cdesc">What kind of market it is now; everything below adapts to it.</div>
        <div className="dk-regime" style={{ color: d.regime.risk === "risk_on" ? "var(--dk-up)" : d.regime.risk === "risk_off" ? "var(--dk-down)" : "var(--dk-ink)" }}>{d.regime.label}</div>
        <div className="dk-drivers" style={{ marginTop: 8 }}>{d.regime.drivers.slice(0, 3).map((x, i) => <div key={i}>· {x}</div>)}</div>
        <div className="dk-pipe">{["L0 data", "L1 features", "L2 regime", "L3 committee", "L4 meta", "L5 build", "L6 risk", "L7 exec", "L8 memory", "L9 you"].map((n) => <span className="n" key={n}><b>{n.split(" ")[0]}</b> {n.split(" ")[1]}</span>)}</div>
      </div>

      <div className="dk-card">
        <h3>Strategy weights — who the engine trusts now</h3>
        <div className="cdesc">Nine strategies; the meta-brain (L4) weights them for this regime.</div>
        {w.slice(0, 6).map(([k, v]) => (
          <div className="dk-bar" key={k}>
            <div className="t"><span>{d.layers.l4.table[k]?.name ?? k}</span><span className="mono">{(v * 100).toFixed(1)}%</span></div>
            <div className="track"><div className="fill" style={{ width: `${(v / wmax) * 100}%` }} /></div>
          </div>
        ))}
      </div>

      <div className="dk-card">
        <h3>Target book — core + satellites</h3>
        <div className="cdesc">The engine's ideal shape: ◆ a world basket core, then capped tilts.</div>
        {picks.slice(0, 8).map((p) => (
          <div className="dk-bar" key={p.symbol}>
            <div className="t"><span>{p.is_core ? "◆ " : ""}{p.symbol}</span><span className="mono">{(p.weight * 100).toFixed(1)}%</span></div>
            <div className="track"><div className={`fill ${p.is_core ? "core" : ""}`} style={{ width: `${(p.weight / pmax) * 100}%` }} /></div>
          </div>
        ))}
      </div>

      <div className="dk-card">
        <h3>Memory — every decision, remembered</h3>
        <div className="cdesc">The engine reads its own decision log; this is what the learning model will train on.</div>
        <div className="dk-leds">
          <span className="dk-led">total <b>{d.memory.total}</b></span>
          <span className="dk-led">approved <b>{d.memory.approved}</b></span>
          <span className="dk-led">rejected <b>{d.memory.rejected}</b></span>
          <span className="dk-led">blocked <b>{d.memory.blocked}</b></span>
        </div>
        {su.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <div className="cdesc">strategies that led to approved trades:</div>
            {su.slice(0, 5).map(([k, v]) => (
              <div className="dk-bar" key={k}><div className="t"><span>{k}</span><span className="mono">{v}</span></div>
                <div className="track"><div className="fill" style={{ width: `${(v / Math.max(...su.map((x) => x[1]))) * 100}%` }} /></div></div>
            ))}
          </div>
        )}
        {d.memory.recent.length > 0 && (
          <div style={{ marginTop: 10 }}>
            {d.memory.recent.slice(0, 6).map((h, i) => (
              <div key={i} style={{ display: "flex", gap: 8, fontSize: 11, padding: "2px 0", color: "var(--dk-muted)" }}>
                <span className="mono" style={{ minWidth: 78 }}>{h.at?.slice(5, 16).replace("T", " ")}</span>
                <span style={{ color: h.action === "approve" ? "var(--dk-up)" : "var(--dk-down)", minWidth: 52 }}>{h.action}</span>
                <span style={{ flex: 1 }}>{h.side} {h.shares} {h.symbol}</span>
                <span className="mono">{h.outcome ?? h.reason ?? ""}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Reason({ r }: { r: Reasoning }) {
  const D = r.deterministic;
  return (
    <details className="dk-why">
      <summary>▸ why — signals · news · memory</summary>
      <div className="dk-why-body">
        <div>
          <span className="dk-rz-lab">deterministic signals</span>
          {D.strategies.length > 0 && <div className="dk-rz-e"><b>fired:</b> {D.strategies.map((s) => s.name).join(", ")} ({D.conviction}/100)</div>}
          {D.evidence.map((e, i) => <div key={i} className="dk-rz-e">• {e}</div>)}
          {D.macro && <div className="dk-rz-e">• {D.macro}</div>}
          <div className="dk-rz-e">• {D.sizing}</div>
        </div>
        <div>
          <span className="dk-rz-lab">news · context, not a signal</span>
          {r.news.event && <div className="dk-event">⚠ {r.news.event}</div>}
          {r.news.headlines.length === 0 && <div className="dk-rz-e" style={{ opacity: .7 }}>quiet.</div>}
          {r.news.headlines.map((h, i) => (
            <a key={i} href={h.link ?? undefined} target="_blank" rel="noreferrer" className="dk-news">
              <span className="mono">{h.when ?? "—"}</span> {h.title}
            </a>
          ))}
        </div>
        <div>
          <span className="dk-rz-lab">memory</span>
          <div className="dk-rz-e">{r.memory.note}</div>
          {r.memory.prior.map((h, i) => <div key={i} className="dk-rz-e" style={{ opacity: .8 }}>· {h.at?.slice(0, 10)} {h.action} {h.side} {h.shares}</div>)}
        </div>
      </div>
    </details>
  );
}
