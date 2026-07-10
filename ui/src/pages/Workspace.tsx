import { useEffect, useMemo, useState } from "react";
import { get, Portfolio } from "../api";
import { TradePanel } from "../components/TradePanel";
import { Stage } from "./Company";

// THE WORKSPACE — the whole app on one screen (UX v3).
// LEFT: one list, three lenses (book / ideas / markets).
// CENTER: the selected symbol as instruments.
// RIGHT: ACT (gated trading + net-proceeds) and the FEED.

interface Signal { symbol: string; name: string; country: string; tier: string; price: number | null; composite: number | null }
interface PipeCard { id: string; symbol: string; stage: string; thesis: string; wrong_price: number | null }
interface TodayData {
  alerts: { level: string; symbol: string | null; text: string }[];
  calendar: { symbol: string; event: string; date: string; days_away: number }[];
  brief: { items: { severity: string; title: string; symbols: string[] }[] };
  tasks: { kind: string; symbol: string | null; text: string }[];
  jobs: { last_run: string | null; ok: boolean | null };
}
interface Proceeds {
  gross_eur: number; costs: { total: number }; net_sale_eur: number;
  gain_eur: number; cgt: { best_case: number; worst_case: number; exemption_eur: number };
  in_pocket_best: number; in_pocket_worst: number; note: string;
}

const STAGE_TAG: Record<string, string> = { INBOX: "idea", TRIAGE: "triage", DIVE: "thesis", DECISION: "DECIDE", LIVE: "live" };

export function Workspace({ initial }: { initial?: string }) {
  const [selected, setSelected] = useState(initial || "COLR");
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [cards, setCards] = useState<PipeCard[]>([]);
  const [today, setToday] = useState<TodayData | null>(null);
  const [mktFilter, setMktFilter] = useState<"ALL" | "BE" | "US">("ALL");
  const [proceeds, setProceeds] = useState<Proceeds | null>(null);

  const reloadPf = () => get<Portfolio>("/api/portfolio").then(setPf).catch(() => {});
  useEffect(() => {
    reloadPf();
    get<Signal[]>("/api/signals").then(setSignals).catch(() => {});
    get<PipeCard[]>("/api/pipeline").then(setCards).catch(() => {});
    get<TodayData>("/api/today").then(setToday).catch(() => {});
    const id = setInterval(() => { reloadPf(); get<TodayData>("/api/today").then(setToday).catch(() => {}); }, 30000);
    return () => clearInterval(id);
  }, []);

  // net-proceeds card for held symbols
  const held = pf?.positions.find((p) => p.symbol === selected);
  useEffect(() => {
    setProceeds(null);
    if (held) get<Proceeds>(`/api/position/${selected}/proceeds`).then(setProceeds).catch(() => {});
  }, [selected, held?.shares, held?.last]);

  useEffect(() => { window.location.hash = `#/w/${selected}`; }, [selected]);

  const openCards = cards.filter((c) => !["CLOSED", "PASSED"].includes(c.stage));
  const selectedCard = openCards.find((c) => c.symbol === selected);
  const markets = useMemo(() =>
    signals
      .filter((s) => s.tier !== "etf" && (mktFilter === "ALL" || s.country === mktFilter))
      .sort((a, b) => (b.composite ?? -1) - (a.composite ?? -1)).slice(0, 18),
    [signals, mktFilter]);

  return (
    <div className="ws">
      {/* ---------------- LEFT RAIL ---------------- */}
      <aside className="ws-rail">
        <div className="ws-sec">MY BOOK <span>{pf?.positions.length ?? "…"}</span></div>
        {pf && pf.positions.length === 0 && <div className="s" style={{ padding: "2px 8px 8px" }}>no positions yet — your first fill lands here</div>}
        {pf?.positions.map((p) => (
          <div key={p.symbol} className={`ws-row ${selected === p.symbol ? "sel" : ""}`} onClick={() => setSelected(p.symbol)}>
            <span className="sym">{p.symbol}</span>
            <span className={`mono ${p.pnl_pct >= 0 ? "up" : "down"}`}>{(p.pnl_pct * 100).toFixed(1)}%</span>
          </div>
        ))}

        <div className="ws-sec">IDEAS <span>{openCards.length}</span></div>
        {openCards.length === 0 && <div className="s" style={{ padding: "2px 8px 8px" }}>Ctrl+K → “+ pipeline” on any name</div>}
        {openCards.map((c) => (
          <div key={c.id} className={`ws-row ${selected === c.symbol ? "sel" : ""}`} onClick={() => setSelected(c.symbol)}>
            <span className="sym">{c.symbol}</span>
            <span className={`ws-tag ${c.stage === "DECISION" ? "hot" : ""}`}>{STAGE_TAG[c.stage] ?? c.stage.toLowerCase()}</span>
          </div>
        ))}

        <div className="ws-sec">MARKETS · by evidence
          <span className="ws-filter">
            {(["ALL", "BE", "US"] as const).map((f) => (
              <button key={f} className={mktFilter === f ? "on" : ""} onClick={() => setMktFilter(f)}>{f}</button>
            ))}
          </span>
        </div>
        {markets.map((s) => (
          <div key={s.symbol} className={`ws-row ${selected === s.symbol ? "sel" : ""}`} onClick={() => setSelected(s.symbol)}>
            <span className="sym">{s.symbol}</span>
            <span className="mono" style={{ color: "var(--muted)" }}>Σ{s.composite ?? "–"}</span>
          </div>
        ))}
      </aside>

      {/* ---------------- CENTER STAGE ---------------- */}
      <main className="ws-stage"><Stage symbol={selected} /></main>

      {/* ---------------- RIGHT RAIL ---------------- */}
      <aside className="ws-rail-r">
        <TradePanel key={selected} symbol={selected}
          currency={signals.find((s) => s.symbol === selected)?.tier === undefined ? "EUR" : (signals.find((s) => s.symbol === selected) as any)?.currency ?? "EUR"}
          lastClose={signals.find((s) => s.symbol === selected)?.price ?? held?.last ?? 0}
          initialWrong={selectedCard?.wrong_price ?? undefined}
          initialThesis={selectedCard?.thesis ?? undefined}
          onFilled={() => { reloadPf(); get<PipeCard[]>("/api/pipeline").then(setCards).catch(() => {}); }} />

        {held && proceeds && (
          <div className="card" style={{ padding: "12px 14px" }}>
            <span className="k">if you sell now — in your pocket 🇧🇪</span>
            <div className="costline" style={{ marginTop: 6 }}><span>gross ({held.shares} sh)</span><span className="mono">€{proceeds.gross_eur.toLocaleString()}</span></div>
            <div className="costline"><span>− spread+TOB+fee</span><span className="mono">−€{proceeds.costs.total.toFixed(0)}</span></div>
            <div className="costline"><span>= net sale</span><span className="mono">€{proceeds.net_sale_eur.toLocaleString()}</span></div>
            <div className="costline"><span>gain vs what you paid</span>
              <span className={`mono ${proceeds.gain_eur >= 0 ? "up" : "down"}`}>{proceeds.gain_eur >= 0 ? "+" : ""}€{proceeds.gain_eur.toFixed(0)}</span></div>
            <div className="costline"><span>− gains tax (10%)</span>
              <span className="mono">€{proceeds.cgt.best_case.toFixed(0)}–{proceeds.cgt.worst_case.toFixed(0)}</span></div>
            <div className="costline" style={{ fontWeight: 700 }}><span>IN YOUR POCKET</span>
              <span className="mono">€{proceeds.in_pocket_worst.toLocaleString()}–{proceeds.in_pocket_best.toLocaleString()}</span></div>
            <div className="s" style={{ marginTop: 6 }}>{proceeds.note}</div>
          </div>
        )}

        <div className="ws-sec" style={{ marginTop: 4 }}>FEED — needs you first</div>
        <div className="ws-feed">
          {today?.tasks.map((t, i) => (
            <FeedItem key={`t${i}`} tag={t.kind.replace("_", " ")} tone={t.kind === "setup" ? "act" : ""} text={t.text}
              onClick={t.symbol ? () => setSelected(t.symbol!) : undefined} />
          ))}
          {today?.alerts.map((a, i) => (
            <FeedItem key={`a${i}`} tag={a.level} tone={a.level === "ACT" ? "act" : a.level === "WATCH" ? "watch" : ""}
              text={a.text} onClick={a.symbol ? () => setSelected(a.symbol!) : undefined} />
          ))}
          {today?.brief.items.slice(0, 4).map((f, i) => (
            <FeedItem key={`b${i}`} tag={f.severity} tone={f.severity === "CANDIDATE" ? "ok" : ""} text={f.title}
              onClick={f.symbols[0] ? () => setSelected(f.symbols[0]) : undefined} />
          ))}
          {today?.calendar.slice(0, 5).map((c, i) => (
            <FeedItem key={`c${i}`} tag="cal" tone="watch" text={`${c.symbol} ${c.event === "earnings" ? "earnings" : "ex-div"} in ${c.days_away}d`}
              onClick={() => setSelected(c.symbol)} />
          ))}
          <div className="s" style={{ padding: "6px 2px" }}>
            jobs: {today?.jobs.last_run ? (today.jobs.ok ? "all green ✓" : "FAILED — check System") : "never ran"} ·
            <a href="#/library/system" className="mini-link"> system</a> · <a href="#/library/lab" className="mini-link">lab</a>
          </div>
        </div>
      </aside>
    </div>
  );
}

function FeedItem({ tag, tone, text, onClick }: { tag: string; tone?: string; text: string; onClick?: () => void }) {
  return (
    <div className={`ws-fitem ${onClick ? "click" : ""}`} onClick={onClick}>
      <span className={`ws-ftag ${tone ?? ""}`}>{tag}</span>
      <span>{text}</span>
    </div>
  );
}
