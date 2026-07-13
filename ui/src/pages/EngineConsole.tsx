import { useEffect, useRef, useState } from "react";
import { get, post } from "../api";
import "../console.css";

// THE AUTONOMOUS ENGINE — command console. Every layer shows itself as a
// live instrument, and a plain-language line so a stranger understands it.

interface Console {
  as_of: string;
  regime: { label: string; risk: string; gross_target: number; tags: string[]; drivers: string[];
    vix: number | null; breadth: number | null; trend: string | null; };
  book: { equity: number; cash: number; invested: number; starting: number; pnl_eur: number; pnl_pct: number;
    positions: { symbol: string; shares: number; value_eur: number; pnl_eur: number }[]; };
  layers: {
    l0: { total: number; by_tier: Record<string, number>; by_country: Record<string, number>;
      last_date: string; fresh_days: number | null; quality: { critical: number; warn: number; ok: boolean } };
    l1: { stocks_scored: number; avg_coverage: number | null;
      leaders: Record<string, { symbol: string; v: number }[]> };
    l3: { strategies: { key: string; name: string; edge: string; conviction: number; top: string; weight: number }[] };
    l4: { weights: Record<string, number>; table: Record<string, { name: string; fit: number }>;
      confidence: { high: number; medium: number; low: number }; method: string };
    l5: { picks: { symbol: string; weight: number; score: number; confidence: number; fired: string[]; is_core?: boolean }[];
      invested: number; cash: number; gross: number; core_symbol?: string | null; core_weight?: number };
    l6: { charter: { risk_per_idea: number; position_cap: number; leverage: number; max_drawdown_eur: number };
      country_exposure: Record<string, number>; tier_exposure: Record<string, number>;
      largest_position: number; names: number; drawdown_eur: number; open_risk_eur: number };
    l7: { half_spread_pct: Record<string, number>; tob_pct: Record<string, number>; commission_eur: number;
      sample_10k: { total: number; total_pct: number }; build_cost_eur: number };
    l8: { equity_history: { date: string; equity: number }[]; equity: number; pnl_eur: number; pnl_pct: number;
      starting: number; holdings: number; decisions: number; last_run: string };
    l9: { total: number; pending: number; proposals: Proposal[] };
  };
  memory: Memory;
}
interface Reasoning {
  deterministic: { regime: string; strategies: { name: string; why: string }[]; conviction?: number;
    confidence?: number; evidence: string[]; macro?: string | null; sizing: string };
  news: { headlines: { when: string | null; title: string; source: string; link?: string | null }[]; event?: string | null; note: string };
  memory: { prior: { at?: string; action?: string; side?: string; shares?: number; outcome?: string; reason?: string }[]; note: string };
  summary: string;
}
interface Memory {
  total: number; approved: number; blocked: number; rejected: number;
  strategy_usage: Record<string, number>;
  by_symbol: { symbol: string; approved: number; rejected: number; holding_pnl_eur?: number; holding_pnl_pct?: number }[];
  recent: { at?: string; action?: string; symbol?: string; side?: string; shares?: number; outcome?: string; reason?: string }[];
  note: string;
}
interface Proposal {
  id: string; symbol: string; name: string; side: string; shares: number; price: number; currency: string;
  status: string; wrong_price?: number; stop_pct?: number; est_cost_eur?: number; notional_eur?: number;
  confidence?: number; fired?: string[]; rationale?: string; blocks?: string[]; reasoning?: Reasoning;
}

const RISKCOL: Record<string, string> = { risk_on: "var(--jv-green)", neutral: "var(--jv-amber)", risk_off: "var(--jv-red)" };
const NODES = [
  ["L0", "Data"], ["L1", "Features"], ["L2", "Regime"], ["L3", "Committee"], ["L4", "Meta-brain"],
  ["L5", "Construct"], ["L6", "Risk veto"], ["L7", "Execution"], ["L8", "Autonomy"], ["L9", "Approval"],
];
const LIVE = new Set(["L0", "L1", "L6", "L7", "L8"]);
const cur = (n: number) => "€" + Math.round(n).toLocaleString();

export function EngineConsole() {
  const [d, setD] = useState<Console | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [hi, setHi] = useState<string | null>(null);
  const refs = useRef<Record<string, HTMLDivElement | null>>({});

  const load = (rebuild = false) => {
    setErr(null);
    get<Console>(`/api/auto/console${rebuild ? "?rebuild=true" : ""}`).then(setD).catch((e) => setErr(String(e)));
  };
  useEffect(() => load(false), []);

  const jump = (code: string) => {
    const key = code.toLowerCase();
    refs.current[key]?.scrollIntoView({ behavior: "smooth", block: "center" });
    setHi(key); setTimeout(() => setHi(null), 1400);
  };
  const act = async (p: Proposal, approve: boolean) => {
    setBusy(true); setFlash(null);
    try {
      const r = await post<{ ok: boolean; error?: string; execution?: { blocks?: string[] } }>(
        approve ? "/api/auto/approve" : "/api/auto/reject", approve ? { id: p.id } : { id: p.id, reason: "not now" });
      setFlash(r.ok ? `▸ ${approve ? "APPROVED" : "REJECTED"} ${p.symbol} → engine book`
        : `✕ ${r.error ?? r.execution?.blocks?.[0] ?? "gate refused"}`);
      load(false);
    } catch (e) { setFlash(String(e)); } finally { setBusy(false); }
  };

  if (err) return <div className="jv"><div style={{ padding: 40 }}>engine offline: {err}</div></div>;
  if (!d) return <div className="jv"><div style={{ padding: 40, color: "var(--jv-cyan)" }}>◇ booting the ten layers…</div></div>;
  const L = d.layers, r = d.regime, b = d.book;
  const mod = (key: string, extra = "") => ({ ref: (el: HTMLDivElement | null) => (refs.current[key] = el), className: `jv-mod ${hi === key ? "flash-on" : ""} ${extra}` });

  return (
    <div className="jv">
      {/* header */}
      <div className="jv-head">
        <div className="jv-title"><b>De Waag</b><span>// AUTONOMOUS ENGINE</span></div>
        <div className="jv-status">
          <span className="jv-live">ONLINE</span>
          <span>SYNC {d.as_of.slice(11, 16)} UTC</span>
          <button className="jv-btn" disabled={busy} onClick={() => load(true)}>↻ RE-RUN</button>
        </div>
      </div>

      {/* hero */}
      <div className="jv-hero">
        <div {...mod("l2", "big")}>
          <div className="jv-mod-head"><span><span className="jv-code">L2</span><span className="jv-name">Regime</span></span><span className="jv-tag panel">weather</span></div>
          <div className="jv-desc">What kind of market is it right now? Everything below adapts to this.</div>
          <div className="jv-regime-verdict" style={{ color: RISKCOL[r.risk] }}>{r.label}</div>
          <div className="jv-gauges">
            <Gauge label="VIX" value={r.vix ?? 0} max={40} invert good={18} warn={28} suffix="" />
            <Gauge label="BREADTH" value={(r.breadth ?? 0) * 100} max={100} good={60} warn={40} suffix="%" />
            <Gauge label="DEPLOY" value={r.gross_target * 100} max={100} good={0} warn={200} suffix="%" />
          </div>
          <div className="jv-drivers">{r.drivers.slice(0, 3).map((x, i) => <div key={i}>› {x}</div>)}</div>
        </div>

        <div {...mod("l8", "big")}>
          <div className="jv-mod-head"><span><span className="jv-code">L8</span><span className="jv-name">Track record</span></span><span className="jv-tag live">autonomous · simulated</span></div>
          <div className="jv-desc">The engine's own book — not your money. It trades on its own; you approve each move.</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
            <div>
              <div className="jv-bignum">{cur(b.equity)}
                <span className="jv-delta" style={{ color: b.pnl_eur >= 0 ? "var(--jv-green)" : "var(--jv-red)" }}>
                  {" "}{b.pnl_eur >= 0 ? "+" : ""}{cur(b.pnl_eur)} · {(b.pnl_pct * 100).toFixed(2)}%</span>
              </div>
            </div>
            <Spark data={L.l8.equity_history.map((h) => h.equity)} start={b.starting} />
          </div>
          <div className="jv-kv">
            <div><span className="kk">cash</span><span className="vv">{cur(b.cash)}</span></div>
            <div><span className="kk">invested</span><span className="vv">{cur(b.invested)}</span></div>
            <div><span className="kk">holdings</span><span className="vv">{L.l8.holdings}</span></div>
            <div><span className="kk">decisions</span><span className="vv">{L.l8.decisions}</span></div>
          </div>
        </div>

        <div {...mod("l9")}>
          <div className="jv-mod-head"><span><span className="jv-code">L9</span><span className="jv-name">Your gate</span></span><span className="jv-tag panel">you</span></div>
          <div className="jv-desc">The one door you touch. Approve and the engine acts.</div>
          <div className="jv-bignum" style={{ fontSize: 34, marginTop: 12 }}>{L.l9.pending}</div>
          <div className="jv-desc">proposals waiting · {L.l9.total} total this run</div>
          <button className="jv-btn" style={{ marginTop: 12 }} onClick={() => jump("l9queue")}>▾ REVIEW QUEUE</button>
        </div>
      </div>

      {/* pipeline flow */}
      <div className="jv-mod jv-pipe">
        <div className="jv-mod-head" style={{ marginBottom: 6 }}><span><span className="jv-code">PIPELINE</span><span className="jv-name">data flows top → bottom, every run</span></span></div>
        <div className="jv-pipe-track">
          {NODES.map(([code, name]) => (
            <div key={code} className={`jv-node ${LIVE.has(code) ? "live" : "panel"} ${hi === code.toLowerCase() ? "on" : ""}`} onClick={() => jump(code)}>
              <div className="ring">{code}</div>
              <div className="nlabel">{name}</div>
              <div className="nstat">{LIVE.has(code) ? "● live" : "▼ panel"}</div>
            </div>
          ))}
        </div>
      </div>

      {/* the grid */}
      <div className="jv-grid">
        {/* L0 data fabric */}
        <div {...mod("l0")}>
          <Head code="L0" name="Data fabric" tag="live" desc="Everything the engine can see, and whether the feed is healthy." />
          <Bars rows={Object.entries(L.l0.by_tier).map(([k, v]) => ({ label: k, val: v, max: L.l0.total, txt: String(v) }))} />
          <div className="jv-leds">
            <span className="jv-led"><span className={`d ${L.l0.quality.ok ? "ok" : "bad"}`} /><b>{L.l0.total}</b> instruments</span>
            <span className="jv-led"><span className={`d ${(L.l0.fresh_days ?? 9) <= 4 ? "ok" : "warn"}`} />fresh <b>{L.l0.fresh_days ?? "?"}d</b></span>
            <span className="jv-led"><span className={`d ${L.l0.quality.ok ? "ok" : "bad"}`} />gate <b>{L.l0.quality.ok ? "PASS" : "FAIL"}</b> · {L.l0.quality.warn}⚠</span>
          </div>
        </div>

        {/* L1 features */}
        <div {...mod("l1")}>
          <Head code="L1" name="Feature engine" tag="live" desc="Raw prices become meaning: who leads on each factor." />
          <div className="jv-leaders">
            {(["quality", "value", "momentum"] as const).map((f) => (
              <div className="col" key={f}>
                <div className="h">{f}</div>
                {(L.l1.leaders[f] ?? []).map((x) => (
                  <div className="row" key={x.symbol}><span>{x.symbol}</span><span className="s">{x.v}</span></div>
                ))}
              </div>
            ))}
          </div>
          <div className="jv-leds"><span className="jv-led"><span className="d ok" /><b>{L.l1.stocks_scored}</b> stocks scored</span></div>
        </div>

        {/* L3 committee */}
        <div {...mod("l3", "span2")}>
          <Head code="L3" name="Alpha committee" tag="panel" desc="Nine independent strategies vote 0–100 on every stock. Bar = conviction now; ★ = its top pick." />
          <Bars rows={L.l3.strategies.map((s) => ({ label: s.name, val: s.conviction, max: 100, txt: `${s.conviction.toFixed(0)} · ★${s.top}` }))} />
        </div>

        {/* L4 meta-brain */}
        <div {...mod("l4")}>
          <Head code="L4" name="Meta-brain" tag="panel" desc="Which strategies to trust in THIS weather. Higher = louder vote today." />
          <Bars rows={Object.entries(L.l4.weights).sort((a, b2) => b2[1] - a[1]).slice(0, 5)
            .map(([k, v]) => ({ label: L.l4.table[k]?.name ?? k, val: v * 100, max: Math.max(...Object.values(L.l4.weights)) * 100, txt: (v * 100).toFixed(1) + "%" }))} />
          <div className="jv-leds">
            <span className="jv-led"><span className="d ok" />high conf <b>{L.l4.confidence.high}</b></span>
            <span className="jv-led"><span className="d warn" />med <b>{L.l4.confidence.medium}</b></span>
            <span className="jv-led"><span className="d bad" />low <b>{L.l4.confidence.low}</b></span>
          </div>
          <div className="jv-desc" style={{ marginTop: 8 }}>{L.l4.method}</div>
        </div>

        {/* L5 construction */}
        <div {...mod("l5")}>
          <Head code="L5" name="Construction" tag="panel" desc="Core-satellite: ◆ a world basket as the base, then capped stock/basket tilts." />
          <div style={{ display: "flex", gap: 14, alignItems: "center", marginTop: 8 }}>
            <Donut invested={L.l5.invested} />
            <div style={{ flex: 1 }}>
              <Bars rows={L.l5.picks.slice(0, 7).map((p) => ({
                label: (p.is_core ? "◆ " : "") + p.symbol,
                val: p.weight * 100,
                max: Math.max(...L.l5.picks.map((x) => x.weight)) * 100 || 10,
                txt: (p.weight * 100).toFixed(1) + "%",
                tone: p.is_core ? ("green" as const) : undefined,
              }))} />
            </div>
          </div>
        </div>

        {/* L6 risk veto */}
        <div {...mod("l6")}>
          <Head code="L6" name="Risk & veto" tag="live" desc="The un-overridable law. Exposures of the target book, and the charter it obeys." />
          <Bars rows={Object.entries(L.l6.country_exposure).slice(0, 4).map(([k, v]) => ({ label: k, val: v * 100, max: 100, txt: (v * 100).toFixed(0) + "%", tone: "amber" as const }))} />
          <div className="jv-leds">
            <span className="jv-led"><span className="d ok" />risk/idea <b>{L.l6.charter.risk_per_idea}%</b></span>
            <span className="jv-led"><span className="d ok" />cap <b>{L.l6.charter.position_cap}%</b></span>
            <span className="jv-led"><span className="d ok" />leverage <b>{L.l6.charter.leverage}</b></span>
            <span className="jv-led"><span className={`d ${L.l6.drawdown_eur > L.l6.charter.max_drawdown_eur ? "bad" : "ok"}`} />drawdown <b>{cur(L.l6.drawdown_eur)}</b>/{cur(L.l6.charter.max_drawdown_eur)}</span>
          </div>
        </div>

        {/* L7 execution */}
        <div {...mod("l7")}>
          <Head code="L7" name="Execution" tag="live" desc="Cheapest fill + Belgian costs, modeled on every trade." />
          <Bars rows={[
            { label: "spread (mid)", val: L.l7.half_spread_pct.mid, max: 0.6, txt: L.l7.half_spread_pct.mid + "%" },
            { label: "TOB share", val: L.l7.tob_pct.share, max: 0.6, txt: L.l7.tob_pct.share + "%" },
            { label: "TOB etf", val: L.l7.tob_pct.etf, max: 0.6, txt: L.l7.tob_pct.etf + "%" },
          ]} />
          <div className="jv-leds">
            <span className="jv-led"><span className="d ok" />commission <b>€{L.l7.commission_eur}</b></span>
            <span className="jv-led"><span className="d warn" />build cost <b>{cur(L.l7.build_cost_eur)}</b></span>
          </div>
        </div>

        {/* L9 queue */}
        <div ref={(el) => (refs.current["l9queue"] = el)} className={`jv-mod span2 ${hi === "l9queue" ? "flash-on" : ""}`}>
          <Head code="L9" name="Approval queue" tag="panel" desc="Each proposal is finished — what, how much, why, cost, the stop. You decide." />
          {L.l9.proposals.length === 0 && (
            <div className="jv-empty">No proposals this run — the engine already holds its target book, or the regime says hold. Re-run after the next market move.</div>
          )}
          {L.l9.proposals.map((p) => (
            <div className="jv-prop" key={p.id}>
              <div className="top">
                <span><span className={`side ${p.side.toLowerCase()}`}>{p.side}</span> {p.shares} {p.symbol} <span style={{ color: "var(--jv-muted)" }}>· {p.name}</span></span>
                <span className="jv-tag" style={{ color: p.status === "pending" ? "var(--jv-green)" : "var(--jv-amber)" }}>{p.status}</span>
              </div>
              {p.rationale && <div className="why">{p.rationale}</div>}
              <div className="meta">
                {p.notional_eur != null && <span>notional {cur(p.notional_eur)}</span>}
                {p.wrong_price != null && <span>stop {p.wrong_price} (−{p.stop_pct}%)</span>}
                {p.est_cost_eur != null && <span>cost €{p.est_cost_eur.toFixed(2)}</span>}
                {p.confidence != null && <span>conf {(p.confidence * 100).toFixed(0)}%</span>}
              </div>
              {p.blocks && p.blocks.length > 0 && <div className="why" style={{ color: "var(--jv-amber)" }}>gate: {p.blocks[0]}</div>}
              {p.reasoning && <Reason r={p.reasoning} />}
              <div className="acts">
                <button className="jv-approve" disabled={busy || p.status !== "pending"} onClick={() => act(p, true)}>✓ APPROVE</button>
                <button className="jv-reject" disabled={busy} onClick={() => act(p, false)}>✕ reject</button>
              </div>
            </div>
          ))}
        </div>

        {/* L8 memory — the decision log read back */}
        <div ref={(el) => (refs.current["l8mem"] = el)} className={`jv-mod span2 ${hi === "l8mem" ? "flash-on" : ""}`}>
          <Head code="L8" name="Memory" tag="live" desc="Every decision the engine has made — remembered with its reasoning, and how the held ones are doing." />
          <div className="jv-leds">
            <span className="jv-led"><span className="d ok" />total <b>{d.memory.total}</b></span>
            <span className="jv-led"><span className="d ok" />approved <b>{d.memory.approved}</b></span>
            <span className="jv-led"><span className="d warn" />rejected <b>{d.memory.rejected}</b></span>
            <span className="jv-led"><span className="d bad" />gate-blocked <b>{d.memory.blocked}</b></span>
          </div>
          {Object.keys(d.memory.strategy_usage).length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div className="jv-desc" style={{ marginBottom: 4 }}>which strategies have actually led to approved trades:</div>
              <Bars rows={Object.entries(d.memory.strategy_usage).slice(0, 6).map(([k, v]) => ({
                label: k, val: v, max: Math.max(...Object.values(d.memory.strategy_usage)), txt: String(v) }))} />
            </div>
          )}
          {d.memory.recent.length === 0 && <div className="jv-empty">No decisions yet — approve or reject a proposal and it is remembered here, with its full reasoning, forever.</div>}
          {d.memory.recent.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {d.memory.recent.map((h, i) => (
                <div key={i} style={{ display: "flex", gap: 10, fontSize: 11, padding: "3px 0", borderBottom: "1px solid var(--jv-line)" }}>
                  <span className="mono" style={{ color: "var(--jv-muted)", minWidth: 82 }}>{h.at?.slice(5, 16).replace("T", " ")}</span>
                  <span style={{ color: h.action === "approve" ? "var(--jv-green)" : "var(--jv-amber)", minWidth: 56 }}>{h.action}</span>
                  <span style={{ flex: 1 }}>{h.side} {h.shares} {h.symbol}</span>
                  <span className="mono" style={{ color: "var(--jv-muted)" }}>{h.outcome ?? h.reason ?? ""}</span>
                </div>
              ))}
            </div>
          )}
          <div className="jv-desc" style={{ marginTop: 8 }}>{d.memory.note}</div>
        </div>
      </div>

      <div className="jv-flash">{flash}</div>
      <div className="jv-note">
        The engine runs all ten layers autonomously and stops at L9 for one human approval — approving fills the engine's
        own simulated book (its charter is pre-signed; the veto is real, not bypassed). This is a research system, not a
        money printer: simulated performance is not a promise, and no system reliably beats the market. Your personal
        account is separate and untouched.
      </div>
    </div>
  );
}

// ---------------- small SVG instruments ----------------

function Head({ code, name, tag, desc }: { code: string; name: string; tag: string; desc: string }) {
  return (
    <>
      <div className="jv-mod-head">
        <span><span className="jv-code">{code}</span><span className="jv-name">{name}</span></span>
        <span className={`jv-tag ${tag === "live" ? "live" : "panel"}`}>{tag === "live" ? "● running" : "▼ panel"}</span>
      </div>
      <div className="jv-desc">{desc}</div>
    </>
  );
}

function Reason({ r }: { r: Reasoning }) {
  const D = r.deterministic;
  return (
    <details className="jv-why">
      <summary>▸ reasoning — deterministic signals · news · memory</summary>
      <div className="jv-why-body">
        <div className="rz">
          <span className="rz-lab cyan">deterministic signals</span>
          {D.strategies.length > 0 && <div className="rz-e"><b>strategies fired:</b> {D.strategies.map((s) => s.name).join(", ")} ({D.conviction}/100, {Math.round((D.confidence ?? 0) * 100)}% conf)</div>}
          {D.evidence.map((e, i) => <div key={i} className="rz-e">• {e}</div>)}
          {D.macro && <div className="rz-e">• macro: {D.macro}</div>}
          <div className="rz-e">• {D.sizing}</div>
        </div>
        <div className="rz">
          <span className="rz-lab amber">news — context, not a signal</span>
          {r.news.event && <div className="rz-event">⚠ {r.news.event}</div>}
          {r.news.headlines.length === 0 && <div className="rz-e" style={{ opacity: 0.7 }}>quiet — no recent coverage.</div>}
          {r.news.headlines.map((h, i) => (
            <a key={i} href={h.link ?? undefined} target="_blank" rel="noreferrer" className="rz-news">
              <span className="mono">{h.when ?? "—"}</span> {h.title} <span style={{ opacity: 0.6 }}>· {h.source}</span>
            </a>
          ))}
          <div className="rz-e" style={{ opacity: 0.6, marginTop: 2 }}>{r.news.note}</div>
        </div>
        <div className="rz">
          <span className="rz-lab green">memory</span>
          <div className="rz-e">{r.memory.note}</div>
          {r.memory.prior.map((h, i) => (
            <div key={i} className="rz-e" style={{ opacity: 0.8 }}>· {h.at?.slice(0, 10)} {h.action} {h.side} {h.shares} — {h.outcome ?? h.reason ?? ""}</div>
          ))}
        </div>
      </div>
    </details>
  );
}

function Bars({ rows }: { rows: { label: string; val: number; max: number; txt: string; tone?: "green" | "amber" }[] }) {
  return (
    <div className="jv-bars">
      {rows.map((r, i) => (
        <div className="jv-bar-row" key={i}>
          <span className="bl" title={r.label}>{r.label}</span>
          <span className="jv-bar-track"><span className={`jv-bar-fill ${r.tone ?? ""}`} style={{ width: `${Math.max(2, Math.min(100, (r.val / (r.max || 1)) * 100))}%` }} /></span>
          <span className="jv-bar-val">{r.txt}</span>
        </div>
      ))}
    </div>
  );
}

function Gauge({ label, value, max, good, warn, suffix }: { label: string; value: number; max: number; good: number; warn: number; suffix: string; invert?: boolean }) {
  const R = 26, C = Math.PI * R;                       // semicircle
  const frac = Math.max(0, Math.min(1, value / max));
  const col = value <= good ? "var(--jv-green)" : value >= warn ? "var(--jv-red)" : "var(--jv-amber)";
  // for gauges where low is calm (VIX): good is a low threshold; for deploy/breadth we pass good=0 so it's neutral cyan
  const color = good === 0 ? "var(--jv-cyan)" : col;
  return (
    <svg className="jv-gauge" width="70" height="48" viewBox="0 0 70 48">
      <path d={`M 8 40 A ${R} ${R} 0 0 1 62 40`} fill="none" stroke="rgba(79,227,255,0.14)" strokeWidth="5" strokeLinecap="round" />
      <path d={`M 8 40 A ${R} ${R} 0 0 1 62 40`} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={C * (1 - frac)} style={{ filter: "drop-shadow(0 0 4px currentColor)" }} />
      <text x="35" y="34" textAnchor="middle" fontSize="13" fontWeight="700">{Math.round(value)}{suffix}</text>
      <text className="lab" x="35" y="46" textAnchor="middle" fontSize="7.5" letterSpacing="0.1em">{label}</text>
    </svg>
  );
}

function Donut({ invested }: { invested: number }) {
  const R = 24, C = 2 * Math.PI * R;
  const frac = Math.max(0, Math.min(1, invested));
  return (
    <svg className="jv-donut" width="74" height="74" viewBox="0 0 74 74">
      <circle cx="37" cy="37" r={R} fill="none" stroke="rgba(79,227,255,0.12)" strokeWidth="8" />
      <circle cx="37" cy="37" r={R} fill="none" stroke="var(--jv-cyan)" strokeWidth="8" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={C * (1 - frac)} transform="rotate(-90 37 37)"
        style={{ filter: "drop-shadow(0 0 5px var(--jv-cyan))" }} />
      <text x="37" y="35" textAnchor="middle" fontSize="14" fontWeight="700">{Math.round(frac * 100)}%</text>
      <text x="37" y="47" textAnchor="middle" fontSize="7.5" fill="var(--jv-muted)">INVESTED</text>
    </svg>
  );
}

function Spark({ data, start }: { data: number[]; start: number }) {
  const w = 160, h = 46;
  const pts = data.length >= 2 ? data : [start, ...data];
  const lo = Math.min(...pts, start) * 0.999, hi = Math.max(...pts, start) * 1.001;
  const rng = hi - lo || 1;
  const x = (i: number) => (i / (pts.length - 1 || 1)) * w;
  const y = (v: number) => h - ((v - lo) / rng) * h;
  const line = pts.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const up = pts[pts.length - 1] >= start;
  const col = up ? "var(--jv-green)" : "var(--jv-red)";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: "visible" }}>
      <polyline points={`0,${h} ${line} ${w},${h}`} className="jv-spark-fill" stroke="none" />
      <polyline points={line} fill="none" stroke={col} strokeWidth="2" strokeLinejoin="round"
        style={{ filter: `drop-shadow(0 0 4px ${col})` }} />
      <circle cx={x(pts.length - 1)} cy={y(pts[pts.length - 1])} r="3" fill={col} />
    </svg>
  );
}
