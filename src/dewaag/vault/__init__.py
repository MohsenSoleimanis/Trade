"""The Data Vault — Layers 0 and 1 of De Waag.

Layer 0: the universe — WHAT exists and is tradable (symbols, exchanges,
         currencies, liquidity tiers).
Layer 1: the history — prices with an `ingested_at` timestamp on every row,
         so the system always knows not just what a value is, but WHEN it
         became knowable (the point-in-time discipline from the curriculum).

HONESTY NOTE (survivorship bias): the free universe below is a list of
companies that exist TODAY. Companies that died or were delisted are
missing — which makes any long backtest on this data look better than
reality. This is a known, accepted limitation of Phase 1; the Backtest
Lab (Phase 4) will display a survivorship warning banner until the vault
is upgraded to a survivorship-free data source (see docs/SETUP-APIS.md).
"""
