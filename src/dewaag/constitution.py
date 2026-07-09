"""The Risk Constitution, as code.

Lesson 6 produced a signed document. This module makes it law:
every rule is a validated field, and the validations themselves encode
the curriculum — the loader *refuses* configurations that break them.

Why validation instead of trust? Because the constitution's whole job
is to bind excited-you to the rules calm-you wrote. A config file you
can quietly edit past its limits binds nobody.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

# repo_root/config/risk-constitution.yaml
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "risk-constitution.yaml"


class Constitution(BaseModel):
    owner: str
    signed_on: date | None = None

    # §1 — Lesson 6: the 1–2% rule. The ceiling (le=2.0) is not a default,
    # it's a refusal: a constitution claiming 3% risk per idea will not load.
    max_risk_per_idea_pct: float = Field(gt=0, le=2.0)

    # §2 — hard position cap. "Feeling sure is data about you, not the stock."
    max_position_pct: float = Field(gt=0, le=10.0)

    # §3 — drawdown limit in EUROS (behavior runs on euros, not percent).
    # 0 is allowed but means "undecided" → constitution stays unsigned.
    max_drawdown_eur: float = Field(ge=0)

    # §4 — never invest money with a deadline.
    emergency_fund_months: int = Field(ge=3)

    # §5 — see validator below. No Field ceiling: the message matters.
    leverage: int

    # §6 — the Trading Desk blocks tickets without a written thesis.
    require_thesis: bool = True

    # §7 — Lesson 7's anti-hopping vaccine.
    min_years_before_strategy_change: int = Field(ge=1)

    strategy_statement: str = ""

    @field_validator("leverage")
    @classmethod
    def leverage_is_zero(cls, v: int) -> int:
        if v != 0:
            raise ValueError(
                "Constitution §5: leverage must be 0. Leverage is the one door "
                "through which a careful portfolio can still die (Lesson 6 §5). "
                "There is deliberately no override."
            )
        return v

    @property
    def signed(self) -> bool:
        """Signed = dated AND the euro drawdown limit is actually decided.

        Until then the app runs in UNSIGNED mode: research is open,
        the Trading Desk stays locked.
        """
        return self.signed_on is not None and self.max_drawdown_eur > 0


def load_constitution(path: Path | str = DEFAULT_PATH) -> Constitution:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Constitution(**raw)
