import { useEffect, useState } from "react";
import { get } from "../api";

interface TodayData {
  jobs: { last_run: string | null; ok: boolean | null; steps: { name: string; ok: boolean; detail: string }[]; note?: string };
  alerts: { level: string; symbol: string | null; text: string }[];
  calendar: { symbol: string; event: string; date: string; days_away: number }[];
  brief: { at: string | null; items: { severity: string; title: string; detail: string; symbols: string[] }[] };
  tasks: { kind: string; card: string | null; symbol: string | null; text: string }[];
  portfolio: { equity: number; pnl: number; drawdown_eur: number; drawdown_limit_eur: number; positions: number; signed: boolean };
}

export function Today() {
  const [d, setD] = useState<TodayData | null>(null);
  const reload = () => get<TodayData>("/api/today").then(setD).catch(() => {});
  useEffect(() => {
    reload();
    const id = setInterval(reload, 30000); // marks to delayed quotes — the page stays alive
    return () => clearInterval(id);
  }, []);

  if (!d) return <div className="loading">assembling your day…</div>;
  const p = d.portfolio;

  return (
    <>
      <div className="pagehead"><h1>Today</h1>
        <span className="s">{new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</span>
      </div>

      <div className="cards" style={{ marginBottom: 12 }}>
        <div className="card"><span className="k">equity</span><span className="v">€{p.equity.toLocaleString()}</span>
          <div className="s">{p.positions} positions · P&L <span className={p.pnl >= 0 ? "up" : "down"}>{p.pnl >= 0 ? "+" : ""}€{p.pnl.toLocaleString()}</span></div></div>
        <div className="card"><span className="k">drawdown</span>
          <span className="v">€{p.drawdown_eur.toLocaleString()}</span>
          <div className="meter"><div className={p.drawdown_limit_eur && p.drawdown_eur / p.drawdown_limit_eur > 0.7 ? "hot" : ""}
            style={{ width: `${p.drawdown_limit_eur ? Math.min(100, p.drawdown_eur / p.drawdown_limit_eur * 100) : 0}%` }} /></div>
          <div className="s">{p.drawdown_limit_eur ? `of your €${p.drawdown_limit_eur.toLocaleString()} limit` : "no limit — unsigned"}</div></div>
        <div className="card"><span className="k">last night's jobs</span>
          <span className="v" style={{ fontSize: 15 }}>
            {d.jobs.last_run == null ? "never ran" : d.jobs.ok ? "all green" : "FAILED"}
          </span>
          <div className="s">
            {d.jobs.last_run == null
              ? "register the scheduler: scripts\\register-scheduler.ps1"
              : `${d.jobs.last_run.slice(0, 16).replace("T", " ")} · ${d.jobs.steps.map((s) => `${s.name} ${s.ok ? "✓" : "✗"}`).join(" · ")}`}
          </div></div>
      </div>

      {!p.signed && <SetupWizard onDone={reload} />}

      <Section title="needs you" empty="nothing needs you — that's a feature, not a gap">
        {d.tasks.map((t, i) => (
          <div key={i} className="lline">
            <span className={`pill2 ${t.kind === "setup" ? "alert" : ""}`}>{t.kind.replace("_", " ")}</span>
            <span style={{ flex: 1 }}>{t.text}</span>
            {t.kind !== "setup" && <a href="#/pipeline" className="mini-link">open →</a>}
          </div>
        ))}
        {d.alerts.map((a, i) => (
          <div key={`a${i}`} className="lline">
            <span className={`pill2 ${a.level === "ACT" ? "alert" : a.level === "WATCH" ? "watch" : ""}`}>{a.level}</span>
            <span style={{ flex: 1 }}>{a.text}</span>
            {a.symbol && <a href={`#/library/company/${a.symbol}`} className="mini-link">{a.symbol} →</a>}
          </div>
        ))}
      </Section>

      <div className="grid2" style={{ marginTop: 12 }}>
        <Section title="next 14 days" empty="no earnings or ex-dividend dates ahead (calendar refreshes nightly)">
          {d.calendar.map((c, i) => (
            <div key={i} className="lline">
              <span className="mono" style={{ width: 46 }}>{c.date.slice(5)}</span>
              <span className="mono" style={{ width: 56 }}><a href={`#/library/company/${c.symbol}`}>{c.symbol}</a></span>
              <span style={{ flex: 1 }}>{c.event === "earnings" ? "earnings" : "ex-dividend"} · in {c.days_away}d</span>
            </div>
          ))}
        </Section>
        <Section title={`engine brief ${d.brief.at ? "· " + d.brief.at.slice(0, 10) : ""}`} empty="no brief yet — runs with the nightly chain">
          {d.brief.items.map((f, i) => (
            <div key={i} className="lline">
              <span className={`pill2 ${f.severity === "ALERT" ? "alert" : f.severity === "CANDIDATE" ? "ok" : ""}`}>{f.severity}</span>
              <span style={{ flex: 1 }}><b style={{ fontSize: 12.5 }}>{f.title}</b>
                <div className="s">{f.symbols.map((s) => <a key={s} className="mono mini-link" href={`#/library/company/${s}`}>{s} </a>)}</div>
              </span>
            </div>
          ))}
        </Section>
      </div>
    </>
  );
}

function Section({ title, empty, children }: { title: string; empty: string; children: React.ReactNode }) {
  const arr = Array.isArray(children) ? children.flat().filter(Boolean) : [children];
  const has = arr.some((c) => Array.isArray(c) ? c.length : c);
  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <span className="k">{title}</span>
      {has ? <div style={{ marginTop: 6 }}>{children}</div> : <div className="s" style={{ padding: "8px 0" }}>{empty}</div>}
    </div>
  );
}

function SetupWizard({ onDone }: { onDone: () => void }) {
  const [dd, setDd] = useState("");
  const [months, setMonths] = useState("6");
  const [err, setErr] = useState("");
  async function sign() {
    setErr("");
    const r = await fetch("/api/constitution/sign", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_drawdown_eur: parseFloat(dd), emergency_fund_months: parseInt(months) }),
    });
    if (!r.ok) { setErr((await r.json()).detail ?? "failed"); return; }
    onDone();
  }
  return (
    <div className="card wizard" style={{ marginBottom: 12 }}>
      <span className="k">first-run setup — sign your risk constitution</span>
      <p style={{ fontSize: 13.5, margin: "8px 0" }}>
        Two numbers only you can choose. Everything else (1% risk per idea, 10% position cap, zero leverage)
        is already law. The Trading Desk unlocks the moment you sign.
      </p>
      <div className="frow"><span>Drawdown you can watch without panic, in euros</span>
        <input type="number" value={dd} placeholder="e.g. 1500" onChange={(e) => setDd(e.target.value)} /></div>
      <div className="frow"><span>Emergency fund kept outside, months</span>
        <input type="number" value={months} min={3} onChange={(e) => setMonths(e.target.value)} /></div>
      {err && <div className="blocklist">{err}</div>}
      <button className="btn" style={{ marginTop: 8 }} onClick={sign} disabled={!dd}>Sign — dated today, kept in git history</button>
    </div>
  );
}
