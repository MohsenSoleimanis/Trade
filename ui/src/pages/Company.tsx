import { useEffect, useState } from "react";
import { CompanyDetail, fmtMoney, fmtNum, fmtPct, get } from "../api";
import { CandleChart } from "../components/CandleChart";
import { Delta, Gauge, heat, RangeBar } from "../components/instruments";
import { PriceChart } from "../components/PriceChart";
import { TradePanel } from "../components/TradePanel";
import { Why } from "../components/Why";

// The dossier as a TERMINAL WORKSPACE: one dense screen of instruments —
// hero strip, chart + trade rail, gauges, heat table, valuation band.
// Sentences live in mentor mode; the surface speaks in visuals.

export function Company({ symbol }: { symbol: string }) {
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

  // valuation band: fair value at implied growth ±1pt (the honest range)
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
      {/* ---------- hero strip ---------- */}
      <div className="card" style={{ padding: "12px 18px", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div style={{ minWidth: 210 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <h1 style={{ fontSize: 19 }}>{d.profile.name}</h1>
              <span className="mono s">{d.symbol}</span>
              <span className="badge tier">{d.profile.tier}</span>
            </div>
            <span className="s">{d.profile.exchange} · {String((d.profile as any).sector ?? "")} · {d.last_date}</span>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
            <span className="v" style={{ fontSize: 26 }}>{sign}{d.last_price.toFixed(2)}</span>
            <Delta v={d.day_change} />
          </div>
          <div style={{ flex: 1 }} />
          <HeroTile label="mkt cap" value={fmtMoney(v.market_cap, d.currency)} />
          <HeroTile label="P/E" value={fmtNum(v.pe, 1)} />
          <HeroTile label="EPS" value={v.eps != null ? sign + v.eps.toFixed(2) : "—"} />
          <HeroTile label="implied growth" value={fmtPct(v.implied_growth)} />
          <div style={{ minWidth: 170 }}>
            <span className="k">52w range</span>
            <RangeBar lo={d.low_52w} hi={d.high_52w} value={d.last_price}
              fmt={(x) => sign + x.toFixed(0)} />
          </div>
        </div>
        {(crit.length > 0 || warns.length > 0) && (
          <div className={`qbanner ${crit.length ? "crit" : "warn"}`} style={{ margin: "10px 0 0" }}>
            {crit.length ? <b>QUARANTINED: </b> : <b>Data notes: </b>}
            {[...crit, ...warns].map((q) => `${q.check}: ${q.detail}`).join(" · ")}
          </div>
        )}
      </div>

      {/* ---------- chart + right rail ---------- */}
      <div className="chart-trade-row" style={{ marginBottom: 12 }}>
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <span className="k">{range === "candles" ? "daily · candles + volume" : "adjusted total-return line"}</span>
            <span className="range-toggle">
              {["candles", "1y", "3y", "5y", "max"].map((r) => (
                <button key={r} className={range === r ? "on" : ""} onClick={() => setRange(r)}>{r.toUpperCase()}</button>
              ))}
            </span>
          </div>
          {range === "candles"
            ? <CandleChart data={d.candles} />
            : <PriceChart data={d.chart} currency={d.currency} />}
          <Why lesson="Lessons 1 & 5">
            Candles show raw daily trading (what you'd have paid); the line view shows dividend-adjusted
            wealth over years — the weighing machine. Day-to-day is mostly noise; years are mostly business.
          </Why>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <TradePanel symbol={d.symbol} currency={d.currency} lastClose={d.last_price} />
          <div className="card">
            <span className="k">engine scores · vs universe</span>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
              <Gauge value={d.engine.scores.q_score} label="quality" size={70} />
              <Gauge value={d.engine.scores.v_score} label="value" size={70} />
              <Gauge value={d.engine.scores.m_score} label="momentum" size={70} />
            </div>
          </div>
        </div>
      </div>

      {/* ---------- instruments row ---------- */}
      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr", gap: 12 }} className="instruments-row">
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: "12px 16px 0" }}><span className="k">fundamentals · heat = direction vs prior year</span></div>
          <table className="data" style={{ marginTop: 6 }}>
            <thead><tr><th className="static">metric</th>
              {years.map((y) => <th key={y.period} className="num static">{y.period.slice(0, 4)}</th>)}</tr></thead>
            <tbody>
              <HeatRow label="Revenue" years={years} get={(y) => y.revenue} fmt={(x) => fmtMoney(x, d.currency)} deltaOf={(y, p) => (y.revenue != null && p?.revenue) ? y.revenue / p.revenue - 1 : null} />
              <HeatRow label="Net margin" years={years} get={(y) => y.net_margin} fmt={(x) => fmtPct(x)} deltaOf={(y, p) => (y.net_margin != null && p?.net_margin != null) ? y.net_margin - p.net_margin : null} />
              <HeatRow label="ROE" years={years} get={(y) => y.roe} fmt={(x) => fmtPct(x, 0)} deltaOf={(y, p) => (y.roe != null && p?.roe != null) ? y.roe - p.roe : null} />
              <HeatRow label="Debt/equity" years={years} get={(y) => y.debt_to_equity} fmt={(x) => fmtNum(x, 2)} deltaOf={(y, p) => (y.debt_to_equity != null && p?.debt_to_equity != null) ? y.debt_to_equity - p.debt_to_equity : null} good="down" />
              <HeatRow label="Cash conv." years={years} get={(y) => y.cash_conversion} fmt={(x) => fmtNum(x, 2)} deltaOf={(y, p) => (y.cash_conversion != null && p?.cash_conversion != null) ? y.cash_conversion - p.cash_conversion : null} />
            </tbody>
          </table>
        </div>

        <div className="card">
          <span className="k">valuation instrument</span>
          {v.pe && band ? (
            <>
              <div style={{ margin: "14px 0 4px" }} className="s">price vs honest fair-value band (implied growth ±1pt)</div>
              <RangeBar
                lo={Math.min(band[0] * 0.9, d.last_price * 0.9)}
                hi={Math.max(band[1] * 1.1, d.last_price * 1.1)}
                value={d.last_price} band={band}
                fmt={(x) => sign + x.toFixed(0)} />
              <div className="costline" style={{ marginTop: 12 }}><span>price</span><span className="mono">{sign}{d.last_price.toFixed(2)}</span></div>
              <div className="costline"><span>band</span><span className="mono">{sign}{band[0].toFixed(0)} – {sign}{band[1].toFixed(0)}</span></div>
              <div className="costline"><span>verdict</span>
                <span className="mono" style={{ fontWeight: 650 }}>
                  {d.last_price < band[0] ? "below band — interesting" : d.last_price > band[1] ? "above band — priced up" : "inside band — no edge"}
                </span></div>
              <Why lesson="Lesson 4">
                The band is the value formula at the market's own implied growth ±1 point. Price inside the
                band = your guess and the market's guess agree — the correct action is usually nothing.
              </Why>
            </>
          ) : <div className="s" style={{ padding: "14px 0" }}>no positive earnings — valuation instruments offline for this name (the right rulers are P/B or events; Lesson 4's multiples table)</div>}
        </div>

        <div className="card">
          <span className="k">engine signals</span>
          <div style={{ marginTop: 6 }}>
            {d.engine.bullets.slice(0, 6).map((b, i) => {
              const tone = b.startsWith("✓") ? "var(--green)" : b.startsWith("⚠") ? "var(--warn)" : "var(--muted)";
              return (
                <div key={i} style={{ display: "flex", gap: 8, padding: "5px 0", borderBottom: "1px solid color-mix(in srgb, var(--line) 45%, transparent)" }}>
                  <span style={{ color: tone, fontSize: 9, lineHeight: "18px" }}>●</span>
                  <span style={{ fontSize: 12, lineHeight: 1.5 }}>{b.replace(/^[✓⚠] /, "")}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="honesty">
        source: {d.meta.source} · ingested {d.meta.ingested_at} · {d.meta.note}
        {" · "}<a href="#/research" className="mini-link">← all companies</a>
      </div>
    </>
  );
}

function HeroTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ minWidth: 84 }}>
      <span className="k">{label}</span>
      <span className="v" style={{ fontSize: 15 }}>{value}</span>
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
        return (
          <td key={y.period} className="num" style={heat(delta, good)}>
            {val == null ? "—" : fmt(val)}
          </td>
        );
      })}
    </tr>
  );
}
