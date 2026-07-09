import { useEffect, useMemo, useRef, useState } from "react";
import { Company, get } from "../api";

// The terminal top bar: global symbol search (the fastest way anywhere),
// market clocks, and the constitution's state — always visible, because
// governance is not a settings page.

function marketOpen(tz: string, openMin: number, closeMin: number): boolean {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: tz, hour: "2-digit", minute: "2-digit", weekday: "short", hour12: false,
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const wd = get("weekday");
  if (wd === "Sat" || wd === "Sun") return false;
  const mins = parseInt(get("hour")) * 60 + parseInt(get("minute"));
  return mins >= openMin && mins < closeMin;
}

export function TopBar() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Company[]>([]);
  const [sel, setSel] = useState(0);
  const [signed, setSigned] = useState<boolean | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    get<Company[]>("/api/companies").then(setRows).catch(() => {});
    get<{ constitution_signed: boolean }>("/health").then((h) => setSigned(h.constitution_signed)).catch(() => {});
  }, []);

  const hits = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    return rows
      .filter((r) => r.symbol.toLowerCase().includes(s) || r.name.toLowerCase().includes(s))
      .slice(0, 7);
  }, [q, rows]);

  function go(symbol: string) {
    window.location.hash = `#/company/${symbol}`;
    setQ("");
  }

  const ebr = marketOpen("Europe/Brussels", 9 * 60, 17 * 60 + 30);
  const nyse = marketOpen("America/New_York", 9 * 60 + 30, 16 * 60);

  return (
    <div className="topbar">
      <div className="search" ref={boxRef}>
        <input
          placeholder="Search symbol or company…  (e.g. LOTB)"
          value={q}
          onChange={(e) => { setQ(e.target.value); setSel(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setSel((s) => Math.min(s + 1, hits.length - 1));
            if (e.key === "ArrowUp") setSel((s) => Math.max(s - 1, 0));
            if (e.key === "Enter" && hits[sel]) go(hits[sel].symbol);
            if (e.key === "Escape") setQ("");
          }}
          aria-label="search companies"
        />
        {hits.length > 0 && (
          <div className="search-pop">
            {hits.map((h, i) => (
              <div key={h.symbol} className={`hit ${i === sel ? "sel" : ""}`}
                onMouseDown={() => go(h.symbol)}>
                <span className="mono" style={{ width: 52 }}>{h.symbol}</span>
                <span style={{ flex: 1 }}>{h.name}</span>
                <span className="s">{h.exchange}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <span className="mkt"><span className={`dot ${ebr ? "open" : ""}`} />EBR {ebr ? "OPEN" : "CLOSED"}</span>
      <span className="mkt"><span className={`dot ${nyse ? "open" : ""}`} />NYSE {nyse ? "OPEN" : "CLOSED"}</span>
      <span className="spacer" />
      {signed != null && (
        <span className={`badge ${signed ? "ok" : "warn"}`}>
          {signed ? "CONSTITUTION SIGNED" : "CONSTITUTION UNSIGNED"}
        </span>
      )}
    </div>
  );
}
