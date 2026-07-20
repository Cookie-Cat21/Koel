"""E12-O01: both-mode health exposes real DB pool checkout contention."""

from __future__ import annotations

import http.client
import json
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.__main__ import POOL_CHECKOUT_WAIT_ELEVATED_MS, _refresh_both_health
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
    return poller


class _StorageWithPoolSnapshot:
    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.health_check = AsyncMock(return_value=True)
        self._snapshot = snapshot

    def pool_health_snapshot(self) -> dict[str, Any]:
        return dict(self._snapshot)


@pytest.mark.asyncio
async def test_both_health_degrades_on_elevated_pool_checkout_wait() -> None:
    storage = _StorageWithPoolSnapshot(
        {
            "health_checkout_wait_ms": POOL_CHECKOUT_WAIT_ELEVATED_MS + 1.0,
            "pool_max": 4,
            "pool_available": 0,
            "requests_waiting": 0,
        }
    )
    health = HealthState()

    await _refresh_both_health(storage, health, _healthy_poller())  # type: ignore[arg-type]

    assert health.ok is False
    assert health.details["db_ok"] is True
    pool = health.details["db_pool"]
    assert pool["health_checkout_wait_ms"] == POOL_CHECKOUT_WAIT_ELEVATED_MS + 1.0
    assert pool["checkout_wait_elevated"] is True
    assert pool["contention"] is True

    with _health_server(health) as port:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/health")
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
        finally:
            conn.close()

    assert resp.status == 503
    assert body["db_pool"]["checkout_wait_elevated"] is True
    assert body["db_pool"]["checkout_wait_elevated_after_ms"] == POOL_CHECKOUT_WAIT_ELEVATED_MS


@pytest.mark.asyncio
async def test_both_health_omits_pool_signal_without_real_snapshot() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    health = HealthState()

    await _refresh_both_health(storage, health, _healthy_poller())

    assert health.ok is True
    assert "db_pool" not in health.details
