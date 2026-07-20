"""Circuit breaker unit tests — no network."""

from __future__ import annotations

import asyncio
import time

import pytest

from koel.circuit import CircuitBreaker, CircuitOpenError, CircuitState


def test_opens_after_fail_max_failures() -> None:
    cb = CircuitBreaker(name="up", fail_max=3, reset_timeout=60.0)
    for _ in range(2):
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_open_error_when_open() -> None:
    cb = CircuitBreaker(name="up", fail_max=1, reset_timeout=60.0)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    async def boom() -> str:
        return "nope"

    with pytest.raises(CircuitOpenError, match="circuit open"):
        await cb.call(boom)


@pytest.mark.asyncio
async def test_half_open_after_reset_timeout_allows_one_trial() -> None:
    cb = CircuitBreaker(name="api", fail_max=1, reset_timeout=0.05)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    await asyncio.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    async def ok() -> str:
        return "ok"

    result = await cb.call(ok)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_second_trial_blocked() -> None:
    cb = CircuitBreaker(name="api", fail_max=1, reset_timeout=0.05)
    cb.record_failure()
    await asyncio.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    # Mark trial in progress without completing call
    cb._before_call()
    assert cb._half_open_trial is True

    async def fn() -> None:
        return None

    with pytest.raises(CircuitOpenError, match="half-open busy"):
        await cb.call(fn)


@pytest.mark.asyncio
async def test_half_open_single_probe_no_stampede() -> None:
    """E11-C01: concurrent half-open callers — only one probe; others busy."""
    cb = CircuitBreaker(name="api", fail_max=1, reset_timeout=0.05)
    cb.record_failure()
    await asyncio.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    started = asyncio.Event()
    release = asyncio.Event()
    probe_count = 0

    async def slow_ok() -> str:
        nonlocal probe_count
        probe_count += 1
        started.set()
        await release.wait()
        return "ok"

    async def race() -> str | BaseException:
        try:
            return await cb.call(slow_ok)
        except BaseException as exc:
            return exc

    t1 = asyncio.create_task(race())
    await started.wait()
    # Stampede while first probe in flight
    others = await asyncio.gather(*(race() for _ in range(5)))
    release.set()
    first = await t1

    assert first == "ok"
    assert probe_count == 1
    assert all(isinstance(r, CircuitOpenError) for r in others)
    assert all("half-open busy" in str(r) for r in others)
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_success_closes_circuit() -> None:
    cb = CircuitBreaker(name="api", fail_max=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    await asyncio.sleep(0.06)

    async def ok() -> int:
        return 42

    assert await cb.call(ok) == 42
    assert cb.state == CircuitState.CLOSED
    assert cb._failures == 0


@pytest.mark.asyncio
async def test_failure_in_call_records_and_reraises() -> None:
    cb = CircuitBreaker(name="api", fail_max=5, reset_timeout=60.0)

    async def bad() -> None:
        raise ValueError("upstream")

    with pytest.raises(ValueError, match="upstream"):
        await cb.call(bad)
    assert cb._failures == 1
    assert cb.state == CircuitState.CLOSED


def test_half_open_failure_reopens() -> None:
    cb = CircuitBreaker(name="api", fail_max=5, reset_timeout=0.05)
    cb._state = CircuitState.HALF_OPEN
    cb._opened_at = time.monotonic() - 1.0
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
