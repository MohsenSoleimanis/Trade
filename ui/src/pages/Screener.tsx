import { useEffect, useMemo, useState } from "react";
import { fmtNum, fmtPct, get } from "../api";
import { Why } from "../components/Why";

interface Signal {
  symbol: string; name: string; country: string; tier: string; currency: string;
  price: number | null; ret_1m: number | null; ret_12m: number | null;
  mom_12_1: number | null; vol_1y: number | null; max_dd_1y: number | null;
  beta_1y: number | null; pe: number | null; roe_avg: number | null;
  dte: number | null; cash_conv_avg: number | null; rev_growth: number | null;
  q_score: number | null; v_score: number | null; m_score: number | null;
  composite: number | null; coverage: number;
}

type Lens = "composite" | "q_score" | "v_score" | "m_score";

const LENSES: { key: Lens; label: string; why: string; lesson: string }[] = [
  { key: "composite", label: "Composite", lesson: "Lesson 7", why: "The plain average of quality, value and momentum ranks — the baseline that's brutally hard to beat. ML (phase 5b) must outperform THIS to earn its place." },
  { key: "q_score", label: "Quality", lesson: "Lessons 3 & 7", why: "ROE level & consistency, low debt, honest cash conversion, margin direction — boring excellence, ranked. Guarded by the boredom moat." },
  { key: "v_score", label: "Value", lesson: "Lessons 4 & 7", why: "Earnings yield vs the whole universe. High score = cheap on evidence — which is a diagnosis to verify, never a verdict: check the value-trap column." },
  { key: "m_score", label: "Momentum", lesson: "Lesson 7", why: "12-1 month return, ranked. Strongest documented factor — and the costliest to trade in Belgium. Long holds or ETF form, never hand-churned." },
];

function ScoreBar({ v }: { v: number | null }) {
  if (v == null) return <span className="s">—</span>;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 90 }}>
      <div className="meter" style={{ flex: 1, margin: 0 }}>
        <div style={{ width: `${v}%`, background: v >= 67 ? "var(--green)" : v >= 34 ? "var(--blue)" : "var(--red)" }} />
      </div>
      <span className="mono" style={{ fontSize: 11, width: 20, textAlign: "right" }}>{v}</span>
    </div>
  );
}

export function Screener() {
  const [rows, setRows] = useState<Signal[] | null>(null);
  const [lens, setLens] = useState<Lens>("composite");
  const [country, setCountry] = useState<"ALL" | "US" | "BE">("ALL");

  useEffect(() => { get<Signal[]>("/api/signals").then(setRows).catch(() => {}); }, []);

  const shown = useMemo(() => {
    if (!rows) return [];
    return rows
      .filter((r) => r.tier !== "etf")
      .filter((r) => country === "ALL" || r.country === country)
      .sort((a, b) => (b[lens] ?? -1) - (a[lens] ?? -1));
  }, [rows, lens, country]);

  const active = LENSES.find((l) => l.key === lens)!;

  if (!rows) return <div className="loading">the engine is reading the universe…</div>;

  return (
    <>
      <div className="pagehead"><h1>Screener</h1>
        <span className="s">every score computed by the engine, cross-sectionally, from your own vault</span>
      </div>

      <div className="chips" style={{ marginTop: 8 }}>
        {LENSES.map((l) => (
          <button key={l.key} className={`chip ${lens === l.key ? "on" : ""}`} onClick={() => setLens(l.key)}>{l.label}</button>
        ))}
        <span style={{ width: 14 }} />
        {(["ALL", "US", "BE"] as const).map((f) => (
          <button key={f} className={`chip ${country === f ? "on" : ""}`} onClick={() => setCountry(f)}>{f}</button>
        ))}
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th className="static">#</th>
              <th className="static">Symbol</th>
              <th className="static">Company</th>
              <th className="static">Q</th>
              <th className="static">V</th>
              <th className="static">M</th>
              <th className="static">Σ</th>
              <th className="num static">P/E</th>
              <th className="num static">ROE ⌀</th>
              <th className="num static">D/E</th>
              <th className="num static">cash conv</th>
              <th className="num static">12-1 mom</th>
              <th className="num static">vol</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={r.symbol} className="click" onClick={() => (window.location.hash = `#/company/${r.symbol}`)}>
                <td className="mono s">{i + 1}</td>
                <td className="mono">{r.symbol}</td>
                <td style={{ maxWidth: 170, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.name}</td>
                <td><ScoreBar v={r.q_score} /></td>
                <td><ScoreBar v={r.v_score} /></td>
                <td><ScoreBar v={r.m_score} /></td>
                <td><ScoreBar v={r.composite} /></td>
                <td className="num">{fmtNum(r.pe, 0)}</td>
                <td className="num">{fmtPct(r.roe_avg, 0)}</td>
                <td className="num">{fmtNum(r.dte, 1)}</td>
                <td className="num">{fmtNum(r.cash_conv_avg, 2)}</td>
                <td className={`num ${(r.mom_12_1 ?? 0) >= 0 ? "up" : "down"}`}>{fmtPct(r.mom_12_1, 0)}</td>
                <td className="num">{fmtPct(r.vol_1y, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <span className="k">what this lens measures</span>
        <p style={{ margin: "6px 0 0", fontSize: 13 }}>{active.why}</p>
        <Why lesson={active.lesson}>
          Scores are percentiles among the {shown.length} stocks shown — evidence ranking, not prophecy.
          A high rank earns research time, never an automatic order: the Trading Desk will still demand
          your thesis and your exit. Survivorship note: free universe, current members only — ranks are
          relative and fair, absolute backtests on this data would flatter.
        </Why>
      </div>
    </>
  );
}
