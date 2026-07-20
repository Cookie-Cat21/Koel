"""Optional scenario AI stub (Phase 3 fence).

Disabled by default via ``AI_SCENARIOS_ENABLED=0``. No LLM provider wiring yet —
on-demand scenario runs land behind this flag later. Guardrails reject buy/sell
language in any future model output before it reaches users.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from koel.scenarios.guardrails import (
    GuardrailViolation,
    assert_safe_scenario_output,
    contains_buy_sell_language,
    nfa_suffix,
)

__all__ = [
    "GuardrailViolation",
    "ScenarioSettings",
    "assert_safe_scenario_output",
    "contains_buy_sell_language",
    "nfa_suffix",
    "scenarios_enabled",
]


@dataclass(frozen=True, slots=True)
class ScenarioSettings:
    """Env knobs (see root ``.env.example``):

    - ``AI_SCENARIOS_ENABLED`` — ``1`` to opt in (default ``0``)
    """

    enabled: bool = False

    @classmethod
    def from_env(cls) -> ScenarioSettings:
        raw = os.getenv("AI_SCENARIOS_ENABLED", "0")
        # Fail closed — non-string getenv mocks used to throw on .strip mid scenario gate.
        return cls(enabled=isinstance(raw, str) and raw.strip() == "1")


def scenarios_enabled(settings: ScenarioSettings | None = None) -> bool:
    """True only when explicitly opted in. No API key / LLM check yet."""
    cfg = settings or ScenarioSettings.from_env()
    return cfg.enabled
