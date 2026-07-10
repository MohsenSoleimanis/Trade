import { useEffect, useMemo, useState } from "react";
import { CompanyDetail, get } from "../api";

interface Card {
  id: string; symbol: string; stage: string; source: string; note: string;
  created: string; thesis: string; wrong_price: number | null;
  pass_reason: string; grade: string | null; grade_note: string;
  history: { at: string; to: string; why: string }[];
}

const COLS = ["INBOX", "TRIAGE", "DIVE", "DECISION", "LIVE"];
const COL_HINT: Record<string, string> = {
  INBOX: "ideas land here", TRIAGE: "dossier ready — hour or pass?",
  DIVE: "thesis owed", DECISION: "buy or pass — both logged", LIVE: "exits armed",
};

export function Pipeline() {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [selId, setSelId] = useState<string | null>(null);
  const [newSym, setNewSym] = useState("");
  const reload = () => get<Card[]>("/api/pipeline").then(setCards).catch(() => {});
  useEffect(() => { reload(); }, []);

  const sel = useMemo(() => cards?.find((c) => c.id === selId) ?? null, [cards, selId]);
  const closed = (cards ?? []).filter((c) => c.stage === "CLOSED");
  const passed = (cards ?? []).filter((c) => c.stage === "PASSED");

  async function post(path: string, body: object) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error((await r.json()).detail ?? "failed");
    reload();
  }

  if (!cards) return <div className="loading">loading pipeline…</div>;

  return (
    <>
      <div className="pagehead"><h1>Pipeline</h1>
        <span className="s">nothing gets bought that didn't travel this board</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <input className="addideain" placeholder="symbol…" value={newSym}
            onChange={(e) => setNewSym(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && newSym && post("/api/pipeline/add", { symbol: newSym }).then(() => setNewSym("")).catch(alert)} />
          <button className="btn" onClick={() => newSym && post("/api/pipeline/add", { symbol: newSym }).then(() => setNewSym("")).catch(alert)}>+ idea</button>
        </span>
      </div>

      <div className="kanban2">
        {COLS.map((col) => {
          const inCol = cards.filter((c) => c.stage === col);
          return (
            <div key={col} className="kcol2">
              <div className="kh2">{col} <span>{inCol.length}</span><div className="khint">{COL_HINT[col]}</div></div>
              {inCol.map((c) => (
                <div key={c.id} className={`kcard2 ${selId === c.id ? "sel" : ""}`} onClick={() => setSelId(c.id === selId ? null : c.id)}>
                  <span className="mono" style={{ fontWeight: 700 }}>{c.symbol}</span>
                  <div className="s">{c.stage === "LIVE" ? `exit @ ${c.wrong_price ?? "—"}` : c.note || c.source}</div>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {sel && <CardPanel card={sel} onAction={post} onClose={() => setSelId(null)} />}

      {(closed.length > 0 || passed.length > 0) && (
        <div className="card" style={{ marginTop: 14 }}>
          <span className="k">closed & passed — the record</span>
          {closed.map((c) => (
            <div key={c.id} className="lline">
              <span className="mono" style={{ width: 56 }}>{c.symbol}</span>
              <span style={{ flex: 1 }}>
                {c.grade ? <>graded <b>{c.grade.replace("_", " ")}</b> — {c.grade_note || "no note"}</>
                  : <GradeForm id={c.id} onAction={post} />}
              </span>
            </div>
          ))}
          {passed.map((c) => (
            <div key={c.id} className="lline">
              <span className="mono" style={{ width: 56 }}>{c.symbol}</span>
              <span style={{ flex: 1 }} className="s">passed: {c.pass_reason}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function GradeForm({ id, onAction }: { id: string; onAction: (p: string, b: object) => Promise<void> }) {
  const [note, setNote] = useState("");
  return (
    <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
      <b>post-mortem due:</b>
      {["thesis_right", "thesis_wrong", "lucky", "unlucky"].map((g) => (
        <button key={g} className="mini" onClick={() => onAction(`/api/pipeline/${id}/grade`, { grade: g, note }).catch(alert)}>{g.replace("_", " ")}</button>
      ))}
      <input className="addideain" style={{ width: 180 }} placeholder="one-line note" value={note} onChange={(e) => setNote(e.target.value)} />
    </span>
  );
}

function CardPanel({ card, onAction, onClose }: { card: Card; onAction: (p: string, b: object) => Promise<void>; onClose: () => void }) {
  const [d, setD] = useState<CompanyDetail | null>(null);
  const [thesis, setThesis] = useState(card.thesis);
  const [wrong, setWrong] = useState(card.wrong_price?.toString() ?? "");
  const [passReason, setPassReason] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => { get<CompanyDetail>(`/api/company/${card.symbol}`).then(setD).catch(() => {}); }, [card.symbol]);

  const advance = () => onAction(`/api/pipeline/${card.id}/advance`,
    { thesis, wrong_price: wrong ? parseFloat(wrong) : null }).catch((e) => setErr(String(e.message ?? e)));

  return (
    <div className="card" style={{ marginTop: 14 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <span className="k" style={{ margin: 0 }}>{card.symbol} · {card.stage}</span>
        {d && <span className="s">{d.profile.name} · {d.currency === "USD" ? "$" : "€"}{d.last_price.toFixed(2)}</span>}
        <a className="mini-link" href={`#/library/company/${card.symbol}`}>full dossier →</a>
        <button className="mini" style={{ marginLeft: "auto" }} onClick={onClose}>close</button>
      </div>

      {d && (
        <div style={{ margin: "10px 0" }}>
          <span style={{ display: "flex", gap: 14, flexWrap: "wrap" }} className="mono">
            {(["q_score", "v_score", "m_score", "composite"] as const).map((k) => (
              <span key={k} style={{ fontSize: 12 }}>{{ q_score: "quality", v_score: "value", m_score: "momentum", composite: "Σ" }[k]}{" "}
                <b>{d.engine.scores[k] ?? "—"}</b></span>
            ))}
          </span>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {d.engine.bullets.slice(0, 4).map((b, i) => <li key={i} style={{ fontSize: 12.5, margin: "3px 0" }}>{b}</li>)}
          </ul>
        </div>
      )}

      {(card.stage === "DIVE" || card.stage === "TRIAGE" || card.stage === "INBOX") && (
        <>
          <div className="frow"><span>thesis</span>
            <textarea value={thesis} onChange={(e) => setThesis(e.target.value)}
              placeholder="why this, why now, and what would prove me wrong" /></div>
          <div className="frow"><span>"I am wrong at…"</span>
            <input type="number" value={wrong} onChange={(e) => setWrong(e.target.value)} /></div>
        </>
      )}

      {err && <div className="blocklist">{err}</div>}

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        {["INBOX", "TRIAGE", "DIVE"].includes(card.stage) && (
          <button className="btn" onClick={advance}>advance →</button>
        )}
        {card.stage === "DECISION" && (
          <a className="btn" style={{ textDecoration: "none" }} href={`#/library/desk/${card.symbol}`}>open order ticket →</a>
        )}
        {!["LIVE", "CLOSED", "PASSED"].includes(card.stage) && (
          <>
            <input className="addideain" style={{ width: 220 }} placeholder="pass reason (kept forever)"
              value={passReason} onChange={(e) => setPassReason(e.target.value)} />
            <button className="mini" onClick={() => onAction(`/api/pipeline/${card.id}/pass`, { reason: passReason }).catch((e) => setErr(String(e.message ?? e)))}>pass</button>
          </>
        )}
      </div>
    </div>
  );
}
