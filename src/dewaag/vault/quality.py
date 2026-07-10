"""Data-quality gates — the vault's immune system.

Curriculum, Lesson (monitoring): a system silently fed garbage will happily
trade garbage. So quality checks exist from Phase 1, and they are GATES,
not suggestions: a CRITICAL finding means downstream consumers (screens,
backtests, tickets) must refuse the affected symbol until a human looks.

Levels:  WARN  = investigate when convenient, data still usable.
         CRITICAL = the symbol is quarantined for anything that matters.
"""

from __future__ import annotations

import pandas as pd

FRESH_DAYS = 10        # a listed stock with no price for >10 calendar days
                       # is stale (holidays included) -> WARN; >30 CRITICAL
GAP_WARN_DAYS = 10     # silent holes in history
GAP_CRIT_DAYS = 30
SPIKE_WARN = 0.40      # |daily move| >40%: real for small caps sometimes,
SPIKE_CRIT = 0.80      # >80% is almost always a data error (or a story
                       # you need to know about either way)
MIN_ROWS = 250         # less than ~1 trading year of history -> WARN


def check_frame(symbol: str, df: pd.DataFrame, today=None, tier: str | None = None) -> list[dict]:
    """Pure function over a price frame -> findings. Pure so tests can feed
    synthetic frames — the immune system itself must be testable.

    tier="macro": the spike check is OFF. VIX doubling in a day is not a
    data error — it is exactly the information the series exists to carry."""
    findings: list[dict] = []
    add = lambda level, check, detail: findings.append(  # noqa: E731
        {"symbol": symbol, "level": level, "check": check, "detail": detail}
    )

    if df.empty:
        add("CRITICAL", "empty", "no rows at all")
        return findings

    dates = pd.to_datetime(df["date"]).sort_values()
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.today()

    if len(df) < MIN_ROWS:
        add("WARN", "min_rows", f"only {len(df)} rows")

    age = (today - dates.iloc[-1]).days
    if age > 30:
        add("CRITICAL", "stale", f"last price {age} days old")
    elif age > FRESH_DAYS:
        add("WARN", "stale", f"last price {age} days old")

    diffs = dates.diff().dt.days.dropna()
    worst_gap = int(diffs.max()) if len(diffs) else 0
    if worst_gap > GAP_CRIT_DAYS:
        add("CRITICAL", "gap", f"{worst_gap}-day hole in history")
    elif worst_gap > GAP_WARN_DAYS:
        add("WARN", "gap", f"{worst_gap}-day hole in history")

    if (df["adj_close"] <= 0).any() or (df["close"] <= 0).any():
        add("CRITICAL", "nonpositive", "zero/negative prices present")

    if tier != "macro":
        rets = df.sort_values("date")["adj_close"].pct_change().abs().dropna()
        if len(rets):
            worst = float(rets.max())
            if worst > SPIKE_CRIT:
                add("CRITICAL", "spike", f"|daily move| {worst:.0%}")
            elif worst > SPIKE_WARN:
                add("WARN", "spike", f"|daily move| {worst:.0%}")

    return findings


def run_checks() -> pd.DataFrame:
    """Check every symbol in the vault. Returns the findings table
    (empty frame = a perfectly healthy vault)."""
    from dewaag.vault import store

    universe = store.load_universe()
    all_findings: list[dict] = []
    for _, row in universe.iterrows():
        symbol = row["symbol"]
        path = store.price_path(symbol)
        if not path.exists():
            all_findings.append(
                {"symbol": symbol, "level": "WARN", "check": "missing",
                 "detail": "in universe but no price file"}
            )
            continue
        all_findings.extend(check_frame(symbol, pd.read_parquet(path), tier=str(row["tier"])))
    cols = ["symbol", "level", "check", "detail"]
    return pd.DataFrame(all_findings, columns=cols)


def gate(findings: pd.DataFrame) -> bool:
    """True = vault passes (no CRITICAL findings)."""
    return findings.empty or not (findings["level"] == "CRITICAL").any()
