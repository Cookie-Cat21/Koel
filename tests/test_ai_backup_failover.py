"""AI backup key chain + FailoverBriefProvider (Track A)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from koel.briefs import BriefSettings, briefs_enabled
from koel.briefs.provider import (
    BriefsDisabledError,
    FailoverBriefProvider,
    _is_transient_provider_error,
    make_brief_provider,
)


def test_brief_settings_parses_backup_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BRIEFS_ENABLED", "1")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_API_KEY", "primary-key")
    monkeypatch.setenv("AI_BACKUP_PROVIDERS", "groq, openrouter")
    monkeypatch.setenv("AI_BACKUP_API_KEYS", "gsk_backup, or_backup")
    monkeypatch.delenv("AI_BACKUP_MODELS", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)

    cfg = BriefSettings.from_env()
    assert cfg.backup_providers == ("groq", "openrouter")
    assert cfg.backup_api_keys == ("gsk_backup", "or_backup")
    slots = cfg.provider_slots()
    assert len(slots) == 3
    assert slots[0].provider == "gemini" and slots[0].api_key == "primary-key"
    assert slots[1].provider == "groq" and slots[1].model == "llama-3.3-70b-versatile"
    assert slots[2].provider == "openrouter" and slots[2].model == "openai/gpt-4o-mini"
    assert slots[1].backup_providers == ()


def test_briefs_enabled_with_backup_key_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BRIEFS_ENABLED", "1")
    monkeypatch.setenv("AI_API_KEY", "")
    monkeypatch.setenv("AI_BACKUP_PROVIDERS", "groq")
    monkeypatch.setenv("AI_BACKUP_API_KEYS", "gsk_only")
    cfg = BriefSettings.from_env()
    assert briefs_enabled(cfg) is True
    assert len(cfg.provider_slots()) == 1


def test_briefs_disabled_without_any_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BRIEFS_ENABLED", "1")
    monkeypatch.setenv("AI_API_KEY", "")
    monkeypatch.delenv("AI_BACKUP_API_KEYS", raising=False)
    monkeypatch.delenv("AI_BACKUP_PROVIDERS", raising=False)
    assert briefs_enabled(BriefSettings.from_env()) is False


def test_provider_slots_skip_empty_backup_keys() -> None:
    cfg = BriefSettings(
        enabled=True,
        api_key="p",
        provider="gemini",
        backup_providers=("groq", "openrouter"),
        backup_api_keys=("gsk_ok",),  # second missing → stop
        backup_models=("llama-3.1-8b-instant",),
    )
    slots = cfg.provider_slots()
    assert len(slots) == 2
    assert slots[1].model == "llama-3.1-8b-instant"


def test_transient_error_classifier() -> None:
    assert _is_transient_provider_error(RuntimeError("Gemini HTTP 429: rate"))
    assert _is_transient_provider_error(RuntimeError("Groq request timed out: x"))
    assert _is_transient_provider_error(RuntimeError("OpenRouter transport error: x"))
    assert _is_transient_provider_error(RuntimeError("Gemini HTTP 503: unavailable"))
    assert not _is_transient_provider_error(RuntimeError("Gemini HTTP 400: bad"))
    assert not _is_transient_provider_error(ValueError("summarize requires non-empty text"))
    assert not _is_transient_provider_error(BriefsDisabledError("off"))


@pytest.mark.asyncio
async def test_failover_uses_backup_on_429() -> None:
    primary = AsyncMock()
    primary.summarize = AsyncMock(side_effect=RuntimeError("Gemini HTTP 429: quota"))
    backup = AsyncMock()
    backup.summarize = AsyncMock(return_value="ok brief from backup")
    backup.aclose = AsyncMock()
    primary.aclose = AsyncMock()

    chain = FailoverBriefProvider([primary, backup], labels=["gemini", "groq"])
    out = await chain.summarize("<<<FILING>>>\nhello\n<<<END_FILING>>>")
    assert out == "ok brief from backup"
    primary.summarize.assert_awaited_once()
    backup.summarize.assert_awaited_once()
    await chain.aclose()
    primary.aclose.assert_awaited()
    backup.aclose.assert_awaited()


@pytest.mark.asyncio
async def test_failover_does_not_rotate_on_permanent_error() -> None:
    primary = AsyncMock()
    primary.summarize = AsyncMock(side_effect=RuntimeError("Gemini HTTP 400: bad request"))
    backup = AsyncMock()
    backup.summarize = AsyncMock(return_value="should not run")

    chain = FailoverBriefProvider([primary, backup], labels=["gemini", "groq"])
    with pytest.raises(RuntimeError, match="HTTP 400"):
        await chain.summarize("<<<FILING>>>\nhello\n<<<END_FILING>>>")
    backup.summarize.assert_not_awaited()


@pytest.mark.asyncio
async def test_failover_raises_value_error_without_rotating() -> None:
    primary = AsyncMock()
    primary.summarize = AsyncMock(side_effect=ValueError("summarize requires non-empty text"))
    backup = AsyncMock()
    backup.summarize = AsyncMock(return_value="nope")

    chain = FailoverBriefProvider([primary, backup])
    with pytest.raises(ValueError, match="non-empty"):
        await chain.summarize("")
    backup.summarize.assert_not_awaited()


def test_make_brief_provider_wraps_failover_chain() -> None:
    cfg = BriefSettings(
        enabled=True,
        api_key="primary",
        provider="gemini",
        model="gemini-2.0-flash",
        backup_providers=("groq",),
        backup_api_keys=("gsk_x",),
        backup_models=("llama-3.3-70b-versatile",),
    )
    prov = make_brief_provider(cfg)
    assert isinstance(prov, FailoverBriefProvider)
    assert len(prov._providers) == 2  # noqa: SLF001 — pin chain length


def test_make_brief_provider_single_slot_no_wrapper() -> None:
    cfg = BriefSettings(enabled=True, api_key="k", provider="gemini")
    prov = make_brief_provider(cfg)
    assert not isinstance(prov, FailoverBriefProvider)


@pytest.mark.asyncio
async def test_failover_all_transient_exhausted() -> None:
    a = AsyncMock()
    a.summarize = AsyncMock(side_effect=RuntimeError("Gemini HTTP 429: a"))
    b = AsyncMock()
    b.summarize = AsyncMock(side_effect=RuntimeError("Groq HTTP 503: b"))
    chain = FailoverBriefProvider([a, b], labels=["gemini", "groq"])
    with pytest.raises(RuntimeError, match="HTTP 503"):
        await chain.summarize("<<<FILING>>>\nx\n<<<END_FILING>>>")
