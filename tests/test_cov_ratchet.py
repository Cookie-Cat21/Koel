"""Small unit pins for config / domain / logging / health 404 (E3-Q01 ratchet)."""

from __future__ import annotations

import http.client
import socket
from collections.abc import Iterator
from contextlib import contextmanager

from chime.config import migrations_dir
from chime.domain import AlertEvent, AlertType, as_dict
from chime.health import HealthState, start_health_server
from chime.logging_setup import configure_logging, get_logger


def test_migrations_dir_points_at_sql() -> None:
    path = migrations_dir()
    assert path.is_dir()
    assert any(path.glob("*.sql"))


def test_as_dict_dumps_alert_event() -> None:
    event = AlertEvent(
        rule_id=1,
        user_id=2,
        telegram_id=3,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="cross",
        current_price=105.0,
        event_key="k",
    )
    data = as_dict(event)
    assert data["symbol"] == "JKH.N0000"
    assert data["type"] in (AlertType.PRICE_ABOVE, "price_above")


def test_configure_logging_and_get_logger() -> None:
    configure_logging("WARNING")
    log = get_logger("chime.test_cov")
    log.warning("cov_pin", ok=True)


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


def test_health_unknown_path_returns_404() -> None:
    state = HealthState()
    with _health_server(state) as port:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/nope")
            resp = conn.getresponse()
            assert resp.status == 404
            resp.read()
        finally:
            conn.close()
