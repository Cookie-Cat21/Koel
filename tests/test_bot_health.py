"""Bot-mode health refresh must reflect DB failures (OPS-HEALTH-001)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.__main__ import _refresh_bot_health, _refresh_both_health
from chime.health import HealthState
from chime.poller import Poller


@pytest.mark.asyncio
async def test_refresh_bot_health_db_down_sets_degraded() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=False)
    health = HealthState()
    health.ok = True

    await _refresh_bot_health(storage, health)

    assert health.ok is False
    assert health.details.get("db_ok") is False
    assert health.details.get("last_error") == "db_unhealthy"


@pytest.mark.asyncio
async def test_refresh_bot_health_db_ok() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    health = HealthState()
    health.ok = False

    await _refresh_bot_health(storage, health)

    assert health.ok is True
    assert health.details.get("db_ok") is True


@pytest.mark.asyncio
async def test_refresh_both_health_requires_tick_ok() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    health = HealthState()
    poller = AsyncMock(spec=Poller)
    poller.last_tick_ok = False
    poller.last_tick_at = None
    poller.price_poll_ok = True
    poller.disclosure_poll_ok = True
    poller.lock_held_skip = False
    poller.watched_missing = []
    poller.last_error = "price_fetch_failed"
    poller.cse = MagicMock()
    poller.cse.circuit_metrics = MagicMock(return_value={})

    await _refresh_both_health(storage, health, poller)

    assert health.ok is False
    assert health.details.get("last_tick_ok") is False
    assert health.details.get("last_error") == "price_fetch_failed"
    assert health.details.get("watched_missing") == []
