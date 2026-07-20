"""E8-O02 / E8-Q02: loopback health includes watched_missing; non-empty → 503."""

from __future__ import annotations

import http.client
import json
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.__main__ import _refresh_both_health
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


@pytest.mark.asyncio
async def test_refresh_both_health_exports_watched_missing() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    poller = MagicMock()
    poller.last_tick_ok = False
    poller.last_tick_at = None
    poller.price_poll_ok = False
    poller.disclosure_poll_ok = True
    poller.lock_held_skip = False
    poller.watched_missing = ["COMB.N0000", "SAMP.N0000"]
    poller.last_error = "poll_degraded"
    poller.cse = MagicMock()
    poller.cse.circuit_metrics = MagicMock(return_value={})

    health = HealthState()
    await _refresh_both_health(storage, health, poller)

    assert health.details["watched_missing"] == ["COMB.N0000", "SAMP.N0000"]
    assert health.ok is False
    assert health.details["price_poll_ok"] is False


@pytest.mark.asyncio
async def test_watched_missing_alone_forces_degraded_even_if_tick_ok() -> None:
    """E8-Q02 wiring: non-empty watched_missing ⇒ health.ok False."""
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    poller = MagicMock()
    poller.last_tick_ok = True
    poller.last_tick_at = None
    poller.price_poll_ok = True
    poller.disclosure_poll_ok = True
    poller.lock_held_skip = False
    poller.watched_missing = ["COMB.N0000"]
    poller.last_error = None
    poller.cse = MagicMock()
    poller.cse.circuit_metrics = MagicMock(return_value={})

    health = HealthState()
    await _refresh_both_health(storage, health, poller)

    assert health.ok is False
    assert health.details["watched_missing"] == ["COMB.N0000"]
    assert health.details["last_tick_ok"] is True

    with _health_server(health) as port:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/health")
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
        finally:
            conn.close()
    assert resp.status == 503
    assert body["status"] == "degraded"
    assert body["watched_missing"] == ["COMB.N0000"]


def test_loopback_health_json_includes_watched_missing() -> None:
    state = HealthState()
    state.update(
        ok=False,
        watched_missing=["COMB.N0000"],
        price_poll_ok=False,
        last_error="poll_degraded",
    )
    with _health_server(state) as port:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/health")
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
        finally:
            conn.close()
    assert resp.status == 503
    assert body["watched_missing"] == ["COMB.N0000"]
    assert body["last_error"] == "poll_degraded"
