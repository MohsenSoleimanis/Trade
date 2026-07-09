import { useRef, useState } from "react";

// Multi-series equity-curve chart: recessive grid, direct end labels,
// hover crosshair with all series' values. Log-ish reading via base-100.

export interface Series { name: string; color: string; values: (number | null)[] }

export function LineChart({ dates, series, base = 100 }: { dates: string[]; series: Series[]; base?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const W = 760, H = 320, padL = 56, padR = 86, padT = 14, padB = 26;
  const all = series.flatMap((s) => s.values.filter((v): v is number => v != null)).map((v) => v * base);
  if (!all.length) return <div className="loading">no data</div>;
  const lo = Math.min(...all) * 0.95, hi = Math.max(...all) * 1.05;
  const xs = (i: number) => padL + ((W - padL - padR) * i) / (dates.length - 1);
  const ys = (v: number) => padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo));

  function path(vals: (number | null)[]) {
    let d = "", pen = false;
    vals.forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${xs(i).toFixed(1)} ${ys(v * base).toFixed(1)}`;
      pen = true;
    });
    return d;
  }

  function onMove(e: React.MouseEvent) {
    const rect = svgRef.current!.getBoundingClientRect();
    const frac = ((e.clientX - rect.left) / rect.width * W - padL) / (W - padL - padR);
    const i = Math.round(frac * (dates.length - 1));
    setHover(i >= 0 && i < dates.length ? i : null);
  }

  const gridVals = [0.25, 0.5, 0.75].map((f) => lo + f * (hi - lo));

  return (
    <div style={{ position: "relative" }}>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block" }}
        onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label="equity curves">
        {gridVals.map((v, k) => (
          <g key={k}>
            <line x1={padL} x2={W - padR} y1={ys(v)} y2={ys(v)} stroke="var(--grid)" strokeWidth={1} />
            <text x={padL - 8} y={ys(v) + 4} fontSize={10.5} fill="var(--muted)" textAnchor="end"
              fontFamily="Consolas, monospace">{v.toFixed(0)}</text>
          </g>
        ))}
        <line x1={padL} x2={W - padR} y1={ys(base)} y2={ys(base)} stroke="var(--muted)" strokeWidth={1} strokeDasharray="4 4" />
        <text x={dates.length ? xs(0) : padL} y={H - 8} fontSize={10.5} fill="var(--muted)" fontFamily="Consolas, monospace">{dates[0]}</text>
        <text x={W - padR} y={H - 8} fontSize={10.5} fill="var(--muted)" textAnchor="end" fontFamily="Consolas, monospace">{dates[dates.length - 1]}</text>

        {series.map((s) => <path key={s.name} d={path(s.values)} fill="none" stroke={s.color} strokeWidth={1.8} />)}

        {series.map((s) => {
          const lastIdx = s.values.length - 1;
          const lastVal = s.values[lastIdx];
          if (lastVal == null) return null;
          return (
            <text key={s.name} x={xs(lastIdx) + 6} y={ys(lastVal * base) + 4} fontSize={11}
              fontWeight={600} fill={s.color} fontFamily="Consolas, monospace">{s.name}</text>
          );
        })}

        {hover != null && (
          <line x1={xs(hover)} x2={xs(hover)} y1={padT} y2={H - padB}
            stroke="var(--muted)" strokeWidth={1} strokeDasharray="3 3" />
        )}
      </svg>
      {hover != null && (
        <div className="mono" style={{
          position: "absolute", top: 8,
          left: `${(xs(hover) / W) * 100}%`, transform: hover > dates.length / 2 ? "translateX(-105%)" : "translateX(10px)",
          background: "var(--ink)", color: "var(--bg)", borderRadius: 5,
          padding: "5px 10px", fontSize: 11.5, pointerEvents: "none", whiteSpace: "nowrap", lineHeight: 1.6,
        }}>
          {dates[hover]}<br />
          {series.map((s) => {
            const v = s.values[hover];
            return <span key={s.name}>{s.name}: {v == null ? "—" : (v * base).toFixed(1)}<br /></span>;
          })}
        </div>
      )}
    </div>
  );
}
