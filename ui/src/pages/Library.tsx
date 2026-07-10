import { useEffect, useState } from "react";
import { get, VaultStatus } from "../api";
import { BacktestLab } from "./BacktestLab";
import { Company } from "./Company";
import { Research } from "./Research";
import { RiskConsole } from "./RiskConsole";
import { Screener } from "./Screener";
import { TradingDesk } from "./TradingDesk";

// Surface 3: the knowledge base. Sub-navigation over the proven engine-room
// pages; System collects vault health, jobs and governance in one place.

const SECTIONS: [string, string][] = [
  ["dossiers", "Dossiers"], ["screener", "Screener"], ["risk", "Risk"],
  ["desk", "Desk"], ["lab", "Lab"], ["system", "System"],
];

export function Library({ route }: { route: string }) {
  // routes: /library, /library/<section>, /library/company/<SYM>, /library/desk/<SYM>
  const parts = route.split("/").filter(Boolean); // ["library", ...]
  const section = parts[1] ?? "dossiers";

  let body: JSX.Element;
  if (section === "company") body = <Company symbol={parts[2]} />;
  else if (section === "screener") body = <Screener />;
  else if (section === "risk") body = <RiskConsole />;
  else if (section === "desk") body = <TradingDesk route={"/desk" + (parts[2] ? `/${parts[2]}` : "")} />;
  else if (section === "lab") body = <BacktestLab />;
  else if (section === "system") body = <SystemPanel />;
  else body = <Research />;

  return (
    <>
      <div className="chips" style={{ marginBottom: 16 }}>
        {SECTIONS.map(([key, label]) => (
          <a key={key} className={`chip ${section === key || (section === "company" && key === "dossiers") ? "on" : ""}`}
            href={`#/library/${key}`} style={{ textDecoration: "none" }}>{label}</a>
        ))}
      </div>
      {body}
    </>
  );
}

function SystemPanel() {
  const [vault, setVault] = useState<VaultStatus | null>(null);
  const [jobs, setJobs] = useState<{ last_run: string | null; ok: boolean | null; steps: { name: string; ok: boolean; detail: string }[] } | null>(null);
  const [con, setCon] = useState<{ signed: boolean; signed_on: string | null; max_drawdown_eur: number; max_risk_per_idea_pct: number; max_position_pct: number; leverage: number } | null>(null);

  useEffect(() => {
    get<VaultStatus>("/api/vault/status").then(setVault).catch(() => {});
    get<{ jobs: typeof jobs }>("/api/today").then((t: any) => setJobs(t.jobs)).catch(() => {});
    get<typeof con & object>("/api/constitution").then(setCon as any).catch(() => {});
  }, []);

  return (
    <>
      <div className="pagehead"><h1>System</h1></div>
      <div className="cards">
        <div className="card"><span className="k">vault</span>
          <span className="v" style={{ fontSize: 16 }}>{vault ? vault.rows.toLocaleString() : "…"} rows</span>
          <div className="s">{vault?.symbols_with_prices}/{vault?.universe} symbols · to {vault?.last_date}</div></div>
        <div className="card"><span className="k">nightly chain</span>
          <span className="v" style={{ fontSize: 16 }}>{jobs?.last_run ? (jobs.ok ? "green" : "FAILED") : "not registered"}</span>
          <div className="s">{jobs?.last_run
            ? jobs.steps.map((s) => `${s.name} ${s.ok ? "✓" : "✗"}`).join(" · ")
            : "run once: scripts\\register-scheduler.ps1 — then it works while you sleep"}</div></div>
        <div className="card"><span className="k">constitution</span>
          <span className="v" style={{ fontSize: 16 }}>{con ? (con.signed ? `signed ${con.signed_on}` : "UNSIGNED") : "…"}</span>
          <div className="s">risk/idea {con?.max_risk_per_idea_pct}% · cap {con?.max_position_pct}% · leverage {con?.leverage} · drawdown €{con?.max_drawdown_eur?.toLocaleString()}</div></div>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <span className="k">governance</span>
        <p style={{ fontSize: 13.5, margin: "6px 0 0" }}>
          Every trade is journaled with its thesis; every backtest is counted in the experiment ledger;
          every engine brief is stored with its timestamp. Amendments to the constitution happen in git —
          the audit trail is the repository itself.
        </p>
      </div>
    </>
  );
}
