// Typed access to the De Waag API — one place, so the shape of the
// backend is documented in the frontend.

export interface Company {
  symbol: string; name: string; exchange: string; currency: string;
  country: string; tier: string; price: number | null;
  day_change: number | null; ret_1y: number | null;
  market_cap: number | null; spark: number[];
}

export interface Position {
  symbol: string; name: string; tier: string; currency: string;
  shares: number; last: number; value_eur: number; pnl_eur: number;
  pnl_pct: number; wrong_price: number | null; thesis: string; opened_at: string | null;
}

export interface Trade {
  at: string; symbol: string; side: string; shares: number; fill: number;
  currency: string; costs_eur: number; total_eur: number; thesis: string;
}

export interface Portfolio {
  currency: string; cash: number; invested: number; equity: number;
  pnl_since_start: number; positions: Position[]; open_risk_eur: number;
  drawdown_eur: number; drawdown_limit_eur: number;
  equity_history: { date: string; equity: number }[];
  trades: Trade[]; constitution_signed: boolean;
}

export interface YearRatios {
  period: string;
  revenue: number | null; net_income: number | null; equity: number | null;
  shares: number | null; rev_growth: number | null; net_margin: number | null;
  roe: number | null; debt_to_equity: number | null; cash_conversion: number | null;
}

export interface CompanyDetail {
  symbol: string;
  profile: { name: string; exchange: string; currency: string; country: string; tier: string };
  last_price: number; last_date: string; currency: string;
  day_change: number | null; high_52w: number; low_52w: number; range: string;
  engine: { scores: { q_score: number | null; v_score: number | null; m_score: number | null; composite: number | null }; coverage?: number; bullets: string[] };
  chart: { date: string; value: number }[];
  toolkit: { years: YearRatios[]; latest: YearRatios | null };
  valuation: {
    price: number | null; eps: number | null; pe: number | null;
    rate: number; implied_growth: number | null; market_cap: number | null;
  };
  quality: { level: string; check: string; detail: string }[];
  meta: { source: string; ingested_at: string; note: string };
}

export interface VaultStatus {
  universe: number; symbols_with_prices: number; rows: number;
  first_date?: string; last_date?: string; last_ingest?: string;
}

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

// ---------- formatting helpers (one voice everywhere) ----------
export const fmtPct = (x: number | null | undefined, digits = 1) =>
  x == null ? "—" : `${(x * 100).toFixed(digits)}%`;

export const fmtNum = (x: number | null | undefined, digits = 2) =>
  x == null ? "—" : x.toFixed(digits);

export function fmtMoney(x: number | null | undefined, currency = "") {
  if (x == null) return "—";
  const sign = currency === "USD" ? "$" : currency === "EUR" ? "€" : "";
  const abs = Math.abs(x);
  if (abs >= 1e12) return `${sign}${(x / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}${(x / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${(x / 1e6).toFixed(1)}M`;
  return `${sign}${x.toFixed(2)}`;
}
