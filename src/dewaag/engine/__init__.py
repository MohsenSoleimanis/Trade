"""The deterministic engine — ratios, valuation, and (later) sizing,
signals, backtests. Pure computation over the vault: no network, no
side effects, fully unit-testable. Agents and UIs consume it; nothing
in here ever guesses."""
