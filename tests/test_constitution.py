"""The constitution's laws have unit tests — that's what 'machine-enforced' means.

If someone (including future-you) edits the rules past their limits,
these tests and the loader itself must refuse. Lesson 6: the software
is calm-you, enforcing rules on excited-you.
"""

import pytest
from pydantic import ValidationError

from dewaag.constitution import Constitution, load_constitution


def valid_kwargs(**overrides):
    base = dict(
        owner="Test",
        signed_on="2026-07-09",
        max_risk_per_idea_pct=1.0,
        max_position_pct=10.0,
        max_drawdown_eur=1500,
        emergency_fund_months=6,
        leverage=0,
        require_thesis=True,
        min_years_before_strategy_change=5,
    )
    base.update(overrides)
    return base


def test_repo_constitution_loads():
    c = load_constitution()
    assert c.leverage == 0


def test_leverage_must_be_zero():
    with pytest.raises(ValidationError, match="leverage must be 0"):
        Constitution(**valid_kwargs(leverage=2))


def test_risk_per_idea_ceiling_is_two_percent():
    # Lesson 6 §1: the 1–2% rule. 3% must be refused, not warned about.
    with pytest.raises(ValidationError):
        Constitution(**valid_kwargs(max_risk_per_idea_pct=3.0))


def test_position_cap_ceiling_is_ten_percent():
    with pytest.raises(ValidationError):
        Constitution(**valid_kwargs(max_position_pct=25.0))


def test_unsigned_until_drawdown_decided():
    # A dated signature without a euro drawdown number is not a signature:
    # the one number behavior actually runs on is still missing.
    c = Constitution(**valid_kwargs(max_drawdown_eur=0))
    assert c.signed is False


def test_signed_when_dated_and_drawdown_set():
    c = Constitution(**valid_kwargs())
    assert c.signed is True
