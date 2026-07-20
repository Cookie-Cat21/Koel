"""Wave8: AI_BRIEF_SLEEP_SECONDS inter-brief drain pacing."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.briefs import BriefSettings
from koel.briefs.worker import claim_pending_briefs


def _enabled_settings(**kwargs: Any) -> BriefSettings:
    base = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        sleep_seconds=0,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


def test_brief_settings_sleep_default_and_soft_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_BRIEF_SLEEP_SECONDS", raising=False)
    assert BriefSettings.from_env().sleep_seconds == 0.5

    monkeypatch.setenv("AI_BRIEF_SLEEP_SECONDS", "nope")
    assert BriefSettings.from_env().sleep_seconds == 0.5

    monkeypatch.setenv("AI_BRIEF_SLEEP_SECONDS", "1.25")
    assert BriefSettings.from_env().sleep_seconds == 1.25

    monkeypatch.setenv("AI_BRIEF_SLEEP_SECONDS", "-1")
    assert BriefSettings.from_env().sleep_seconds == 0.0

    monkeypatch.setenv("AI_BRIEF_SLEEP_SECONDS", "0")
    assert BriefSettings.from_env().sleep_seconds == 0.0


@pytest.mark.asyncio
async def test_claim_pending_briefs_sleeps_between_llm_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inter-brief pacing: sleep between LLM calls, not before the first."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.briefs.worker.asyncio.sleep", sleep_mock)

    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {"disclosure_id": 1, "symbol": "AAA.N0000", "title": "A"},
            {"disclosure_id": 2, "symbol": "BBB.N0000", "title": "B"},
            {"disclosure_id": 3, "symbol": "CCC.N0000", "title": "C"},
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="ok")

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(sleep_seconds=0.5),
        provider=provider,
    )
    assert n == 3
    assert provider.summarize.await_count == 3
    assert sleep_mock.await_count == 2
    assert all(call.args == (0.5,) for call in sleep_mock.await_args_list)


@pytest.mark.asyncio
async def test_claim_pending_briefs_no_sleep_when_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.briefs.worker.asyncio.sleep", sleep_mock)

    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {"disclosure_id": 1, "symbol": "AAA.N0000", "title": "A"},
            {"disclosure_id": 2, "symbol": "BBB.N0000", "title": "B"},
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="ok")

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(sleep_seconds=0),
        provider=provider,
    )
    assert n == 2
    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_pending_briefs_no_sleep_for_single_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.briefs.worker.asyncio.sleep", sleep_mock)

    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[{"disclosure_id": 1, "symbol": "AAA.N0000", "title": "A"}]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="ok")

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(sleep_seconds=0.5),
        provider=provider,
    )
    assert n == 1
    sleep_mock.assert_not_awaited()
