"""Vault CLI:  python -m dewaag.vault <command>

    universe   build & save the Layer-0 universe table
    ingest     fetch/refresh daily prices for the whole universe (idempotent)
    check      run the data-quality gates, print findings
    status     one-line health summary of the vault
"""

from __future__ import annotations

import sys


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "universe":
        from dewaag.vault import store
        from dewaag.vault.universe import build_universe

        df = build_universe()
        path = store.save_universe(df)
        print(f"universe: {len(df)} symbols -> {path}")
        print(df["tier"].value_counts().to_string())
        return 0

    if cmd == "ingest":
        from dewaag.vault.ingest import ingest_universe

        print("ingesting universe (free data, ~20y history)...")
        result = ingest_universe()
        print(f"\nok: {result['ok']} symbols, +{result['new_rows']} rows")
        if result["failed"]:
            print("FAILED:")
            for sym, err in result["failed"]:
                print(f"  {sym}: {err}")
        return 1 if result["failed"] else 0

    if cmd == "fundamentals":
        from dewaag.vault.fundamentals import ingest_universe_fundamentals

        print("ingesting annual statements (free data, ~4y per company)...")
        result = ingest_universe_fundamentals()
        print(f"\nok: {result['ok']} symbols")
        if result["failed"]:
            print("FAILED:")
            for sym, err in result["failed"]:
                print(f"  {sym}: {err}")
        return 1 if result["failed"] else 0

    if cmd == "check":
        from dewaag.vault.quality import gate, run_checks

        findings = run_checks()
        if findings.empty:
            print("all checks passed — vault is healthy")
            return 0
        print(findings.to_string(index=False))
        ok = gate(findings)
        print(f"\ngate: {'PASS (warnings only)' if ok else 'FAIL — CRITICAL findings'}")
        return 0 if ok else 1

    if cmd == "status":
        from dewaag.vault.store import vault_status

        for k, v in vault_status().items():
            print(f"{k:>20}: {v}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
