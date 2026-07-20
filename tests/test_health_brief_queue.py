"""Wave3: loopback health exposes fail-soft brief/pdf enrich queue hint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.__main__ import _refresh_bot_health, _refresh_both_health
from koel.health import HealthState, brief_queue_health_hint


def _healthy_poller() -> MagicMock:
    poller = MagicMock()
    poller.last_tick_ok = True
    poller.last_tick_at = None
    poller.price_poll_ok = True
    poller.disclosure_poll_ok = True
    poller.lock_held_skip = False
    poller.watched_missing = []
    poller.last_error = None
    poller.cse = MagicMock()
    poller.cse.circuit_metrics = MagicMock(return_value={})
    poller.pdf_enrich_health_snapshot = MagicMock(
        return_value={
            "in_flight_tasks": 1,
            "last_batch_size": 3,
            "batches_started": 2,
        }
    )
    return poller


@pytest.mark.asyncio
async def test_brief_queue_hint_includes_pdf_and_pending() -> None:
    storage = MagicMock()
    storage.count_pending_disclosure_briefs = AsyncMock(return_value=7)
    poller = _healthy_poller()

    hint = await brief_queue_health_hint(storage=storage, poller=poller)

    assert hint["pending_briefs"] == 7
    assert hint["pdf_enrich"]["in_flight_tasks"] == 1
    assert hint["pdf_enrich"]["last_batch_size"] == 3
    assert hint["pdf_enrich"]["batches_started"] == 2


@pytest.mark.asyncio
async def test_brief_queue_hint_omits_pending_on_sql_failure() -> None:
    storage = MagicMock()
    storage.count_pending_disclosure_briefs = AsyncMock(side_effect=RuntimeError("db down"))
    poller = _healthy_poller()

    hint = await brief_queue_health_hint(storage=storage, poller=poller)

    assert "pending_briefs" not in hint
    assert hint["pdf_enrich"]["in_flight_tasks"] == 1


@pytest.mark.asyncio
async def test_brief_queue_hint_survives_bad_pdf_snapshot() -> None:
    storage = MagicMock()
    storage.count_pending_disclosure_briefs = AsyncMock(return_value=0)
    poller = MagicMock()
    poller.pdf_enrich_health_snapshot = MagicMock(side_effect=RuntimeError("boom"))

    hint = await brief_queue_health_hint(storage=storage, poller=poller)

    assert hint == {"pending_briefs": 0}


@pytest.mark.asyncio
async def test_both_health_exposes_brief_queue_without_degrading() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    storage.count_pending_disclosure_briefs = AsyncMock(return_value=4)
    health = HealthState()

    await _refresh_both_health(storage, health, _healthy_poller())

    assert health.ok is True
    assert health.details["brief_queue"]["pending_briefs"] == 4
    assert health.details["brief_queue"]["pdf_enrich"]["in_flight_tasks"] == 1


@pytest.mark.asyncio
async def test_bot_health_exposes_pending_briefs_fail_soft() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    storage.count_pending_disclosure_briefs = AsyncMock(side_effect=OSError("timeout"))
    health = HealthState()

    await _refresh_bot_health(storage, health)

    assert health.ok is True
    assert "brief_queue" not in health.details
