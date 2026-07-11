"""HTTP health endpoint honesty — 200/ok vs 503/degraded."""

from __future__ import annotations

import http.client
import json
import socket
from collections.abc import Iterator
from contextlib import contextmanager

from chime.health import HealthState, start_health_server


def _ephemeral_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _health_server(state: HealthState) -> Iterator[int]:
    port = _ephemeral_port()
    server = start_health_server("127.0.0.1", port, state)
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()


def _get_health(port: int) -> tuple[int, dict[str, object]]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        return resp.status, body
    finally:
        conn.close()


def test_health_ok_returns_200() -> None:
    state = HealthState()
    assert state.ok is True
    with _health_server(state) as port:
        status, body = _get_health(port)
    assert status == 200
    assert body["status"] == "ok"


def test_health_degraded_returns_503() -> None:
    state = HealthState()
    state.ok = False
    with _health_server(state) as port:
        status, body = _get_health(port)
    assert status == 503
    assert body["status"] == "degraded"
