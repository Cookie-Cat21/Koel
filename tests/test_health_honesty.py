"""WS-077: Health honesty — poller last_tick_ok / lock_held_skip pins."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from chime.circuit import CircuitOpenError
from chime.config import Settings
from chime.poller import Poller


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


@pytest.mark.asyncio
async def test_circuit_open_with_watchlist_sets_last_tick_ok_false() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.unsent_alerts = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(side_effect=CircuitOpenError("open"))
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.last_tick_ok is False
    assert poller.lock_held_skip is False
    assert poller.last_error == "poll_degraded"


@pytest.mark.asyncio
async def test_lock_skip_sets_lock_held_skip() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=False)
    storage.advisory_unlock = AsyncMock()

    cse = AsyncMock()
    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.lock_held_skip is True
    assert poller.last_tick_ok is False
    assert poller.last_error == "poll_lock_held"
    assert poller.last_tick_at is not None
    storage.try_advisory_lock.assert_awaited_once()
    storage.advisory_unlock.assert_not_awaited()
    cse.fetch_trade_summary.assert_not_awaited()
