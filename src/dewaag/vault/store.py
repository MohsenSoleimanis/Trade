"""Storage: Parquet files on disk, DuckDB for querying.

Why files + DuckDB instead of a database server? Debuggability = trust.
Every table is a file you can open and inspect; DuckDB queries 20 years
of prices in milliseconds without any service to administer. The vault
can never be 'down' — it's just your disk.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
PRICES_DIR = DATA_DIR / "prices"
UNIVERSE_PATH = DATA_DIR / "universe.parquet"


def ensure_dirs() -> None:
    PRICES_DIR.mkdir(parents=True, exist_ok=True)


def save_universe(df: pd.DataFrame) -> Path:
    ensure_dirs()
    df.to_parquet(UNIVERSE_PATH, index=False)
    return UNIVERSE_PATH


def load_universe() -> pd.DataFrame:
    if not UNIVERSE_PATH.exists():
        raise FileNotFoundError(
            "No universe yet — run:  python -m dewaag.vault universe"
        )
    return pd.read_parquet(UNIVERSE_PATH)


def price_path(symbol: str) -> Path:
    return PRICES_DIR / f"{symbol}.parquet"


def load_prices(symbol: str) -> pd.DataFrame:
    return pd.read_parquet(price_path(symbol))


def query(sql: str) -> pd.DataFrame:
    """Run SQL over the whole vault. `prices` and `universe` are views."""
    con = duckdb.connect()
    if any(PRICES_DIR.glob("*.parquet")):
        con.execute(
            f"CREATE VIEW prices AS SELECT * FROM read_parquet('{PRICES_DIR.as_posix()}/*.parquet')"
        )
    if UNIVERSE_PATH.exists():
        con.execute(
            f"CREATE VIEW universe AS SELECT * FROM read_parquet('{UNIVERSE_PATH.as_posix()}')"
        )
    return con.execute(sql).df()


def vault_status() -> dict:
    """One dict the API and CLI both use — a vault you can't see is a vault
    you won't notice breaking (Lesson: monitoring starts at Phase 1, not 7)."""
    if not UNIVERSE_PATH.exists():
        return {"universe": 0, "symbols_with_prices": 0, "rows": 0}
    n_universe = len(load_universe())
    files = list(PRICES_DIR.glob("*.parquet"))
    if not files:
        return {"universe": n_universe, "symbols_with_prices": 0, "rows": 0}
    agg = query(
        "SELECT COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows, "
        "MIN(date) AS first_date, MAX(date) AS last_date, "
        "MAX(ingested_at) AS last_ingest FROM prices"
    ).iloc[0]
    return {
        "universe": n_universe,
        "symbols_with_prices": int(agg["syms"]),
        "rows": int(agg["rows"]),
        "first_date": str(agg["first_date"])[:10],
        "last_date": str(agg["last_date"])[:10],
        "last_ingest": str(agg["last_ingest"]),
    }
