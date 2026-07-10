import { useEffect, useState } from "react";
import { CompanyDetail, fmtMoney, fmtNum, fmtPct, get } from "../api";
import { CandleChart } from "../components/CandleChart";
import { Delta, Gauge, heat, RangeBar } from "../components/instruments";
import { PriceChart } from "../components/PriceChart";
import { Why } from "../components/Why";

// The STAGE — the center of the one-workspace design: everything about
// one company as instruments, full width. Acting happens in the ACT rail
// beside it (Workspace); this component never navigates you away.

export function Stage({ symbol }: { symbol: string }) {
  const [d, setD] = useState<CompanyDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [range, setRange] = useState("candles");

  useEffect(() => {
    setErr(null);
    get<CompanyDetail>(`/api/company/${symbol}?range=${range === "candles" ? "1y" : range}`)
      .then(setD).catch((e) => setErr(String(e)));
  }, [symbol, range]);

  if (err) return <div className="loading">could not load {symbol}: {err}</div>;
  if (!d) return <div className="loading">weighing {symbol}…</div>;

  const sign = d.currency === "USD" ? "$" : "€";
  const crit = d.quality.filter((q) => q.level === "CRITICAL");
  const warns = d.quality.filter((q) => q.level === "WARN");
  const v = d.valuation;

  let band: [number, number] | undefined;
  if (v.eps && v.eps > 0 && v.implied_growth != null) {
    const fv = (g: number) => (g < v.rate - 0.005 ? (v.eps! * (1 + g)) / (v.rate - g) : NaN);
    const lo = fv(Math.max(0, v.implied_growth - 0.01));
    const hi = fv(Math.min(v.rate - 0.01, v.implied_growth + 0.01));
    if (isFinite(lo) && isFinite(hi)) band = [Math.min(lo, hi), Math.max(lo, hi)];
  }
  const years = d.toolkit.years.slice(-4);

  return (
    <>
      {/* hero strip */}
      <div className="card" style={{ padding: "10px 16px", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <div style={{ minWidth: 170 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <h1 style={{ fontSize: 17 }}>{d.profile.name}</h1>
              <span className="mono s">{d.symbol}</span>
              <span className="badge tier">{d.profile.tier}</span>
            </div>
            <span className="s">{d.profile.exchange} · {String((d.profile as any).sector ?? "")}</span>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span className="v" style={{ fontSize: 23 }}>{sign}{d.last_price.toFixed(2)}</span>
            <Delta v={d.day_change} />
          </div>
          <div style={{ flex: 1 }} />
          <HeroTile label="mkt cap" value={fmtMoney(v.market_cap, d.currency)} />
          <HeroTile label="P/E" value={fmtNum(v.pe, 1)} />
          <HeroTile label="impl. growth" value={fmtPct(v.implied_growth)} />
          <div style={{ minWidth: 140 }}>
            <span className="k">52w</span>
            <RangeBar lo={d.low_52w} hi={d.high_52w} value={d.last_price} fmt={(x) => sign + x.toFixed(0)} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Gauge value={d.engine.scores.q_score} label="qual" size={52} />
            <Gauge value={d.engine.scores.v_score} label="val" size={52} />
            <Gauge value={d.engine.scores.m_score} label="mom" size={52} />
          </div>
        </div>
        {(crit.length > 0 || warns.length > 0) && (
          <div className={`qbanner ${crit.length ? "crit" : "warn"}`} style={{ margin: "8px 0 0", padding: "6px 10px" }}>
            {crit.length ? <b>QUARANTINED: </b> : <b>Data: </b>}
            {[...crit, ...warns].map((q) => `${q.check}: ${q.detail}`).join(" · ")}
          </div>
        )}
      </div>

      {/* chart */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <span className="k">{range === "candles" ? "daily · candles + volume" : "adjusted total-return"}</span>
          <span className="range-toggle">
            {["candles", "1y", "3y", "5y", "max"].map((r) => (
              <button key={r} className={range === r ? "on" : ""} onClick={() => setRange(r)}>{r.toUpperCase()}</button>
            ))}
          </span>
        </div>
        {range === "candles" ? <CandleChart data={d.candles} /> : <PriceChart data={d.chart} currency={d.currency} />}
      </div>

      {/* instruments row */}
      <div className="instruments-row" style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr", gap: 10 }}>
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: "10px 14px 0" }}><span className="k">fundamentals · heat = direction</span></div>
          <table className="data" style={{ marginTop: 4 }}>
            <thead><tr><th className="static">metric</th>
              {years.map((y) => <th key={y.period} className="num static">{y.period.slice(0, 4)}</th>)}</tr></thead>
            <tbody>
              <HeatRow label="Revenue" years={years} get={(y) => y.revenue} fmt={(x) => fmtMoney(x, d.currency)} deltaOf={(y, p) => (y.revenue != null && p?.revenue) ? y.revenue / p.revenue - 1 : null} />
              <HeatRow label="Net margin" years={years} get={(y) => y.net_margin} fmt={(x) => fmtPct(x)} deltaOf={(y, p) => (y.net_margin != null && p?.net_margin != null) ? y.net_margin - p.net_margin : null} />
              <HeatRow label="ROE" years={years} get={(y) => y.roe} fmt={(x) => fmtPct(x, 0)} deltaOf={(y, p) => (y.roe != null && p?.roe != null) ? y.roe - p.roe : null} />
              <HeatRow label="Debt/eq" years={years} get={(y) => y.debt_to_equity} fmt={(x) => fmtNum(x, 2)} deltaOf={(y, p) => (y.debt_to_equity != null && p?.debt_to_equity != null) ? y.debt_to_equity - p.debt_to_equity : null} good="down" />
              <HeatRow label="Cash conv." years={years} get={(y) => y.cash_conversion} fmt={(x) => fmtNum(x, 2)} deltaOf={(y, p) => (y.cash_conversion != null && p?.cash_conversion != null) ? y.cash_conversion - p.cash_conversion : null} />
            </tbody>
          </table>
        </div>

        <div className="card">
          <span className="k">valuation instrument</span>
          {v.pe && band ? (
            <>
              <div style={{ margin: "10px 0 2px" }} className="s">price vs fair-value band (implied ±1pt)</div>
              <RangeBar lo={Math.min(band[0] * 0.9, d.last_price * 0.9)} hi={Math.max(band[1] * 1.1, d.last_price * 1.1)}
                value={d.last_price} band={band} fmt={(x) => sign + x.toFixed(0)} />
              <div className="costline" style={{ marginTop: 10 }}><span>band</span><span className="mono">{sign}{band[0].toFixed(0)} – {sign}{band[1].toFixed(0)}</span></div>
              <div className="costline"><span>verdict</span>
                <span className="mono" style={{ fontWeight: 650 }}>
                  {d.last_price < band[0] ? "below band" : d.last_price > band[1] ? "above band" : "inside band — no edge"}
                </span></div>
              <Why lesson="Lesson 4">Band = value formula at the market's own implied growth ±1pt. Inside the band, your guess and the market's agree — usually do nothing.</Why>
            </>
          ) : <div className="s" style={{ padding: "10px 0" }}>no positive earnings — P/E instruments offline (wrong ruler, Lesson 4)</div>}
        </div>

        <div className="card">
          <span className="k">engine signals</span>
          <div style={{ marginTop: 4 }}>
            {d.engine.bullets.slice(0, 6).map((b, i) => {
              const tone = b.startsWith("✓") ? "var(--green)" : b.startsWith("⚠") ? "var(--warn)" : "var(--muted)";
              return (
                <div key={i} style={{ display: "flex", gap: 8, padding: "4px 0", borderBottom: "1px solid color-mix(in srgb, var(--line) 45%, transparent)" }}>
                  <span style={{ color: tone, fontSize: 9, lineHeight: "17px" }}>●</span>
                  <span style={{ fontSize: 11.5, lineHeight: 1.45 }}>{b.replace(/^[✓⚠] /, "")}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <Outlook symbol={symbol} price={d.last_price} sign={sign} />

      <AgentBrief symbol={symbol} />

      <div className="honesty">source: {d.meta.source} · {d.meta.note}</div>
    </>
  );
}

// ---- the forward half of the page: what the street expects + what is happening now

interface OutlookData {
  forward: {
    available: boolean; note?: string;
    forward_pe?: number | null; trailing_pe?: number | null;
    street_eps_growth?: number | null;
    target_low?: number | null; target_mean?: number | null; target_high?: number | null;
    recommendation?: string | null; analysts?: number | null;
  };
  news: { title: string; when: string | null; source: string; link?: string | null }[];
  read: string[];
  macro: { channel: string; label: string; beta: number; r: number | null; strength: string; so_what: string }[];
}

function Outlook({ symbol, price, sign }: { symbol: string; price: number; sign: string }) {
  const [o, setO] = useState<OutlookData | null>(null);
  const [dead, setDead] = useState(false);
  useEffect(() => {
    setO(null); setDead(false);
    get<OutlookData>(`/api/company/${symbol}/outlook`).then(setO).catch(() => setDead(true));
  }, [symbol]);

  if (dead) return null;
  const f = o?.forward;
  const hasTargets = !!(f?.available && f.target_low && f.target_high);

  return (
    <div className="instruments-row" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1.2fr", gap: 10, marginTop: 10 }}>
      <div className="card">
        <span className="k">forward view · street expectations</span>
        {!o && <div className="loading" style={{ padding: "10px 0" }}>asking the street…</div>}
        {o && !f?.available && <div className="s" style={{ padding: "10px 0" }}>{f?.note ?? "no analyst coverage found for this name."}</div>}
        {o && f?.available && (
          <>
            {hasTargets && (
              <>
                <div style={{ margin: "10px 0 2px" }} className="s">
                  price vs analyst targets ({f.analysts ?? "?"} analysts{f.recommendation ? ` · consensus: ${f.recommendation.replace("_", " ")}` : ""})
                </div>
                <RangeBar lo={Math.min(f.target_low!, price) * 0.97} hi={Math.max(f.target_high!, price) * 1.03}
                  value={price} band={[f.target_low!, f.target_high!]} fmt={(x) => sign + x.toFixed(0)} />
                <div className="costline" style={{ marginTop: 10 }}><span>target low / mean / high</span>
                  <span className="mono">{sign}{f.target_low!.toFixed(0)} / {sign}{f.target_mean?.toFixed(0)} / {sign}{f.target_high!.toFixed(0)}</span></div>
              </>
            )}
            {f.street_eps_growth != null && (
              <div className="costline"><span>street EPS growth (next yr)</span>
                <span className="mono" style={{ fontWeight: 650, color: f.street_eps_growth >= 0 ? "var(--green)" : "var(--red)" }}>
                  {(f.street_eps_growth * 100).toFixed(0)}%</span></div>
            )}
            {f.forward_pe != null && f.trailing_pe != null && (
              <div className="costline"><span>P/E — trailing → forward</span>
                <span className="mono">{f.trailing_pe.toFixed(1)} → {f.forward_pe.toFixed(1)}</span></div>
            )}
            {o.read[0] && <Why lesson="Lesson 1">{o.read.join(" ")}</Why>}
          </>
        )}
      </div>

      <div className="card">
        <span className="k">macro lens · how the world reaches this name</span>
        {!o && <div className="loading" style={{ padding: "10px 0" }}>measuring channels…</div>}
        {o && o.macro.length === 0 && <div className="s" style={{ padding: "10px 0" }}>not enough overlapping history to measure.</div>}
        {o && o.macro.length > 0 && (
          <>
            <div style={{ marginTop: 6 }}>
              {o.macro.map((m, i) => {
                const dim = m.strength === "negligible";
                const col = m.strength === "strong" ? "var(--red)" : m.strength === "clear" ? "var(--warn)" : "var(--muted)";
                return (
                  <div key={i} style={{ padding: "4px 0", borderBottom: "1px solid color-mix(in srgb, var(--line) 45%, transparent)", opacity: dim ? 0.55 : 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                      <span style={{ fontSize: 11.5 }}>{m.label}</span>
                      <span className="mono s" style={{ color: col, whiteSpace: "nowrap" }}>
                        {m.channel === "IWDA" ? `β ${m.beta.toFixed(2)}` : m.strength}
                      </span>
                    </div>
                    {!dim && <div className="s" style={{ lineHeight: 1.4 }}>{m.so_what}</div>}
                  </div>
                );
              })}
            </div>
            <Why lesson="risk">Measured co-movement (~3y weekly, market effect removed) — not causation, not prophecy. You can&apos;t forecast a war; you CAN know which channel would carry it to this name before it happens.</Why>
          </>
        )}
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: "10px 14px 4px", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span className="k">news · what is happening now</span>
          <span className="s">context, not signal — it&apos;s already in the price</span>
        </div>
        {!o && <div className="loading" style={{ padding: "4px 14px 12px" }}>reading the wires…</div>}
        {o && o.news.length === 0 && <div className="s" style={{ padding: "4px 14px 12px" }}>quiet — no recent coverage found.</div>}
        {o && o.news.length > 0 && (
          <div style={{ maxHeight: 218, overflowY: "auto", padding: "0 4px 6px 0" }}>
            {o.news.map((n, i) => (
              <a key={i} href={n.link ?? undefined} target="_blank" rel="noreferrer"
                style={{ display: "flex", gap: 10, padding: "5px 14px", textDecoration: "none", color: "inherit", alignItems: "baseline", borderBottom: "1px solid color-mix(in srgb, var(--line) 40%, transparent)" }}>
                <span className="mono s" style={{ minWidth: 62, color: "var(--muted)" }}>{n.when ?? "—"}</span>
                <span style={{ fontSize: 11.5, lineHeight: 1.45, flex: 1 }}>{n.title}</span>
                <span className="s" style={{ color: "var(--muted)", whiteSpace: "nowrap", maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis" }}>{n.source}</span>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface Brief {
  symbol: string; at?: string; author?: string; inputs?: string[]; missing?: boolean;
  sections?: { summary: string; bull_case: string; bear_case: string; verify: string; verdict: string };
}

function AgentBrief({ symbol }: { symbol: string }) {
  const [b, setB] = useState<Brief | null>(null);
  useEffect(() => { setB(null); get<Brief>(`/api/agent/brief/${symbol}`).then(setB).catch(() => {}); }, [symbol]);

  return (
    <div className="card" style={{ marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span className="k">agent research brief</span>
        {b && !b.missing && <span className="s mono">by {b.author} · {b.at?.slice(0, 10)} · reads: {b.inputs?.join(", ")}</span>}
      </div>
      {!b && <div className="loading" style={{ padding: "10px 0" }}>checking the floor…</div>}
      {b?.missing && (
        <div className="s" style={{ padding: "10px 0" }}>
          no brief yet for {symbol} — ask Claude in a session ("write the agent brief for {symbol}") and it lands here,
          with provenance, built from everything the system remembers (position, trades, theses, pipeline history, engine read, calendar).
        </div>
      )}
      {b?.sections && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 22px", marginTop: 8 }} className="brief-grid">
          <BriefBlock title="summary" text={b.sections.summary} />
          <BriefBlock title="verdict" text={b.sections.verdict} strong />
          <BriefBlock title="bull case" text={b.sections.bull_case} tone="var(--green)" />
          <BriefBlock title="bear case" text={b.sections.bear_case} tone="var(--red)" />
          <div style={{ gridColumn: "1 / -1" }}><BriefBlock title="what to verify before acting" text={b.sections.verify} tone="var(--warn)" /></div>
        </div>
      )}
    </div>
  );
}

function BriefBlock({ title, text, tone, strong }: { title: string; text: string; tone?: string; strong?: boolean }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <span className="k" style={tone ? { color: tone } : undefined}>{title}</span>
      <p style={{ margin: "4px 0 0", fontSize: 12.5, lineHeight: 1.6, fontWeight: strong ? 600 : 400 }}>{text}</p>
    </div>
  );
}

function HeroTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ minWidth: 74 }}>
      <span className="k">{label}</span>
      <span className="v" style={{ fontSize: 14 }}>{value}</span>
    </div>
  );
}

function HeatRow({ label, years, get, fmt, deltaOf, good = "up" }: {
  label: string;
  years: import("../api").YearRatios[];
  get: (y: import("../api").YearRatios) => number | null;
  fmt: (x: number) => string;
  deltaOf: (y: import("../api").YearRatios, prev: import("../api").YearRatios | undefined) => number | null;
  good?: "up" | "down";
}) {
  return (
    <tr>
      <td className="s">{label}</td>
      {years.map((y, i) => {
        const val = get(y);
        const delta = deltaOf(y, years[i - 1]);
        return <td key={y.period} className="num" style={heat(delta, good)}>{val == null ? "—" : fmt(val)}</td>;
      })}
    </tr>
  );
}

/** Legacy route wrapper (Library → Dossiers → company). */
export function Company({ symbol }: { symbol: string }) {
  return <Stage symbol={symbol} />;
}
