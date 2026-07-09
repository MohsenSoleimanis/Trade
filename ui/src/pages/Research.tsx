import { useEffect, useMemo, useState } from "react";
import { Company, fmtMoney, get } from "../api";
import { Spark } from "../components/Spark";

type SortKey = "symbol" | "name" | "price" | "day_change" | "ret_1y" | "market_cap";

export function Research() {
  const [rows, setRows] = useState<Company[] | null>(null);
  const [filter, setFilter] = useState<"ALL" | "US" | "BE">("ALL");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "market_cap", dir: -1 });

  useEffect(() => { get<Company[]>("/api/companies").then(setRows).catch(() => {}); }, []);

  const shown = useMemo(() => {
    if (!rows) return [];
    const f = rows.filter((r) => filter === "ALL" || r.country === filter);
    return f.sort((a, b) => {
      const av = a[sort.key], bv = b[sort.key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return (av < bv ? -1 : av > bv ? 1 : 0) * sort.dir;
    });
  }, [rows, filter, sort]);

  if (!rows) return <div className="loading">loading universe…</div>;

  const TH = ({ k, label, num }: { k: SortKey; label: string; num?: boolean }) => (
    <th className={num ? "num" : ""} onClick={() =>
      setSort((s) => ({ key: k, dir: s.key === k ? (s.dir === 1 ? -1 : 1) : -1 }))}>
      {label}{sort.key === k ? (sort.dir === -1 ? " ▾" : " ▴") : ""}
    </th>
  );

  return (
    <>
      <div className="pagehead"><h1>Research</h1>
        <span className="s">{shown.length} names · click a column to sort, a row to open</span>
      </div>

      <div className="chips" style={{ marginTop: 8 }}>
        {(["ALL", "US", "BE"] as const).map((f) => (
          <button key={f} className={`chip ${filter === f ? "on" : ""}`} onClick={() => setFilter(f)}>
            {f === "ALL" ? "All" : f === "US" ? "United States" : "Belgium"}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <TH k="symbol" label="Symbol" />
              <TH k="name" label="Company" />
              <th className="static">30d</th>
              <TH k="price" label="Price" num />
              <TH k="day_change" label="Day" num />
              <TH k="ret_1y" label="1Y" num />
              <TH k="market_cap" label="Mkt cap" num />
              <th className="static">Tier</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.symbol} className="click" onClick={() => (window.location.hash = `#/company/${r.symbol}`)}>
                <td className="mono">{r.symbol}</td>
                <td>{r.name}</td>
                <td><Spark data={r.spark} /></td>
                <td className="num">{r.price == null ? "—" : `${r.currency === "USD" ? "$" : "€"}${r.price.toFixed(2)}`}</td>
                <td className={`num ${(r.day_change ?? 0) >= 0 ? "up" : "down"}`}>
                  {r.day_change == null ? "—" : `${r.day_change >= 0 ? "+" : ""}${(r.day_change * 100).toFixed(2)}%`}
                </td>
                <td className={`num ${(r.ret_1y ?? 0) >= 0 ? "up" : "down"}`}>
                  {r.ret_1y == null ? "—" : `${r.ret_1y >= 0 ? "+" : ""}${(r.ret_1y * 100).toFixed(0)}%`}
                </td>
                <td className="num">{fmtMoney(r.market_cap, r.currency)}</td>
                <td><span className="badge tier">{r.tier}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
