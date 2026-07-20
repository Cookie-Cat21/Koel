"""NFA guardrails for scenario AI outputs.

Rejects buy/sell (and adjacent advice) language before any scenario text is
shown to users. No LLM calls live here — validators only.
"""

from __future__ import annotations

import re

from koel.domain import disclaimer

__all__ = [
    "GuardrailViolation",
    "assert_safe_scenario_output",
    "contains_buy_sell_language",
    "nfa_suffix",
]

# Fail-closed on investment-action / advice phrasing. Scenario outputs must stay
# descriptive (simulated reactions from public info), never actionable.
_BUY_SELL_RE = re.compile(
    r"\b(?:"
    r"buys?|buying|bought|"
    r"sells?|selling|sold|"
    r"strong\s+(?:buy|sell)|"
    r"recommend(?:s|ed|ing|ation|ations)?|"
    r"price\s*targets?|"
    r"overweight|underweight|"
    r"accumulat(?:e|es|ed|ing)|"
    r"take\s+profits?|"
    r"(?:go|going|went)\s+(?:long|short)\b|"
    r"short\s+(?:the\s+)?(?:stocks?|shares?|positions?|names?)|"
    r"long\s+(?:the\s+)?(?:stocks?|shares?|positions?|names?)|"
    r"exit\s+(?:the\s+)?(?:stocks?|shares?|positions?)|"
    r"hold(?:s|ing)?\s+(?:the\s+)?(?:stocks?|shares?|positions?|securit(?:y|ies))"
    r")\b",
    re.IGNORECASE,
)


class GuardrailViolation(ValueError):
    """Raised when scenario output fails NFA / buy-sell checks."""


def nfa_suffix() -> str:
    """Same NFA framing as bot/briefs (domain ``disclaimer``)."""
    return disclaimer()


def contains_buy_sell_language(text: object) -> bool:
    """True when ``text`` contains buy/sell or adjacent advice phrasing."""
    # Fail closed — non-strings must not coerce via str() into false hits.
    if not isinstance(text, str) or not text.strip():
        return False
    return _BUY_SELL_RE.search(text) is not None


def assert_safe_scenario_output(text: object) -> str:
    """Return stripped text if safe; raise ``GuardrailViolation`` otherwise.

    Empty/whitespace-only output is rejected. Buy/sell advice language is
    rejected. Does not call an LLM and does not mutate beyond strip.
    """
    # Fail closed — non-strings used to throw on .replace mid scenario gate.
    if not isinstance(text, str):
        raise GuardrailViolation("scenario output is empty")
    cleaned = text.replace("\x00", "").strip()
    if not cleaned:
        raise GuardrailViolation("scenario output is empty")
    match = _BUY_SELL_RE.search(cleaned)
    if match is not None:
        raise GuardrailViolation(
            f"scenario output contains buy/sell language: {match.group(0)!r}"
        )
    return cleaned
