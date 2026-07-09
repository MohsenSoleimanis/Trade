import { useEffect, useState } from "react";
import { Company, get } from "../api";

export function Research() {
  const [rows, setRows] = useState<Company[] | null>(null);
  const [filter, setFilter] = useState<"ALL" | "US" | "BE">("ALL");

  useEffect(() => { get<Company[]>("/api/companies").then(setRows).catch(() => {}); }, []);

  if (!rows) return <div className="loading">loading universe…</div>;

  const shown = rows
    .filter((r) => filter === "ALL" || r.country === filter)
    .sort((a, b) => a.country.localeCompare(b.country) || a.name.localeCompare(b.name));

  return (
    <>
      <div className="pagehead"><h1>Research</h1></div>
      <p className="pagesub">The universe — {rows.length} names across both markets. Click a company to open its workbench page.</p>

      <div className="chips">
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
              <th>Symbol</th><th>Company</th><th>Exchange</th><th>Tier</th><th className="num">Last price</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.symbol} className="click" onClick={() => (window.location.hash = `#/company/${r.symbol}`)}>
                <td className="mono">{r.symbol}</td>
                <td>{r.name}</td>
                <td className="s">{r.exchange}</td>
                <td><span className="badge tier">{r.tier}</span></td>
                <td className="num">
                  {r.price == null ? "—" : `${r.currency === "USD" ? "$" : "€"}${r.price.toFixed(2)}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
