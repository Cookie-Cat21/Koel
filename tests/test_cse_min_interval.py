"""Wave16: CSE_MIN_INTERVAL_SECONDS soft pacing between CSE HTTP calls."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from chime.adapters.cse import CSEClient
from chime.config import Settings

_DSN = "postgresql://chime:chime@localhost:5432/chime"


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
    monkeypatch.setattr("chime.adapters.cse.asyncio.sleep", sleep_mock)

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
    monkeypatch.setattr("chime.adapters.cse.asyncio.sleep", sleep_mock)

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
    monkeypatch.setattr("chime.adapters.cse.asyncio.sleep", sleep_mock)

    clock = {"t": 100.0}

    def _mono() -> float:
        return clock["t"]

    monkeypatch.setattr("chime.adapters.cse.time.monotonic", _mono)

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
    monkeypatch.setattr("chime.adapters.cse.asyncio.sleep", sleep_mock)

    http = AsyncMock()
    http.request = AsyncMock(return_value=_ok_response())
    client = CSEClient(min_interval_seconds=0.3, client=http)

    import asyncio

    await asyncio.gather(
        client._request("POST", "/tradeSummary", json_body={}),
        client._request("POST", "/tradeSummary", json_body={}),
    )
    assert http.request.await_count == 2
    assert sleep_mock.await_count == 1
