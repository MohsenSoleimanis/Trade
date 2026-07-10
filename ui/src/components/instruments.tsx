// Visual instruments — the terminal's language. Numbers become gauges,
// ranges and heat, readable at a glance; sentences retreat to mentor mode.

const col = (v: number | null) =>
  v == null ? "var(--muted)" : v >= 67 ? "var(--green)" : v >= 34 ? "var(--blue)" : "var(--red)";

/** Radial score gauge, 0–100. */
export function Gauge({ value, label, size = 78 }: { value: number | null; label: string; size?: number }) {
  const r = (size - 12) / 2;
  const cx = size / 2, cy = size / 2;
  const startA = 135, sweepMax = 270;
  const sweep = value == null ? 0 : (Math.max(0, Math.min(100, value)) / 100) * sweepMax;
  const arc = (a0: number, a1: number) => {
    const p = (a: number) => {
      const rad = ((a - 90) * Math.PI) / 180;
      return `${cx + r * Math.cos(rad)},${cy + r * Math.sin(rad)}`;
    };
    const large = a1 - a0 > 180 ? 1 : 0;
    return `M ${p(a0)} A ${r} ${r} 0 ${large} 1 ${p(a1)}`;
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
      <svg width={size} height={size} role="img" aria-label={`${label} ${value ?? "n/a"} of 100`}>
        <path d={arc(startA, startA + sweepMax)} fill="none" stroke="var(--code-bg)" strokeWidth={7} strokeLinecap="round" />
        {value != null && (
          <path d={arc(startA, startA + Math.max(sweep, 2))} fill="none" stroke={col(value)} strokeWidth={7} strokeLinecap="round" />
        )}
        <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle"
          fontSize={size * 0.28} fontWeight={700} fill="var(--ink)"
          fontFamily="'JetBrains Mono', Consolas, monospace">{value ?? "—"}</text>
      </svg>
      <span className="k" style={{ letterSpacing: "0.08em" }}>{label}</span>
    </div>
  );
}

/** Horizontal range bar with a marker (52-week range, valuation band…). */
export function RangeBar({ lo, hi, value, band, loLabel, hiLabel, fmt }: {
  lo: number; hi: number; value: number;
  band?: [number, number]; loLabel?: string; hiLabel?: string;
  fmt?: (x: number) => string;
}) {
  const f = fmt ?? ((x: number) => x.toFixed(0));
  const span = hi - lo || 1;
  const pos = Math.max(0, Math.min(1, (value - lo) / span)) * 100;
  const b0 = band ? Math.max(0, Math.min(1, (band[0] - lo) / span)) * 100 : null;
  const b1 = band ? Math.max(0, Math.min(1, (band[1] - lo) / span)) * 100 : null;
  return (
    <div>
      <div style={{ position: "relative", height: 18, margin: "4px 0 2px" }}>
        <div style={{ position: "absolute", top: 7, left: 0, right: 0, height: 4, borderRadius: 2, background: "var(--code-bg)" }} />
        {b0 != null && b1 != null && (
          <div style={{ position: "absolute", top: 6, left: `${b0}%`, width: `${Math.max(1, b1 - b0)}%`, height: 6, borderRadius: 3, background: "var(--accent-soft)", border: "1px solid var(--accent)" }} />
        )}
        <div style={{
          position: "absolute", top: 1, left: `calc(${pos}% - 5px)`, width: 10, height: 16,
          borderRadius: 3, background: "var(--ink)", boxShadow: "0 0 0 2px var(--surface)",
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }} className="s mono">
        <span>{loLabel ?? f(lo)}</span><span>{hiLabel ?? f(hi)}</span>
      </div>
    </div>
  );
}

/** Delta-colored value: ▲ +2.3% / ▼ −1.1% */
export function Delta({ v, digits = 2, suffix = "%" }: { v: number | null | undefined; digits?: number; suffix?: string }) {
  if (v == null) return <span className="s">—</span>;
  const up = v >= 0;
  return (
    <span className="mono" style={{ color: up ? "var(--green)" : "var(--red)", fontWeight: 650 }}>
      {up ? "▲" : "▼"} {up ? "+" : ""}{(v * 100).toFixed(digits)}{suffix}
    </span>
  );
}

/** Heat cell background for tables: sign+intensity coded. */
export function heat(v: number | null | undefined, good: "up" | "down" = "up"): React.CSSProperties {
  if (v == null) return {};
  const s = good === "up" ? v : -v;
  const alpha = Math.min(0.34, Math.abs(s) * 1.4 + 0.05);
  return { background: s >= 0 ? `rgba(34,197,94,${alpha})` : `rgba(239,68,68,${alpha})` };
}
