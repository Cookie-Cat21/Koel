"""Wave14: cover remaining health.py branches + circuit.py edge pins."""

from __future__ import annotations

import asyncio
import http.client
import json
import socket
import time
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.circuit import CircuitBreaker, CircuitOpenError, CircuitState
from koel.health import (
    HealthState,
    brief_queue_health_hint,
    pdf_enrich_hint_from_poller,
    pending_briefs_count,
    start_health_server,
)


@contextmanager
def _health_server(state: HealthState, host: str = "127.0.0.1") -> Iterator[int]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    server = start_health_server(host, port, state)
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()


def _get(port: int, path: str) -> tuple[int, dict[str, object] | None]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        raw = resp.read()
        if not raw:
            return resp.status, None
        return resp.status, json.loads(raw.decode())
    finally:
        conn.close()


# --- health.py: pdf_enrich_hint_from_poller ---


def test_pdf_enrich_hint_rejects_async_snapshot() -> None:
    """Line 30: async pdf_enrich_health_snapshot must not be awaited here."""
    poller = MagicMock()
    poller.pdf_enrich_health_snapshot = AsyncMock(
        return_value={"in_flight_tasks": 1, "last_batch_size": 1, "batches_started": 1}
    )
    assert pdf_enrich_hint_from_poller(poller) == {}


def test_pdf_enrich_hint_rejects_non_callable_and_missing() -> None:
    poller = MagicMock(spec=[])  # no pdf_enrich_health_snapshot
    assert pdf_enrich_hint_from_poller(poller) == {}

    poller2 = MagicMock()
    poller2.pdf_enrich_health_snapshot = "not-a-fn"
    assert pdf_enrich_hint_from_poller(poller2) == {}


def test_pdf_enrich_hint_rejects_non_dict_and_filters_bad_ints() -> None:
    poller = MagicMock()
    poller.pdf_enrich_health_snapshot = MagicMock(return_value=["not", "a", "dict"])
    assert pdf_enrich_hint_from_poller(poller) == {}

    poller.pdf_enrich_health_snapshot = MagicMock(
        return_value={
            "in_flight_tasks": True,  # bool rejected
            "last_batch_size": -1,  # negative rejected
            "batches_started": "3",  # non-int rejected
            "extra_ignored": 99,
        }
    )
    assert pdf_enrich_hint_from_poller(poller) == {}

    poller.pdf_enrich_health_snapshot = MagicMock(
        return_value={
            "in_flight_tasks": 2,
            "last_batch_size": False,
            "batches_started": 0,
        }
    )
    hint = pdf_enrich_hint_from_poller(poller)
    assert hint == {"in_flight_tasks": 2, "batches_started": 0}
    assert "last_batch_size" not in hint


# --- health.py: pending_briefs_count + brief_queue_health_hint ---


@pytest.mark.asyncio
async def test_pending_briefs_count_sync_and_invalid() -> None:
    storage = MagicMock()
    storage.count_pending_disclosure_briefs = MagicMock(return_value=5)
    assert await pending_briefs_count(storage) == 5

    storage.count_pending_disclosure_briefs = MagicMock(return_value=True)
    assert await pending_briefs_count(storage) is None

    storage.count_pending_disclosure_briefs = MagicMock(return_value=-2)
    assert await pending_briefs_count(storage) is None

    storage2 = MagicMock(spec=[])
    assert await pending_briefs_count(storage2) is None


@pytest.mark.asyncio
async def test_brief_queue_hint_omits_empty_pdf_and_none_inputs() -> None:
    """Branch 71→75: poller present but empty pdf snapshot → no pdf_enrich key."""
    poller = MagicMock()
    poller.pdf_enrich_health_snapshot = MagicMock(return_value={})
    storage = MagicMock()
    storage.count_pending_disclosure_briefs = AsyncMock(return_value=3)

    hint = await brief_queue_health_hint(storage=storage, poller=poller)
    assert hint == {"pending_briefs": 3}
    assert "pdf_enrich" not in hint

    assert await brief_queue_health_hint(storage=None, poller=None) == {}


# --- health.py: HealthState + HTTP paths ---


def test_health_state_update_without_ok_preserves_flag() -> None:
    """Branch 86→exit: update without ok leaves self.ok untouched."""
    state = HealthState()
    assert state.ok is True
    state.update(db_ok=True, last_error=None)
    assert state.ok is True
    assert state.details["db_ok"] is True
    state.ok = False
    state.update(watched_missing=["JKH.N0000"])
    assert state.ok is False
    assert state.details["watched_missing"] == ["JKH.N0000"]


def test_healthz_and_root_alias_paths() -> None:
    state = HealthState()
    state.update(ok=True, db_ok=True)
    with _health_server(state) as port:
        for path in ("/healthz", "/"):
            status, body = _get(port, path)
            assert status == 200
            assert body is not None
            assert body["status"] == "ok"
            assert body["db_ok"] is True


def test_health_unknown_path_returns_404_empty_body() -> None:
    state = HealthState()
    with _health_server(state) as port:
        status, body = _get(port, "/metrics")
    assert status == 404
    assert body is None


# --- circuit.py: residual edge pins ---


def test_open_without_opened_at_stays_open() -> None:
    """OPEN with _opened_at is None must not auto-transition to half-open."""
    cb = CircuitBreaker(name="api", fail_max=1, reset_timeout=0.01)
    cb._state = CircuitState.OPEN
    cb._opened_at = None
    assert cb.state == CircuitState.OPEN
    snap = cb.snapshot()
    assert snap["state"] == "open"
    assert snap["half_open_trial"] is False


@pytest.mark.asyncio
async def test_half_open_failure_via_call_reopens_and_blocks() -> None:
    cb = CircuitBreaker(name="api", fail_max=5, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    await asyncio.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    async def bad() -> None:
        raise RuntimeError("probe fail")

    with pytest.raises(RuntimeError, match="probe fail"):
        await cb.call(bad)
    assert cb.state == CircuitState.OPEN

    async def ok() -> str:
        return "nope"

    with pytest.raises(CircuitOpenError, match="circuit open"):
        await cb.call(ok)


def test_snapshot_reflects_half_open_after_timeout() -> None:
    cb = CircuitBreaker(name="tradeSummary", fail_max=1, reset_timeout=0.05)
    cb.record_failure()
    assert cb.snapshot()["state"] == "open"
    time.sleep(0.06)
    snap = cb.snapshot()
    assert snap["state"] == "half_open"
    assert snap["failures"] == 1
    assert snap["name"] == "tradeSummary"
