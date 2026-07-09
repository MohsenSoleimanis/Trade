import { useEffect, useState } from "react";
import { fmtPct, get } from "../api";
import { LineChart } from "../components/LineChart";
import { Why } from "../components/Why";

interface Stats { cagr?: number; vol?: number; sharpe?: number; max_dd?: number }
interface BtResult {
  dates: string[]; gross: number[]; net: number[]; equal_weight: number[];
  benchmark?: (number | null)[];
  stats: { strategy: string; top_n: number; months: number; gross: Stats; net: Stats;
           equal_weight: Stats; benchmark?: Stats; avg_turnover_1way: number; total_cost_drag: number | null };
  warnings: string[]; ledger_count: number;
}
interface LedgerRow { at: string; strategy: string; top_n: number; months: number; net_cagr: number | null; net_sharpe: number | null }

export function BacktestLab() {
  const [strategy, setStrategy] = useState<"mom_12_1" | "equal_weight">("mom_12_1");
  const [topN, setTopN] = useState(8);
  const [startYear, setStartYear] = useState(2006);
  const [running, setRunning] = useState(false);
  const [res, setRes] = useState<BtResult | null>(null);
  const [led, setLed] = useState<LedgerRow[]>([]);

  const loadLedger = () => get<LedgerRow[]>("/api/backtest/ledger").then(setLed).catch(() => {});
  useEffect(() => { loadLedger(); }, []);

  async function runBt() {
    setRunning(true);
    try {
      const r = await fetch("/api/backtest", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy, top_n: topN, start_year: startYear }),
      });
      setRes(await r.json());
      loadLedger();
    } finally { setRunning(false); }
  }

  const S = ({ s }: { s?: Stats }) => (
    <>{s?.cagr != null ? fmtPct(s.cagr) : "—"} / {s?.sharpe ?? "—"} / {s?.max_dd != null ? fmtPct(s.max_dd, 0) : "—"}</>
  );

  return (
    <>
      <div className="pagehead"><h1>Backtest Lab</h1>
        <span className="s">walk a rule through 20 years of your own vault — costs deducted, every run counted</span>
      </div>

      <div className="qbanner warn" style={{ marginTop: 6 }}>
        <b>Survivorship notice:</b> this universe contains only today's survivors — dead companies are missing,
        so absolute numbers flatter. Read <i>relative</i> results (strategy vs equal-weight vs benchmark), not absolute ones.
      </div>

      <div className="card">
        <div style={{ display: "flex", gap: 22, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div><span className="k">strategy</span>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value as typeof strategy)}
              style={{ font: "13px 'Segoe UI', system-ui, sans-serif", background: "var(--code-bg)", color: "var(--ink)", border: "1px solid var(--line)", borderRadius: 6, padding: "6px 10px", marginTop: 4 }}>
              <option value="mom_12_1">12-1 momentum, top N, monthly</option>
              <option value="equal_weight">equal weight everything (the humble baseline)</option>
            </select></div>
          {strategy === "mom_12_1" && (
            <div><span className="k">top N: {topN}</span>
              <input type="range" min={4} max={15} value={topN} onChange={(e) => setTopN(Number(e.target.value))}
                style={{ width: 160, marginTop: 8 }} aria-label="top N" /></div>
          )}
          <div><span className="k">from year: {startYear}</span>
            <input type="range" min={2006} max={2022} value={startYear} onChange={(e) => setStartYear(Number(e.target.value))}
              style={{ width: 160, marginTop: 8 }} aria-label="start year" /></div>
          <button className="btn" onClick={runBt} disabled={running}>{running ? "walking history…" : "Run backtest"}</button>
          <span className="s mono">runs logged: {res?.ledger_count ?? led.length}</span>
        </div>
        <Why lesson="M06 / Lesson 7">
          The ledger counts every configuration you ever try — the more you try, the luckier your best result
          is expected to be (deflated Sharpe). That's why the knobs here are few and boring on purpose.
        </Why>
      </div>

      {res && (
        <>
          <div className="card" style={{ marginTop: 12 }}>
            <span className="k">equity curves — base 100</span>
            <LineChart
              dates={res.dates}
              series={[
                { name: "net", color: "var(--green)", values: res.net },
                { name: "gross", color: "var(--blue)", values: res.gross },
                { name: "eq-wt", color: "var(--muted)", values: res.equal_weight },
                ...(res.benchmark ? [{ name: "IWDA", color: "var(--warn)", values: res.benchmark }] : []),
              ]}
            />
            <Why lesson="Lesson 2">
              The gap between <b>gross</b> and <b>net</b> is everything Lesson 2 warned about — spread, TOB and
              commissions, compounding against you for {res.stats.months} months
              (total drag {res.stats.total_cost_drag != null ? fmtPct(res.stats.total_cost_drag) : "—"},
              avg one-way turnover {fmtPct(res.stats.avg_turnover_1way, 0)}/month).
            </Why>
          </div>

          <div className="cards" style={{ marginTop: 12 }}>
            <div className="card"><span className="k">strategy NET · cagr / sharpe / maxDD</span><span className="v" style={{ fontSize: 15 }}><S s={res.stats.net} /></span></div>
            <div className="card"><span className="k">strategy GROSS</span><span className="v" style={{ fontSize: 15 }}><S s={res.stats.gross} /></span></div>
            <div className="card"><span className="k">equal weight</span><span className="v" style={{ fontSize: 15 }}><S s={res.stats.equal_weight} /></span></div>
            {res.stats.benchmark && <div className="card"><span className="k">IWDA benchmark</span><span className="v" style={{ fontSize: 15 }}><S s={res.stats.benchmark} /></span></div>}
          </div>

          <div className="card" style={{ marginTop: 12 }}>
            <span className="k">how to read this honestly</span>
            <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 13 }}>
              <li>Beat equal-weight after costs? Then the <i>ranking</i> added something beyond just owning stocks.</li>
              <li>Beat IWDA after costs? Then the whole exercise beat the two-click alternative — the only bar that pays.</li>
              <li>Look at max drawdown and ask the Lesson 6 question: could YOU hold through that, in euros?</li>
              <li>{res.warnings[0]}</li>
            </ul>
          </div>
        </>
      )}

      <div className="card" style={{ marginTop: 12, padding: 0 }}>
        <div style={{ padding: "10px 14px 0" }}><span className="k">experiment ledger — every run you ever made</span></div>
        {led.length ? (
          <table className="data">
            <thead><tr><th className="static">when</th><th className="static">strategy</th><th className="num static">top N</th><th className="num static">months</th><th className="num static">net CAGR</th><th className="num static">net Sharpe</th></tr></thead>
            <tbody>
              {[...led].reverse().slice(0, 20).map((r, i) => (
                <tr key={i}>
                  <td className="mono s">{r.at.slice(0, 16).replace("T", " ")}</td>
                  <td className="mono">{r.strategy}</td>
                  <td className="num">{r.top_n}</td>
                  <td className="num">{r.months}</td>
                  <td className="num">{r.net_cagr != null ? (r.net_cagr * 100).toFixed(1) + "%" : "—"}</td>
                  <td className="num">{r.net_sharpe ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <div className="loading" style={{ padding: "14px" }}>no runs yet — the ledger starts with your first</div>}
      </div>
    </>
  );
}
