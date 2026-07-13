import { useEffect, useMemo, useState } from "react";
import { get, post } from "../api";
import { ChartMarker, SignalChart } from "../components/SignalChart";
import "../console.css";

// THE ENGINE TERMINAL — one cohesive chart-first screen (Trade-with-Jarvis
// style): watchlist · big candlestick chart with trend cloud + your trades
// marked on it · the engine's read, the action, and the news. Honest engine
// underneath; no day-trade signals.

interface Position { symbol: string; name: string; shares: number; currency: string; last: number; value_eur: number; cost_eur: number; pnl_eur: number; pnl_pct: number; }
interface Trade { at: string; symbol: string; side: string; shares: number; fill: number; }
interface Book { equity: number; cash: number; pnl_eur: number; pnl_pct: number; unrealized_pnl: number; realized_pnl: number; positions: Position[]; trades: Trade[]; }
interface Proposal { id: string; symbol: string; name: string; side: string; shares: number; price: number; currency: string; tier: string; status: string; wrong_price?: number; stop_pct?: number; est_cost_eur?: number; notional_eur?: number; confidence?: number; rationale?: string; blocks?: string[]; }
interface Console { book: Book; regime: { label: string; risk: string }; layers: { l9: { proposals: Proposal[] } }; }
interface Company { symbol: string; name: string; price: number | null; day_change: number | null; country: string; tier: string; }
interface Detail {
  symbol: string; profile: { name: string; currency: string; exchange: string; tier: string };
  last_price: number; day_change: number | null; high_52w: number; low_52w: number; currency: string;
  candles: { time: string; open: number; high: number; low: number; close: number; volume: number }[];
  engine: { scores: { q_score: number | null; v_score: number | null; m_score: number | null; composite: number | null }; bullets: string[] };
}
interface Outlook { news: { when: string | null; title: string; source: string; link?: string | null }[]; }

const eur = (n: number, d = 0) => "€" + n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const pc = (n: number | null | undefined) => (n == null ? "flat" : n > 0 ? "up" : n < 0 ? "down" : "flat");
const pct = (n: number | null | undefined, d = 2) => (n == null ? "—" : (n >= 0 ? "+" : "") + (n * 100).toFixed(d) + "%");
type Left = "holdings" | "watch";
const TFS: [string, number][] = [["1M", 21], ["3M", 63], ["6M", 126], ["MAX", 999]];

export function EngineConsole() {
  const [c, setC] = useState<Console | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [sym, setSym] = useState<string>("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [outlook, setOutlook] = useState<Outlook | null>(null);
  const [left, setLeft] = useState<Left>("holdings");
  const [tf, setTf] = useState(3);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const loadConsole = (rebuild = false) =>
    get<Console>(`/api/auto/console${rebuild ? "?rebuild=true" : ""}`).then((d) => {
      setC(d);
      if (!sym) setSym(d.book.positions[0]?.symbol ?? d.layers.l9.proposals[0]?.symbol ?? "WEBN");
    }).catch(() => {});

  useEffect(() => {
    loadConsole(false);
    get<Company[]>("/api/companies").then(setCompanies).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!sym) return;
    setDetail(null); setOutlook(null);
    get<Detail>(`/api/company/${sym}`).then(setDetail).catch(() => {});
    get<Outlook>(`/api/company/${sym}/outlook`).then(setOutlook).catch(() => {});
  }, [sym]);

  const act = async (p: Proposal, approve: boolean) => {
    setBusy(true); setFlash(null);
    try {
      const r = await post<{ ok: boolean; error?: string; execution?: { blocks?: string[] } }>(
        approve ? "/api/auto/approve" : "/api/auto/reject", approve ? { id: p.id } : { id: p.id, reason: "not now" });
      setFlash(r.ok ? `${approve ? "Filled" : "Rejected"} ${p.side} ${p.shares} ${p.symbol}` : `Not filled: ${r.error ?? r.execution?.blocks?.[0] ?? "gate"}`);
      loadConsole(false);
      setTimeout(() => setFlash(null), 4000);
    } catch (e) { setFlash(String(e)); } finally { setBusy(false); }
  };

  const priceMap = useMemo(() => Object.fromEntries(companies.map((x) => [x.symbol, x])), [companies]);
  const watch = useMemo(() => {
    const pri = ["WEBN", "IMEU", "EMIM"];
    return companies.filter((x) => x.tier !== "fx" && x.tier !== "macro")
      .sort((a, b) => (pri.indexOf(b.symbol)) - (pri.indexOf(a.symbol)) || (b.day_change ?? 0) - (a.day_change ?? 0));
  }, [companies]);

  if (!c) return <div className="tm"><div className="tm-empty" style={{ padding: 40 }}>loading terminal…</div></div>;
  const b = c.book;
  const held = new Set(b.positions.map((p) => p.symbol));
  const candles = detail?.candles ?? [];
  const shown = tf >= 900 ? candles : candles.slice(-TFS[tf][1]);
  const markers: ChartMarker[] = (b.trades ?? []).filter((t) => t.symbol === sym)
    .map((t) => ({ time: t.at.slice(0, 10), side: t.side as "BUY" | "SELL", text: `${t.side} ${t.shares}` }));
  const trendUp = shown.length >= 2 && shown[shown.length - 1].close >= (shown.reduce((s, x) => s + x.close, 0) / shown.length);
  const order = c.layers.l9.proposals.find((p) => p.symbol === sym);
  const pos = b.positions.find((p) => p.symbol === sym);

  return (
    <div className="tm">
      {/* top bar */}
      <div className="tm-top">
        <a className="tm-brand" href="#/" style={{ textDecoration: "none", color: "inherit" }} title="back to workspace">◄ De&nbsp;<b>Waag</b></a>
        <div className="tm-acct">
          <div className="a"><div className="k">Equity</div><div className="v">{eur(b.equity, 2)}</div></div>
          <div className="a"><div className="k">Total P&amp;L</div><div className={`v ${pc(b.pnl_eur)}`}>{(b.pnl_eur >= 0 ? "+" : "") + eur(b.pnl_eur, 2)}</div></div>
          <div className="a"><div className="k">Open</div><div className={`v ${pc(b.unrealized_pnl)}`}>{(b.unrealized_pnl >= 0 ? "+" : "") + eur(b.unrealized_pnl, 2)}</div></div>
          <div className="a"><div className="k">Realized</div><div className={`v ${pc(b.realized_pnl)}`}>{(b.realized_pnl >= 0 ? "+" : "") + eur(b.realized_pnl, 2)}</div></div>
          <div className="a"><div className="k">Cash</div><div className="v">{eur(b.cash, 0)}</div></div>
        </div>
        <div className="grow" />
        <span className="tm-ordbadge">regime: <b>{c.regime.label}</b></span>
        <button className="tm-btn" disabled={busy} onClick={() => loadConsole(true)}>↻ re-run engine</button>
      </div>

      <div className="tm-body">
        {/* left: watchlist / holdings */}
        <div className="tm-left">
          <div className="tm-ltabs">
            <button className={left === "holdings" ? "on" : ""} onClick={() => setLeft("holdings")}>Holdings ({b.positions.length})</button>
            <button className={left === "watch" ? "on" : ""} onClick={() => setLeft("watch")}>Watchlist</button>
          </div>
          <div className="tm-list">
            {left === "holdings" && b.positions.length === 0 && (
              <div className="tm-empty">No positions yet. Pick a name from the <b>Watchlist</b>, then approve the engine's order on the right.</div>
            )}
            {left === "holdings" && b.positions.map((p) => (
              <div key={p.symbol} className={`tm-row ${sym === p.symbol ? "on" : ""}`} onClick={() => setSym(p.symbol)}>
                <div><div className="sym">{p.symbol}</div><div className="nm">{p.shares} sh · {eur(p.value_eur, 0)}</div></div>
                <div><div className="px">{p.last.toFixed(2)}</div><div className={`chg ${pc(p.pnl_eur)}`}>{pct(p.pnl_pct)}</div></div>
              </div>
            ))}
            {left === "watch" && watch.map((x) => (
              <div key={x.symbol} className={`tm-row ${sym === x.symbol ? "on" : ""}`} onClick={() => setSym(x.symbol)}>
                <div><div className="sym">{x.symbol}{held.has(x.symbol) ? " ●" : ""}</div><div className="nm">{x.name}</div></div>
                <div><div className="px">{x.price?.toFixed(2) ?? "—"}</div><div className={`chg ${pc(x.day_change)}`}>{pct(x.day_change)}</div></div>
              </div>
            ))}
          </div>
        </div>

        {/* center: chart */}
        <div className="tm-center">
          <div className="tm-chead">
            <div className="title"><b>{sym}</b><span className="nm">{detail?.profile.name ?? priceMap[sym]?.name ?? ""}</span></div>
            {detail && <>
              <span className="price">{detail.last_price.toFixed(2)} <span style={{ fontSize: 13, color: "var(--muted)" }}>{detail.currency === "USD" ? "$" : "€"}</span></span>
              <span className={`chg ${pc(detail.day_change)}`}>{pct(detail.day_change)}</span>
            </>}
            <span className={`tm-trend ${trendUp ? "up" : "down"}`}>{trendUp ? "▲ UPTREND" : "▼ DOWNTREND"} · vs avg</span>
            <div className="grow" />
            <div className="tm-tf">
              {TFS.map(([lab], i) => <button key={lab} className={tf === i ? "on" : ""} onClick={() => setTf(i)}>{lab}</button>)}
            </div>
          </div>
          <div className="tm-chart">
            {detail ? <SignalChart data={shown} markers={markers} height={430} /> : <div className="tm-empty" style={{ padding: 40 }}>loading chart…</div>}
            {flash && <div className="tm-flash">{flash}</div>}
          </div>
          <div className="tm-legend">
            <span><span className="sw" style={{ background: "#16C784" }} /> up candle</span>
            <span><span className="sw" style={{ background: "#F0616D" }} /> down candle</span>
            <span><span className="sw" style={{ background: "rgba(120,170,255,.8)" }} /> 50-day average</span>
            <span><span className="sw" style={{ background: "rgba(22,199,132,.4)" }} /> trend cloud (price vs long-term avg)</span>
            <span>▲▼ = the engine's trades</span>
          </div>
        </div>

        {/* right: engine read + action + news */}
        <div className="tm-right">
          <div className="scroll">
            {/* engine read */}
            <div className="tm-sec">
              <div className="h">Engine read · {sym}</div>
              {detail ? <>
                <div className="tm-score">
                  {(["q_score", "v_score", "m_score", "composite"] as const).map((k) => (
                    <div className="s" key={k}><div className="n">{detail.engine.scores[k] ?? "—"}</div><div className="l">{k === "composite" ? "score" : k.replace("_score", "")}</div></div>
                  ))}
                </div>
                {detail.engine.bullets.slice(0, 4).map((bl, i) => (
                  <div className="tm-bul" key={i}><span className="d">›</span><span>{bl.replace(/^[✓⚠] /, "")}</span></div>
                ))}
              </> : <div className="tm-hold">reading…</div>}
            </div>

            {/* action */}
            <div className="tm-sec tm-action">
              <div className="h">Action</div>
              {order && order.status === "pending" ? (
                <div className="tm-order">
                  <div className="row1"><span className={`side ${order.side.toLowerCase()}`}>{order.side}</span> <b>{order.shares} {order.symbol}</b>
                    {order.tier === "etf" && <span style={{ fontSize: 10, color: "var(--accent)" }}>basket core</span>}</div>
                  <div className="facts">
                    {order.notional_eur != null && <span>size <b>{eur(order.notional_eur, 0)}</b></span>}
                    {order.wrong_price != null ? <span>stop <b>{order.wrong_price} (−{order.stop_pct}%)</b></span> : <span>stop <b>none</b></span>}
                    {order.est_cost_eur != null && <span>cost <b>€{order.est_cost_eur.toFixed(2)}</b></span>}
                    {order.confidence != null && <span>conviction <b>{(order.confidence * 100).toFixed(0)}%</b></span>}
                  </div>
                  {order.rationale && (
                    <details className="tm-why"><summary>▸ why</summary><div className="b">{order.rationale}</div></details>
                  )}
                  <div className="tm-acts">
                    <button className="tm-approve" disabled={busy} onClick={() => act(order, true)}>✓ Approve buy</button>
                    <button className="tm-reject" disabled={busy} onClick={() => act(order, false)}>Skip</button>
                  </div>
                </div>
              ) : pos ? (
                <div className="tm-hold">You hold <b>{pos.shares} {pos.symbol}</b> worth <b>{eur(pos.value_eur, 2)}</b>,
                  <span className={pc(pos.pnl_eur)}> {(pos.pnl_eur >= 0 ? "+" : "") + eur(pos.pnl_eur, 2)} ({pct(pos.pnl_pct)})</span>.
                  The engine has no new order here right now — it holds.</div>
              ) : (
                <div className="tm-hold">No order for <b>{sym}</b>. The engine only proposes trades that fit the target book
                  and clear its risk &amp; cost checks. Hit <b>↻ re-run engine</b> to refresh, or pick a held name.</div>
              )}
            </div>

            {/* news */}
            <div className="tm-sec tm-news">
              <div className="h">News · context, not a signal</div>
              {!outlook && <div className="tm-hold">loading…</div>}
              {outlook && outlook.news.length === 0 && <div className="tm-hold">Quiet — no recent coverage.</div>}
              {outlook && outlook.news.slice(0, 6).map((n, i) => (
                <a key={i} href={n.link ?? undefined} target="_blank" rel="noreferrer">
                  {n.title}<div className="meta">{n.when ?? "—"} · {n.source}</div>
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
