// 22-day sparkline — the professional table's heartbeat column.
export function Spark({ data, w = 84, h = 24 }: { data: number[]; w?: number; h?: number }) {
  if (!data || data.length < 2) return <span className="s">—</span>;
  const lo = Math.min(...data), hi = Math.max(...data);
  const span = hi - lo || 1;
  const pts = data
    .map((v, i) => `${((i / (data.length - 1)) * (w - 2) + 1).toFixed(1)},${(h - 2 - ((v - lo) / span) * (h - 4)).toFixed(1)}`)
    .join(" ");
  const upward = data[data.length - 1] >= data[0];
  return (
    <svg width={w} height={h} aria-hidden="true">
      <polyline points={pts} fill="none" strokeWidth={1.4}
        stroke={upward ? "var(--green)" : "var(--red)"} />
    </svg>
  );
}
