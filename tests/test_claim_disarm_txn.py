"""E2-C03: claim + disarm in one DB transaction; conflict skips disarm."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.config import Settings
from chime.domain import AlertEvent, AlertType, PreviousPriceState, PriceSnapshot
from chime.poller import Poller
from chime.storage import Storage
from tests.conftest import make_rule


class _FakeResult:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row


class _FakeTxn:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> _FakeTxn:
        self.entered = True
        return self

    async def __aexit__(self, *args: object) -> None:
        self.exited = True


class _FakeConn:
    def __init__(self, *, claim_row: dict[str, Any] | None) -> None:
        self._claim_row = claim_row
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []
        self._txn = _FakeTxn()

    def transaction(self) -> _FakeTxn:
        return self._txn

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> _FakeResult:
        self.calls.append((sql, params))
        if "INSERT INTO alert_log" in sql:
            return _FakeResult(self._claim_row)
        return _FakeResult(None)


class _FakeCM:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        return None


def _event(*, rule_id: int = 1, event_key: str = "price:1:above:100:s42") -> AlertEvent:
    return AlertEvent(
        rule_id=rule_id,
        user_id=10,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="price crossed above 100.00",
        current_price=105.0,
        snapshot_id=42,
        event_key=event_key,
        set_armed=False,
    )


@pytest.mark.asyncio
async def test_claim_and_disarm_runs_in_one_transaction() -> None:
    """Successful claim UPDATE armed=False inside the same transaction."""
    storage = Storage("postgresql://unused", min_size=1, max_size=2)
    conn = _FakeConn(claim_row={"id": 501})
    storage._pool = MagicMock()
    storage._pool.connection = MagicMock(return_value=_FakeCM(conn))

    log_id = await storage.claim_and_disarm(_event(), "alert text")

    assert log_id == 501
    assert conn._txn.entered is True
    assert conn._txn.exited is True
    assert len(conn.calls) == 2
    assert "INSERT INTO alert_log" in conn.calls[0][0]
    assert "delivery_lease_until" in conn.calls[0][0]
    assert conn.calls[0][1] is not None
    assert conn.calls[0][1][-1] == 120
    assert "UPDATE alert_rules SET armed" in conn.calls[1][0]
    assert conn.calls[1][1] == (False, 1)


@pytest.mark.asyncio
async def test_claim_and_disarm_conflict_skips_disarm() -> None:
    """ON CONFLICT / no RETURNING row → None and no armed UPDATE."""
    storage = Storage("postgresql://unused", min_size=1, max_size=2)
    conn = _FakeConn(claim_row=None)
    storage._pool = MagicMock()
    storage._pool.connection = MagicMock(return_value=_FakeCM(conn))

    log_id = await storage.claim_and_disarm(_event(), "alert text")

    assert log_id is None
    assert conn._txn.entered is True
    assert len(conn.calls) == 1
    assert "INSERT INTO alert_log" in conn.calls[0][0]
    assert not any("UPDATE alert_rules SET armed" in sql for sql, _ in conn.calls)


@pytest.mark.asyncio
async def test_price_path_uses_claim_and_disarm() -> None:
    """_evaluate_price_snaps claims+disarms via claim_and_disarm, not set_rule_armed."""
    rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
    snap = PriceSnapshot(
        symbol="JKH.N0000",
        price=105.0,
        previous_close=98.0,
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        id=42,
    )

    storage = AsyncMock()
    storage.claim_and_disarm = AsyncMock(return_value=501)
    storage.claim_alert = AsyncMock(return_value=999)
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    storage.set_rule_armed = AsyncMock()
    storage.insert_snapshot = AsyncMock(side_effect=lambda s: s)
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=95.0))

    send = AsyncMock(return_value=False)
    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, AsyncMock(), send)

    fired = await poller._evaluate_price_snaps(
        [snap],
        rules_by_symbol={"JKH.N0000": [rule]},
    )

    assert len(fired) == 1
    storage.claim_and_disarm.assert_awaited_once()
    storage.claim_alert.assert_not_awaited()
    storage.set_rule_armed.assert_not_awaited()
    storage.mark_alert_attempt.assert_awaited_once_with(501)
