"""Phase 3 scenario AI stub: disabled-by-default fence + NFA buy/sell guardrails."""

from __future__ import annotations

import pytest

from koel.scenarios import (
    GuardrailViolation,
    ScenarioSettings,
    assert_safe_scenario_output,
    contains_buy_sell_language,
    nfa_suffix,
    scenarios_enabled,
)


def test_scenarios_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_SCENARIOS_ENABLED", raising=False)
    assert ScenarioSettings.from_env().enabled is False
    assert scenarios_enabled() is False


def test_scenarios_enabled_only_when_flag_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_SCENARIOS_ENABLED", "0")
    assert scenarios_enabled() is False

    monkeypatch.setenv("AI_SCENARIOS_ENABLED", "1")
    assert ScenarioSettings.from_env().enabled is True
    assert scenarios_enabled() is True

    monkeypatch.setenv("AI_SCENARIOS_ENABLED", "true")
    assert scenarios_enabled() is False


def test_scenarios_enabled_respects_explicit_settings() -> None:
    assert scenarios_enabled(ScenarioSettings(enabled=False)) is False
    assert scenarios_enabled(ScenarioSettings(enabled=True)) is True


def test_nfa_suffix_matches_domain_disclaimer() -> None:
    from koel.domain import disclaimer

    assert nfa_suffix() == disclaimer()
    assert "Not financial advice" in nfa_suffix()


@pytest.mark.parametrize(
    "text",
    [
        "Investors may watch liquidity into the close.",
        "Simulated reaction: cautious tone on margin commentary.",
        "Filing notes a board meeting next Tuesday.",
    ],
)
def test_safe_scenario_output_passes(text: str) -> None:
    assert contains_buy_sell_language(text) is False
    assert assert_safe_scenario_output(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "You should buy JKH now.",
        "Strong sell on this name.",
        "Traders are selling the break.",
        "I would hold the stock here.",
        "We recommend accumulating on dips.",
        "Price target: 200.",
        "Fund is overweight banks.",
        "Accumulate on weakness.",
        "Go long the shares into the close.",
        "Short the stock on the gap.",
        "Exit the position before the close.",
        "Take profits into strength.",
    ],
)
def test_buy_sell_language_rejected(text: str) -> None:
    assert contains_buy_sell_language(text) is True
    with pytest.raises(GuardrailViolation, match="buy/sell"):
        assert_safe_scenario_output(text)


def test_empty_output_rejected() -> None:
    assert contains_buy_sell_language("") is False
    with pytest.raises(GuardrailViolation, match="empty"):
        assert_safe_scenario_output("   ")


def test_null_bytes_stripped_before_check() -> None:
    text = "Cautious tone on margins.\x00"
    assert assert_safe_scenario_output(text) == "Cautious tone on margins."
