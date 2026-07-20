"""HTTP health endpoint honesty + non-loopback redaction (WS-095)."""

from __future__ import annotations

import http.client
import json
import socket
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager

from koel.health import HealthState, _is_loopback_host, start_health_server


def _ephemeral_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _health_server(state: HealthState, host: str = "127.0.0.1") -> Iterator[int]:
    port = _ephemeral_port()
    server = start_health_server(host, port, state)
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


def _get_json(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


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


def test_is_loopback_host() -> None:
    assert _is_loopback_host("127.0.0.1") is True
    assert _is_loopback_host("::1") is True
    assert _is_loopback_host("[::1]") is True
    assert _is_loopback_host("0.0.0.0") is False
    assert _is_loopback_host("192.168.1.10") is False


def test_loopback_health_includes_last_error_detail() -> None:
    state = HealthState()
    state.update(
        ok=False,
        last_error="OperationalError: connection to host db.internal user koel failed",
        lock_held_skip=False,
        db_ok=False,
    )
    with _health_server(state, host="127.0.0.1") as port:
        code, body = _get_json(f"http://127.0.0.1:{port}/health")
    assert code == 503
    assert body["status"] == "degraded"
    assert "last_error" in body
    assert "db.internal" in body["last_error"]
    assert body["db_ok"] is False


def test_non_loopback_health_redacts_last_error() -> None:
    """Bind 0.0.0.0 but fetch via 127.0.0.1 — redaction keys off bind host."""
    state = HealthState()
    state.update(
        ok=False,
        last_error="OperationalError: connection to host db.internal user koel failed",
        lock_held_skip=True,
        db_ok=False,
        last_tick_ok=False,
    )
    with _health_server(state, host="0.0.0.0") as port:
        code, body = _get_json(f"http://127.0.0.1:{port}/health")
    assert code == 503
    assert body["status"] == "degraded"
    assert body["ok"] is False
    assert "last_error" not in body
    assert "db_ok" not in body
    assert "lock_held_skip" not in body
    assert set(body.keys()) <= {"status", "ok"}


def test_non_loopback_ok_payload_is_minimal() -> None:
    state = HealthState()
    state.update(ok=True, last_error=None, db_ok=True)
    with _health_server(state, host="0.0.0.0") as port:
        code, body = _get_json(f"http://127.0.0.1:{port}/health")
    assert code == 200
    assert body == {"status": "ok", "ok": True}
