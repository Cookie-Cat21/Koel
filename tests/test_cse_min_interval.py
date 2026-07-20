"""Wave16: CSE_MIN_INTERVAL_SECONDS soft pacing between CSE HTTP calls."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from koel.adapters.cse import CSEClient
from koel.config import Settings

_DSN = "postgresql://koel:koel@localhost:5432/koel"


def test_cse_min_interval_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.delenv("CSE_MIN_INTERVAL_SECONDS", raising=False)
    settings = Settings.from_env(require_token=True)
    assert settings.cse_min_interval_seconds == 0.0


def test_cse_min_interval_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("CSE_MIN_INTERVAL_SECONDS", "0.25")
    settings = Settings.from_env(require_token=True)
    assert settings.cse_min_interval_seconds == 0.25


@pytest.mark.parametrize("raw", ["-1", "-0.5", "nan", "inf"])
def test_cse_min_interval_rejects_bad(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("CSE_MIN_INTERVAL_SECONDS", raw)
    settings = Settings.from_env(require_token=True)
    assert settings.cse_min_interval_seconds == 0.0


def _ok_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={"reqTradeSummery": []},
        request=httpx.Request("POST", "https://www.cse.lk/api/tradeSummary"),
        headers={"content-type": "application/json"},
    )


@pytest.mark.asyncio
async def test_pace_sleeps_between_requests_not_before_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.adapters.cse.asyncio.sleep", sleep_mock)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0.2, client=http)

    await client._request("POST", "/tradeSummary", json_body={})
    await client._request("POST", "/tradeSummary", json_body={})
    await client._request("POST", "/tradeSummary", json_body={})

    assert http.request.await_count == 3
    assert sleep_mock.await_count == 2
    for call in sleep_mock.await_args_list:
        assert call.args[0] == pytest.approx(0.2, abs=0.05)


@pytest.mark.asyncio
async def test_pace_disabled_when_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.adapters.cse.asyncio.sleep", sleep_mock)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0, client=http)

    await client._request("POST", "/tradeSummary", json_body={})
    await client._request("POST", "/tradeSummary", json_body={})

    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_pace_skips_sleep_when_gap_already_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If wall time since last call already exceeds min interval, no sleep."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.adapters.cse.asyncio.sleep", sleep_mock)

    clock = {"t": 100.0}

    def _mono() -> float:
        return clock["t"]

    monkeypatch.setattr("koel.adapters.cse.time.monotonic", _mono)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0.5, client=http)

    await client._request("POST", "/tradeSummary", json_body={})
    clock["t"] = 100.6  # already past 0.5s gap
    await client._request("POST", "/tradeSummary", json_body={})

    sleep_mock.assert_not_awaited()
    assert http.request.await_count == 2


@pytest.mark.asyncio
async def test_pace_lock_serializes_concurrent_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two concurrent _request calls still honor min interval (one sleep)."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.adapters.cse.asyncio.sleep", sleep_mock)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0.3, client=http)

    await asyncio.gather(
        client._request("POST", "/tradeSummary", json_body={}),
        client._request("POST", "/tradeSummary", json_body={}),
    )
    assert http.request.await_count == 2
    assert sleep_mock.await_count == 1


@pytest.mark.asyncio
async def test_pace_three_concurrent_callers_two_sleeps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N concurrent _request calls → N-1 sleeps (first is free)."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.adapters.cse.asyncio.sleep", sleep_mock)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0.25, client=http)

    await asyncio.gather(
        *(client._request("POST", "/tradeSummary", json_body={}) for _ in range(3))
    )
    assert http.request.await_count == 3
    assert sleep_mock.await_count == 2
    for call in sleep_mock.await_args_list:
        assert call.args[0] == pytest.approx(0.25, abs=0.05)


@pytest.mark.asyncio
async def test_pace_concurrent_after_prior_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After one paced call, two concurrent callers each sleep the full gap."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.adapters.cse.asyncio.sleep", sleep_mock)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0.4, client=http)

    await client._request("POST", "/tradeSummary", json_body={})
    sleep_mock.assert_not_awaited()

    await asyncio.gather(
        client._request("POST", "/tradeSummary", json_body={}),
        client._request("POST", "/tradeSummary", json_body={}),
    )
    assert http.request.await_count == 3
    # Both concurrent callers see a recent last_request_at and sleep.
    assert sleep_mock.await_count == 2
    for call in sleep_mock.await_args_list:
        assert call.args[0] == pytest.approx(0.4, abs=0.05)


@pytest.mark.asyncio
async def test_pace_concurrent_zero_interval_no_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent callers with pacing off never sleep (early return)."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr("koel.adapters.cse.asyncio.sleep", sleep_mock)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0.0, client=http)

    await asyncio.gather(
        *(client._request("POST", "/tradeSummary", json_body={}) for _ in range(4))
    )
    assert http.request.await_count == 4
    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_pace_concurrent_advances_last_request_under_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sleep under the lock advances monotonic so stamped gaps stay >= interval."""
    clock = {"t": 1_000.0}
    sleeps: list[float] = []

    def _mono() -> float:
        return clock["t"]

    async def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["t"] += seconds

    monkeypatch.setattr("koel.adapters.cse.time.monotonic", _mono)
    monkeypatch.setattr("koel.adapters.cse.asyncio.sleep", _sleep)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0.2, client=http)

    await asyncio.gather(
        *(client._request("POST", "/tradeSummary", json_body={}) for _ in range(3))
    )

    assert http.request.await_count == 3
    assert len(sleeps) == 2
    assert all(s == pytest.approx(0.2, abs=1e-9) for s in sleeps)
    # First free at t=1000; after two paced stamps: 1000.2 and 1000.4.
    assert client._last_request_at == pytest.approx(1_000.4, abs=1e-9)
