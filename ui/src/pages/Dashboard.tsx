import { useEffect, useMemo, useState } from "react";
import { Company, fmtMoney, get, Portfolio, VaultStatus } from "../api";
import { Spark } from "../components/Spark";
import { Why } from "../components/Why";

interface Quality { gate: string; findings: { level: string }[] }

export function Dashboard() {
  const [vault, setVault] = useState<VaultStatus | null>(null);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [rows, setRows] = useState<Company[] | null>(null);
  const [pf, setPf] = useState<Portfolio | null>(null);

  useEffect(() => {
    get<VaultStatus>("/api/vault/status").then(setVault).catch(() => {});
    get<Company[]>("/api/companies").then(setRows).catch(() => {});
    get<Portfolio>("/api/portfolio").then(setPf).catch(() => {});
    get<Quality>("/api/vault/quality").then(setQuality).catch(() => {});
  }, []);

  const movers = useMemo(() => {
    if (!rows) return { up: [], down: [] };
    const withDay = rows.filter((r) => r.day_change != null);
    const sorted = [...withDay].sort((a, b) => (b.day_change ?? 0) - (a.day_change ?? 0));
    return { up: sorted.slice(0, 5), down: sorted.slice(-5).reverse() };
  }, [rows]);

  const watchlist = useMemo(
    () => (rows ?? []).filter((r) => ["IWDA", "LOTB", "MELE", "ABI", "MSFT", "KBC"].includes(r.symbol)),
    [rows]
  );

  const dd = pf ? pf.drawdown_eur : 0;
  const ddLim = pf?.drawdown_limit_eur || 0;

  return (
    <>
      <div className="pagehead"><h1>Dashboard</h1>
        <span className="s">{vault ? `vault: ${vault.rows.toLocaleString()} rows · ${vault.symbols_with_prices}/${vault.universe} symbols · to ${vault.last_date}` : "…"}</span>
        {quality && <span className={`badge ${quality.gate === "PASS" ? "ok" : "warn"}`}>GATE {quality.gate}</span>}
      </div>
      <p className="pagesub">Paper book · local fills · IBKR adapter arrives with account approval.</p>

      <div className="cards" style={{ marginBottom: 12 }}>
        <div className="card">
          <span className="k">equity</span>
          <span className="v">{pf ? fmtMoney(pf.equity, "EUR") : "…"}</span>
          <div className="s">cash {pf ? fmtMoney(pf.cash, "EUR") : "…"} · invested {pf ? fmtMoney(pf.invested, "EUR") : "…"}</div>
        </div>
        <div className="card">
          <span className="k">p&amp;l since start</span>
          <span className={`v ${pf && pf.pnl_since_start >= 0 ? "up" : "down"}`}>
            {pf ? `${pf.pnl_since_start >= 0 ? "+" : ""}${fmtMoney(pf.pnl_since_start, "EUR")}` : "…"}
          </span>
          <div className="s">benchmark comparison arrives with attribution (ph 7)</div>
        </div>
        <div className="card">
          <span className="k">open risk</span>
          <span className="v">{pf ? fmtMoney(pf.open_risk_eur, "EUR") : "…"}</span>
          <div className="s">sum of distance-to-"I-am-wrong" across positions</div>
        </div>
        <div className="card">
          <span className="k">drawdown used</span>
          <span className="v">{pf ? fmtMoney(dd, "EUR") : "…"}</span>
          <div className="meter"><div className={dd / (ddLim || 1) > 0.7 ? "hot" : ""}
            style={{ width: `${ddLim ? Math.min(100, (dd / ddLim) * 100) : 0}%` }} /></div>
          <div className="s">{ddLim ? `of your €${ddLim.toLocaleString()} limit` : "no limit set — constitution unsigned"}</div>
        </div>
      </div>

      <span className="k" style={{ margin: "10px 0 6px" }}>watchlist</span>
      <div className="strip" style={{ marginBottom: 14 }}>
        {watchlist.map((r) => (
          <div key={r.symbol} className="wtile" onClick={() => (window.location.hash = `#/company/${r.symbol}`)}>
            <span className="sym">{r.symbol}</span> <span className="nm">{r.name}</span>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
              <div>
                <div className="px">{r.currency === "USD" ? "$" : "€"}{r.price?.toFixed(2)}</div>
                <div className={`chg ${((r.day_change ?? 0) >= 0) ? "up" : "down"}`}>
                  {r.day_change != null ? `${r.day_change >= 0 ? "+" : ""}${(r.day_change * 100).toFixed(2)}%` : "—"}
                </div>
              </div>
              <Spark data={r.spark} w={62} h={26} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid31">
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: "10px 14px 0" }}><span className="k">positions</span></div>
          {pf && pf.positions.length > 0 ? (
            <table className="data">
              <thead><tr><th className="static">Symbol</th><th className="static">Thesis</th><th className="num static">Shares</th><th className="num static">Value €</th><th className="num static">P&amp;L</th></tr></thead>
              <tbody>
                {pf.positions.map((p) => (
                  <tr key={p.symbol} className="click" onClick={() => (window.location.hash = `#/company/${p.symbol}`)}>
                    <td className="mono">{p.symbol}</td>
                    <td className="s" style={{ maxWidth: 260, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.thesis || "—"}</td>
                    <td className="num">{p.shares}</td>
                    <td className="num">{p.value_eur.toLocaleString()}</td>
                    <td className={`num ${p.pnl_eur >= 0 ? "up" : "down"}`}>{p.pnl_eur >= 0 ? "+" : ""}{p.pnl_eur.toFixed(0)} ({(p.pnl_pct * 100).toFixed(1)}%)</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="loading" style={{ padding: "18px 14px" }}>
              no positions yet — open the <a href="#/desk">Trading Desk</a> to place your first gated paper order
            </div>
          )}
        </div>

        <div className="card">
          <span className="k">today's movers</span>
          {movers.up.map((r) => (
            <div key={r.symbol} className="costline" style={{ cursor: "pointer" }} onClick={() => (window.location.hash = `#/company/${r.symbol}`)}>
              <span className="mono">{r.symbol}</span>
              <span className="mono up">+{((r.day_change ?? 0) * 100).toFixed(2)}%</span>
            </div>
          ))}
          {movers.down.map((r) => (
            <div key={r.symbol} className="costline" style={{ cursor: "pointer" }} onClick={() => (window.location.hash = `#/company/${r.symbol}`)}>
              <span className="mono">{r.symbol}</span>
              <span className="mono down">{((r.day_change ?? 0) * 100).toFixed(2)}%</span>
            </div>
          ))}
          <Why lesson="Lesson 1 §3">Daily moves are mostly noise — this box is weather, not information. It exists so you learn to watch it calmly and act on nothing here.</Why>
        </div>
      </div>
    </>
  );
}
