"""Wave84: medium+ bugs — claim/disarm/attempt/lock/count soft-accepts.

1. ``claim_alert`` / ``claim_and_disarm`` must isinstance-guard RETURNING ids
   (no ``int(True)==1`` soft-accept mid deliver / disarm).
2. ``mark_alert_attempt`` must isinstance-guard ``attempt_count``.
3. ``try_advisory_lock`` must require ``locked is True`` (no ``bool(1)``).
4. ``health_check`` must reject bool ``ok`` (``True == 1`` soft-accept).
5. PG COUNT helpers must reject bool / negative ``n`` (brief cap + retention).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from koel.domain import AlertEvent, AlertType
from koel.storage import Storage, _pg_count, _require_pg_int

ROOT = Path(__file__).resolve().parents[1]


class _Cursor:
    def __init__(self, *, one: Any = None) -> None:
        self._one = one

    async def fetchone(self) -> Any:
        return self._one


class _Conn:
    def __init__(self, results: list[Any] | None = None) -> None:
        self._results = list(results or [])
        self.sql: list[str] = []

    async def execute(self, sql: str, params: Any = None) -> _Cursor:
        self.sql.append(sql)
        if not self._results:
            return _Cursor()
        return _Cursor(one=self._results.pop(0))

    @asynccontextmanager
    async def transaction(self) -> Any:
        yield

    @asynccontextmanager
    async def connection(self) -> Any:
        yield self


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def connection(self) -> Any:
        yield self._conn


def _store(conn: _Conn) -> Storage:
    store = Storage("postgresql://unused", min_size=1, max_size=2)
    store._pool = _Pool(conn)  # type: ignore[assignment]
    return store


def _event() -> AlertEvent:
    return AlertEvent(
        rule_id=1,
        user_id=3,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="cross",
        current_price=101.0,
        event_key="above:100",
        snapshot_id=5,
    )


def test_require_pg_int_and_pg_count_helpers() -> None:
    assert _require_pg_int(42, what="id") == 42
    with pytest.raises(ValueError, match="failed validation"):
        _require_pg_int(True, what="id")
    with pytest.raises(ValueError, match="failed validation"):
        _require_pg_int("9", what="id")
    assert _pg_count(0) == 0
    assert _pg_count(3) == 3
    assert _pg_count(True) is None
    assert _pg_count(-1) is None
    assert _pg_count("1") is None


@pytest.mark.asyncio
async def test_claim_alert_rejects_poisoned_returning_id() -> None:
    with pytest.raises(ValueError, match="claim_alert RETURNING id"):
        await _store(_Conn([{"id": True}])).claim_alert(_event(), "hi")
    with pytest.raises(ValueError, match="claim_alert RETURNING id"):
        await _store(_Conn([{"id": [1]}])).claim_alert(_event(), "hi")
    assert await _store(_Conn([{"id": 50}])).claim_alert(_event(), "hi") == 50
    assert await _store(_Conn([None])).claim_alert(_event(), "hi") is None

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def claim_alert")[1].split("async def claim_and_disarm")[0]
    assert "_require_pg_int" in chunk
    assert 'int(_as_row(row)["id"])' not in chunk


@pytest.mark.asyncio
async def test_claim_and_disarm_rejects_poisoned_id_before_disarm() -> None:
    conn = _Conn([{"id": True}])
    with pytest.raises(ValueError, match="claim_and_disarm RETURNING id"):
        await _store(conn).claim_and_disarm(_event(), "hi")
    # Poisoned id must not reach the armed=False UPDATE (xact rolls back).
    assert not any("armed" in s.lower() for s in conn.sql)

    conn_ok = _Conn([{"id": 51}, None])
    assert await _store(conn_ok).claim_and_disarm(_event(), "hi") == 51
    assert any("armed" in s.lower() for s in conn_ok.sql)


@pytest.mark.asyncio
async def test_mark_alert_attempt_rejects_poisoned_count() -> None:
    with pytest.raises(ValueError, match="attempt_count"):
        await _store(_Conn([{"attempt_count": True}])).mark_alert_attempt(1)
    with pytest.raises(ValueError, match="attempt_count"):
        await _store(_Conn([{"attempt_count": "3"}])).mark_alert_attempt(1)
    assert await _store(_Conn([{"attempt_count": 3}])).mark_alert_attempt(1) == 3


@pytest.mark.asyncio
async def test_try_advisory_lock_requires_locked_is_true() -> None:
    # Truthy non-bool must not hold the pool connection.
    conn = _Conn([{"locked": 1}])
    store = _store(conn)
    assert await store.try_advisory_lock(99) is False
    assert store._lock_conn is None

    conn_s = _Conn([{"locked": "true"}])
    store_s = _store(conn_s)
    assert await store_s.try_advisory_lock(99) is False
    assert store_s._lock_conn is None

    conn_ok = _Conn([{"locked": True}])
    store_ok = _store(conn_ok)
    assert await store_ok.try_advisory_lock(99) is True
    assert store_ok._lock_conn is conn_ok
    await store_ok.advisory_unlock()

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def try_advisory_lock")[1].split("async def advisory_unlock")[0]
    assert 'get("locked") is True' in chunk
    assert 'bool(row and _as_row(row)["locked"])' not in chunk


@pytest.mark.asyncio
async def test_health_check_rejects_bool_ok() -> None:
    assert await _store(_Conn([{"ok": True}])).health_check() is False
    assert await _store(_Conn([{"ok": 1}])).health_check() is True
    assert await _store(_Conn([{"ok": 0}])).health_check() is False
    assert await _store(_Conn([None])).health_check() is False


@pytest.mark.asyncio
async def test_count_helpers_reject_bool_n() -> None:
    with pytest.raises(ValueError, match="count_briefs_today"):
        await _store(_Conn([{"n": True}])).count_briefs_today()
    assert await _store(_Conn([{"n": 4}])).count_briefs_today() == 4
    assert await _store(_Conn([None])).count_briefs_today() == 0

    with pytest.raises(ValueError, match="count_pending"):
        await _store(_Conn([{"n": True}])).count_pending_disclosure_briefs()
    assert await _store(_Conn([{"n": 7}])).count_pending_disclosure_briefs() == 7

    # Retention delete count fail-closed to 0 (no raise — tick must continue).
    assert await _store(_Conn([{"n": True}])).delete_old_non_watchlist_snapshots(7) == 0
    assert await _store(_Conn([{"n": 2}])).delete_old_non_watchlist_snapshots(7) == 2
