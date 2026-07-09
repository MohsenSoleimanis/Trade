import { useRef, useState } from "react";

// Dependency-free SVG price chart, in the visual language of the lessons:
// recessive grid, thin line, endpoint dot, hover crosshair with tooltip.

interface Point { date: string; value: number }

export function PriceChart({ data, currency }: { data: Point[]; currency: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  if (!data.length) return <div className="loading">no price history</div>;

  const W = 720, H = 260, padL = 54, padR = 20, padT = 14, padB = 26;
  const vals = data.map((d) => d.value);
  const lo = Math.min(...vals) * 0.97, hi = Math.max(...vals) * 1.03;
  const xs = (i: number) => padL + ((W - padL - padR) * i) / (data.length - 1);
  const ys = (v: number) => padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo));
  const path = data.map((d, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)} ${ys(d.value).toFixed(1)}`).join(" ");

  const gridVals = [0.25, 0.5, 0.75].map((f) => lo + f * (hi - lo));
  const sign = currency === "USD" ? "$" : "€";
  const last = data[data.length - 1];
  const first = data[0];
  const ret = last.value / first.value - 1;

  function onMove(e: React.MouseEvent) {
    const rect = svgRef.current!.getBoundingClientRect();
    const frac = ((e.clientX - rect.left) / rect.width * W - padL) / (W - padL - padR);
    const i = Math.round(frac * (data.length - 1));
    setHover(i >= 0 && i < data.length ? i : null);
  }

  return (
    <div style={{ position: "relative" }}>
      <svg
        ref={svgRef} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block" }}
        onMouseMove={onMove} onMouseLeave={() => setHover(null)}
        role="img" aria-label="price history chart"
      >
        {gridVals.map((v, k) => (
          <g key={k}>
            <line x1={padL} x2={W - padR} y1={ys(v)} y2={ys(v)} stroke="var(--grid)" strokeWidth={1} />
            <text x={padL - 8} y={ys(v) + 4} fontSize={10.5} fill="var(--muted)"
              textAnchor="end" fontFamily="Consolas, monospace">{sign}{v.toFixed(v > 500 ? 0 : 1)}</text>
          </g>
        ))}
        <text x={padL} y={H - 8} fontSize={10.5} fill="var(--muted)" fontFamily="Consolas, monospace">{first.date}</text>
        <text x={W - padR} y={H - 8} fontSize={10.5} fill="var(--muted)" textAnchor="end" fontFamily="Consolas, monospace">{last.date}</text>

        <path d={path} fill="none" stroke="var(--blue)" strokeWidth={2} />
        <circle cx={xs(data.length - 1)} cy={ys(last.value)} r={4}
          fill="var(--blue)" stroke="var(--surface)" strokeWidth={2} />

        {hover != null && (
          <g>
            <line x1={xs(hover)} x2={xs(hover)} y1={padT} y2={H - padB}
              stroke="var(--muted)" strokeWidth={1} strokeDasharray="3 3" />
            <circle cx={xs(hover)} cy={ys(data[hover].value)} r={4}
              fill="var(--blue)" stroke="var(--surface)" strokeWidth={2} />
          </g>
        )}
      </svg>
      {hover != null && (
        <div className="mono" style={{
          position: "absolute", top: 6,
          left: `${(xs(hover) / W) * 100}%`, transform: hover > data.length / 2 ? "translateX(-105%)" : "translateX(8px)",
          background: "var(--ink)", color: "var(--bg)", borderRadius: 5,
          padding: "4px 9px", fontSize: 12, pointerEvents: "none", whiteSpace: "nowrap",
        }}>
          {data[hover].date} · {sign}{data[hover].value.toFixed(2)}
        </div>
      )}
      <div className="s" style={{ marginTop: 6 }}>
        5 years, adjusted for dividends · total return{" "}
        <span className={`mono ${ret >= 0 ? "up" : "down"}`}>{(ret * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}
