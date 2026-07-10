import { useEffect, useMemo, useRef, useState } from "react";
import { Company, get } from "../api";
import { mentorOn, toggleMentor } from "../mentor";

// The v2 chrome: brand + three surfaces + command palette (Ctrl+K) +
// market clocks + mentor toggle + constitution state. No sidebar.

function marketOpen(tz: string, openMin: number, closeMin: number): boolean {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: tz, hour: "2-digit", minute: "2-digit", weekday: "short", hour12: false,
  }).formatToParts(new Date());
  const gp = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const wd = gp("weekday");
  if (wd === "Sat" || wd === "Sun") return false;
  const mins = parseInt(gp("hour")) * 60 + parseInt(gp("minute"));
  return mins >= openMin && mins < closeMin;
}

const MENU: [string, string][] = [
  ["Autopilot (narrated plans)", "/autopilot"],
  ["Pipeline board", "/pipeline"],
  ["Today (classic)", "/today"],
  ["Screener table", "/library/screener"],
  ["Risk console", "/library/risk"],
  ["Backtest Lab", "/library/lab"],
  ["System & jobs", "/library/system"],
];

export function TopBar({ route }: { route: string }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Company[]>([]);
  const [sel, setSel] = useState(0);
  const [signed, setSigned] = useState<boolean | null>(null);
  const [mentor, setMentor] = useState(mentorOn());
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    get<Company[]>("/api/companies").then(setRows).catch(() => {});
    get<{ constitution_signed: boolean }>("/health").then((h) => setSigned(h.constitution_signed)).catch(() => {});
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const hits = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    return rows.filter((r) => r.symbol.toLowerCase().includes(s) || r.name.toLowerCase().includes(s)).slice(0, 7);
  }, [q, rows]);

  function open(symbol: string) {
    window.location.hash = `#/library/company/${symbol}`;
    setQ("");
  }
  async function addIdea(symbol: string) {
    await fetch("/api/pipeline/add", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, source: "palette" }),
    });
    window.location.hash = "#/pipeline";
    setQ("");
  }

  const ebr = marketOpen("Europe/Brussels", 540, 1050);
  const nyse = marketOpen("America/New_York", 570, 960);
  const active = (to: string) =>
    to === "/" ? route === "/" : route.startsWith(to) || (to === "/library" && route.startsWith("/company"));

  return (
    <div className="topbar">
      <a className="brand2" href="#/">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 3v18M3 21h18M6 3h12" />
          <path d="M6 3 3 10a3 3 0 0 0 6 0L6 3zM18 3l-3 7a3 3 0 0 0 6 0l-3-7z" />
        </svg>
        De Waag
      </a>
      <a className={`tab-main ${route === "/" || route.startsWith("/w/") ? "on" : ""}`} href="#/">Workspace</a>
      <details className="menu">
        <summary aria-label="more pages">▤</summary>
        <div className="menu-pop">
          {MENU.map(([label, to]) => (
            <a key={to} href={`#${to}`} onClick={(e) => (e.currentTarget.closest("details") as HTMLDetailsElement).open = false}>{label}</a>
          ))}
        </div>
      </details>
      <div className="search">
        <input ref={inputRef} placeholder="Ctrl+K — symbol, company…" value={q}
          onChange={(e) => { setQ(e.target.value); setSel(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setSel((s) => Math.min(s + 1, hits.length - 1));
            if (e.key === "ArrowUp") setSel((s) => Math.max(s - 1, 0));
            if (e.key === "Enter" && hits[sel]) open(hits[sel].symbol);
            if (e.key === "Escape") setQ("");
          }}
          aria-label="command palette" />
        {hits.length > 0 && (
          <div className="search-pop">
            {hits.map((h, i) => (
              <div key={h.symbol} className={`hit ${i === sel ? "sel" : ""}`}>
                <span className="mono" style={{ width: 52, cursor: "pointer" }} onMouseDown={() => open(h.symbol)}>{h.symbol}</span>
                <span style={{ flex: 1, cursor: "pointer" }} onMouseDown={() => open(h.symbol)}>{h.name}</span>
                <button className="mini" onMouseDown={(e) => { e.preventDefault(); addIdea(h.symbol); }}>+ pipeline</button>
              </div>
            ))}
          </div>
        )}
      </div>
      <span className="mkt"><span className={`dot ${ebr ? "open" : ""}`} />EBR</span>
      <span className="mkt"><span className={`dot ${nyse ? "open" : ""}`} />NYSE</span>
      <span className="spacer" />
      <button className={`chip ${mentor ? "on" : ""}`} style={{ fontSize: 11 }}
        onClick={() => setMentor(toggleMentor())} title="show/hide the teaching layer">
        mentor {mentor ? "on" : "off"}
      </button>
      {signed != null && (
        <span className={`badge ${signed ? "ok" : "warn"}`}>{signed ? "SIGNED" : "UNSIGNED"}</span>
      )}
    </div>
  );
}
