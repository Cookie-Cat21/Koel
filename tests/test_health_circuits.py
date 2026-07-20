"""E8-C01: circuit breaker snapshots appear in loopback health details."""

from __future__ import annotations

import http.client
import json
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.__main__ import _refresh_both_health
from koel.adapters.cse import CSEClient
from koel.circuit import CircuitBreaker
from koel.health import HealthState, start_health_server


@contextmanager
def _health_server(state: HealthState) -> Iterator[int]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    server = start_health_server("127.0.0.1", port, state)
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()


def test_circuit_breaker_snapshot_shape() -> None:
    cb = CircuitBreaker(name="tradeSummary", fail_max=2, reset_timeout=30.0)
    cb.record_failure()
    snap = cb.snapshot()
    assert snap["name"] == "tradeSummary"
    assert snap["state"] == "closed"
    assert snap["failures"] == 1
    assert snap["fail_max"] == 2
    assert snap["reset_timeout_seconds"] == 30.0
    assert snap["half_open_trial"] is False


def test_cse_client_circuit_metrics_empty_then_populated() -> None:
    client = CSEClient(fail_max=1, reset_timeout=60.0, client=AsyncMock())
    assert client.circuit_metrics() == {}
    breaker = client._breaker("tradeSummary")
    breaker.record_failure()
    metrics = client.circuit_metrics()
    assert metrics["tradeSummary"]["state"] == "open"
    assert metrics["tradeSummary"]["failures"] == 1


@pytest.mark.asyncio
async def test_refresh_both_health_exports_circuits() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    poller = MagicMock()
    poller.last_tick_ok = True
    poller.last_tick_at = None
    poller.price_poll_ok = True
    poller.disclosure_poll_ok = True
    poller.lock_held_skip = False
    poller.watched_missing = []
    poller.last_error = None
    poller.cse = MagicMock()
    poller.cse.circuit_metrics = MagicMock(
        return_value={
            "tradeSummary": {
                "name": "tradeSummary",
                "state": "open",
                "failures": 5,
                "fail_max": 5,
                "reset_timeout_seconds": 60.0,
                "half_open_trial": False,
            }
        }
    )

    health = HealthState()
    await _refresh_both_health(storage, health, poller)

    assert health.ok is True
    assert health.details["circuits"]["tradeSummary"]["state"] == "open"

    with _health_server(health) as port:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/health")
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
        finally:
            conn.close()
    assert resp.status == 200
    assert body["circuits"]["tradeSummary"]["failures"] == 5
    assert body["circuits"]["tradeSummary"]["half_open_trial"] is False
