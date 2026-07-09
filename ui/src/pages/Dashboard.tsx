import { useEffect, useState } from "react";
import { get, VaultStatus } from "../api";
import { Why } from "../components/Why";

interface Quality { gate: string; findings: { level: string; check: string; symbol: string; detail: string }[] }
interface Constitution { signed: boolean; max_risk_per_idea_pct: number; max_position_pct: number; max_drawdown_eur: number; leverage: number; owner: string }

export function Dashboard() {
  const [vault, setVault] = useState<VaultStatus | null>(null);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [con, setCon] = useState<Constitution | null>(null);

  useEffect(() => {
    get<VaultStatus>("/api/vault/status").then(setVault).catch(() => {});
    get<Constitution>("/api/constitution").then(setCon).catch(() => {});
    get<Quality>("/api/vault/quality").then(setQuality).catch(() => {});
  }, []);

  return (
    <>
      <div className="pagehead"><h1>Dashboard</h1>
        {con && <span className={`badge ${con.signed ? "ok" : "warn"}`}>{con.signed ? "CONSTITUTION SIGNED" : "CONSTITUTION UNSIGNED"}</span>}
      </div>
      <p className="pagesub">Phase 2 — research era. Portfolio &amp; attribution arrive with the Trading Desk (phase 3).</p>

      <div className="cards">
        <div className="card">
          <span className="k">data vault</span>
          <span className="v">{vault ? vault.rows.toLocaleString() : "…"}</span>
          <div className="s">price rows · {vault?.symbols_with_prices ?? "…"} of {vault?.universe ?? "…"} symbols · to {vault?.last_date ?? "…"}</div>
        </div>
        <div className="card">
          <span className="k">quality gate</span>
          <span className="v">{quality ? quality.gate : "…"}</span>
          <div className="s">
            {quality
              ? `${quality.findings.filter(f => f.level === "CRITICAL").length} critical · ${quality.findings.filter(f => f.level === "WARN").length} warnings (incl. real 2008 history)`
              : "running checks…"}
          </div>
          <Why lesson="Phase 1 / master plan L7">A system silently fed garbage happily trades garbage. The gate runs before anything downstream trusts the data — FAIL quarantines a symbol everywhere.</Why>
        </div>
        <div className="card">
          <span className="k">risk constitution</span>
          <span className="v">{con ? `${con.max_risk_per_idea_pct}% / ${con.max_position_pct}%` : "…"}</span>
          <div className="s">risk per idea / position cap · leverage {con?.leverage ?? "…"} · drawdown limit €{con?.max_drawdown_eur?.toLocaleString() ?? "…"}</div>
          <Why lesson="Lesson 6">These numbers gate every future order ticket. Unsigned = Trading Desk stays locked. Sign it in config/risk-constitution.yaml.</Why>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <span className="k">start here</span>
        <p style={{ margin: "8px 0 0" }}>
          Open <a href="#/research">Research</a> and click any company — every number you learned in
          Lessons 3 &amp; 4 is computed live from your own vault, with a “why” under each one.
          Try <a href="#/company/LOTB">Lotus Bakeries</a>, your homework stock.
        </p>
      </div>
    </>
  );
}
