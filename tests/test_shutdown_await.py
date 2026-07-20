"""E2-C02 / CORE-005: shutdown awaits in-flight scheduled tick (with timeout).

Wave4: also drains shielded PDF enrich / brief push background tasks so
``storage.close()`` does not race lock-holding fire-and-forget work.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.config import Settings
from koel.poller import SHUTDOWN_TICK_TIMEOUT_SECONDS, PendingPdfEnrich, Poller


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


def _poller() -> Poller:
    return Poller(_settings(), AsyncMock(), AsyncMock(), AsyncMock())


@pytest.mark.asyncio
async def test_shutdown_awaits_in_flight_tick() -> None:
    """shutdown must not return until the tracked tick finishes."""
    poller = _poller()
    started = asyncio.Event()
    finished = asyncio.Event()

    async def slow_tick() -> None:
        started.set()
        await asyncio.sleep(0.15)
        finished.set()

    poller._tick_task = asyncio.create_task(slow_tick())
    await started.wait()

    t0 = time.monotonic()
    await poller.shutdown()
    elapsed = time.monotonic() - t0

    assert finished.is_set()
    assert elapsed >= 0.1


@pytest.mark.asyncio
async def test_shutdown_returns_quickly_when_no_tick() -> None:
    poller = _poller()
    assert poller._tick_task is None

    t0 = time.monotonic()
    await poller.shutdown()
    elapsed = time.monotonic() - t0

    assert elapsed < 0.5
    assert poller._background_closed is True


@pytest.mark.asyncio
async def test_shutdown_times_out_waiting_for_tick() -> None:
    """After timeout, shutdown returns without cancelling the tick (shield)."""
    poller = _poller()
    cancelled = False

    async def never_finishes() -> None:
        nonlocal cancelled
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled = True
            raise

    poller._tick_task = asyncio.create_task(never_finishes())
    await asyncio.sleep(0)  # let task start

    with patch("koel.poller.SHUTDOWN_TICK_TIMEOUT_SECONDS", 0.05):
        t0 = time.monotonic()
        await poller.shutdown()
        elapsed = time.monotonic() - t0

    assert elapsed < 1.0
    assert cancelled is False
    # Clean up the still-running shielded task.
    task = poller._tick_task
    assert task is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_scheduled_tick_registers_and_clears_task() -> None:
    poller = _poller()
    seen: list[asyncio.Task[object] | None] = []

    async def capture_run_once(*, force: bool = False) -> list[object]:
        seen.append(poller._tick_task)
        assert poller._tick_task is asyncio.current_task()
        return []

    poller.run_once = capture_run_once  # type: ignore[method-assign]

    await poller._scheduled_tick()

    assert len(seen) == 1
    assert seen[0] is not None
    assert poller._tick_task is None


@pytest.mark.asyncio
async def test_shutdown_stops_scheduler_then_awaits_tick() -> None:
    """scheduler.shutdown(wait=False) runs before the in-flight tick completes."""
    poller = _poller()
    order: list[str] = []
    mid = asyncio.Event()

    scheduler = MagicMock()

    def _sched_shutdown(*, wait: bool = True) -> None:
        assert wait is False
        order.append("scheduler")

    scheduler.shutdown.side_effect = _sched_shutdown
    poller._scheduler = scheduler

    async def slow_tick() -> None:
        order.append("tick_start")
        mid.set()
        await asyncio.sleep(0.1)
        order.append("tick_done")

    poller._tick_task = asyncio.create_task(slow_tick())
    await mid.wait()

    await poller.shutdown()

    assert "scheduler" in order
    assert "tick_done" in order
    assert order.index("scheduler") < order.index("tick_done")
    assert poller._scheduler is None
    scheduler.shutdown.assert_called_once_with(wait=False)


def test_shutdown_timeout_constant() -> None:
    assert SHUTDOWN_TICK_TIMEOUT_SECONDS == 30.0


@pytest.mark.asyncio
async def test_shutdown_awaits_pdf_enrich_without_cancelling() -> None:
    """Timeout must not cancel PDF enrich (holds enrich lock / pool borrow)."""
    poller = _poller()
    cancelled = False
    started = asyncio.Event()

    async def slow_pdf() -> None:
        nonlocal cancelled
        async with poller._pdf_enrich_lock:
            started.set()
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled = True
                raise

    task = asyncio.create_task(slow_pdf(), name="koel_pdf_enrich")
    poller._pdf_enrich_tasks.add(task)
    task.add_done_callback(poller._pdf_enrich_tasks.discard)
    await started.wait()

    with patch("koel.poller.SHUTDOWN_TICK_TIMEOUT_SECONDS", 0.05):
        await poller.shutdown()

    assert cancelled is False
    assert poller._background_closed is True
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_shutdown_awaits_brief_drain_and_logs_exceptions() -> None:
    """Brief drain failures are logged; shutdown still closes background gate."""
    poller = _poller()
    started = asyncio.Event()

    async def boom() -> None:
        async with poller._brief_drain_lock:
            started.set()
            await asyncio.sleep(0.05)
            raise RuntimeError("brief boom")

    task = asyncio.create_task(boom(), name="koel_brief_drain")
    poller._brief_drain_tasks.add(task)
    task.add_done_callback(poller._brief_drain_tasks.discard)
    await started.wait()

    await poller.shutdown()

    assert task.done()
    assert poller._background_closed is True
    assert not poller._brief_drain_tasks


@pytest.mark.asyncio
async def test_shutdown_rejects_late_pdf_and_brief_schedules() -> None:
    """After drain, late tick must not spawn work that races storage.close()."""
    poller = _poller()
    await poller.shutdown()

    poller._schedule_pdf_enrichment(
        [PendingPdfEnrich(disclosure_id=1, symbol="JKH.N0000", external_id="1")]
    )
    assert not poller._pdf_enrich_tasks

    with patch("koel.poller.briefs_enabled", return_value=True):
        poller._schedule_brief_drain()
    assert not poller._brief_drain_tasks


@pytest.mark.asyncio
async def test_brief_drain_coalesces_while_lock_held() -> None:
    """Second schedule while drain owns the lock does not stack tasks."""
    poller = _poller()
    release = asyncio.Event()
    started = asyncio.Event()

    async def hold_lock() -> None:
        async with poller._brief_drain_lock:
            started.set()
            await release.wait()

    task = asyncio.create_task(hold_lock())
    poller._brief_drain_tasks.add(task)
    task.add_done_callback(poller._brief_drain_tasks.discard)
    await started.wait()

    with patch("koel.poller.briefs_enabled", return_value=True):
        poller._schedule_brief_drain()
    assert len(poller._brief_drain_tasks) == 1

    release.set()
    await task


@pytest.mark.asyncio
async def test_shutdown_drains_pdf_then_late_brief_from_same_window() -> None:
    """Shutdown re-scans so a brief task spawned mid-drain is still awaited."""
    poller = _poller()
    order: list[str] = []
    brief_started = asyncio.Event()

    async def pdf_then_spawn_brief() -> None:
        order.append("pdf")
        await asyncio.sleep(0.05)

        async def brief() -> None:
            order.append("brief")
            brief_started.set()

        t = asyncio.create_task(brief(), name="koel_brief_drain")
        poller._brief_drain_tasks.add(t)
        t.add_done_callback(poller._brief_drain_tasks.discard)

    pdf_task = asyncio.create_task(pdf_then_spawn_brief(), name="koel_pdf_enrich")
    poller._pdf_enrich_tasks.add(pdf_task)
    pdf_task.add_done_callback(poller._pdf_enrich_tasks.discard)

    await poller.shutdown()

    assert order == ["pdf", "brief"]
    assert brief_started.is_set()
    assert poller._background_closed is True
    assert not poller._pdf_enrich_tasks
    assert not poller._brief_drain_tasks
