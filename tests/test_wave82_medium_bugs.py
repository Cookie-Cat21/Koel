"""Wave82: medium+ bugs — claim/attempt/count/lock/health soft-accepts.

1. ``claim_alert`` / ``claim_and_disarm`` must isinstance-guard RETURNING ids
   (no ``int(True)==1`` soft-accept mid deliver / disarm).
2. ``mark_alert_attempt`` must isinstance-guard ``attempt_count`` (no
   ``int(True)==1`` undercount delaying dead-letter).
3. PG COUNT helpers must reject bool/non-int ``n`` (retention / brief cap /
   pending-briefs hint).
4. ``try_advisory_lock`` must require ``locked is True`` (no ``bool(1)``).
5. ``health_check`` must reject bool ``ok`` (``True == 1`` soft-accept).
6. ``pool_health_snapshot`` must reject bool stats (``isinstance(True, int)``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.domain import AlertEvent, AlertType
from koel.storage import Storage, _pg_count, _require_pg_int

ROOT = Path(__file__).resolve().parents[1]


class _Cursor:
    def __init__(self, *, one: Any = None, many: list[Any] | None = None) -> None:
        self._one = one
        self._many = many or []

    async def fetchone(self) -> Any:
        return self._one

    async def fetchall(self) -> list[Any]:
        return list(self._many)


class _Conn:
    def __init__(self, results: list[Any] | None = None) -> None:
        self._results = list(results or [])
        self.sql: list[str] = []

    async def execute(self, sql: str, params: Any = None) -> _Cursor:
        self.sql.append(sql)
        if not self._results:
            return _Cursor()
        nxt = self._results.pop(0)
        if isinstance(nxt, list):
            return _Cursor(many=nxt)
        return _Cursor(one=nxt)

    @asynccontextmanager
    async def transaction(self) -> Any:
        yield


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


def _event(**kwargs: object) -> AlertEvent:
    base: dict[str, object] = dict(
        rule_id=1,
        user_id=2,
        telegram_id=3,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        price=101.0,
        trigger="cross",
        event_key="k1",
        snapshot_id=9,
        fired_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    base.update(kwargs)
    return AlertEvent.model_construct(**base)  # type: ignore[arg-type]


def test_require_pg_int_and_pg_count_helpers() -> None:
    assert _require_pg_int(7, what="id") == 7
    with pytest.raises(ValueError, match="id failed validation"):
        _require_pg_int(True, what="id")
    with pytest.raises(ValueError, match="id failed validation"):
        _require_pg_int("7", what="id")
    with pytest.raises(ValueError, match="id failed validation"):
        _require_pg_int(None, what="id")

    assert _pg_count(0) == 0
    assert _pg_count(3) == 3
    assert _pg_count(True) is None
    assert _pg_count(False) is None
    assert _pg_count(-1) is None
    assert _pg_count("1") is None
    assert _pg_count(1.5) is None


@pytest.mark.asyncio
async def test_claim_alert_rejects_poisoned_returning_id() -> None:
    with pytest.raises(ValueError, match="claim_alert RETURNING id"):
        await _store(_Conn([{"id": True}])).claim_alert(_event(), "hi")
    with pytest.raises(ValueError, match="claim_alert RETURNING id"):
        await _store(_Conn([{"id": "9"}])).claim_alert(_event(), "hi")
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
    # Only the INSERT ran — disarm UPDATE must not execute on poison.
    assert len(conn.sql) == 1
    assert "INSERT INTO alert_log" in conn.sql[0]

    ok_conn = _Conn([{"id": 51}])
    assert await _store(ok_conn).claim_and_disarm(_event(), "hi") == 51
    assert any("UPDATE alert_rules" in s for s in ok_conn.sql)

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def claim_and_disarm")[1].split(
        "async def mark_delivery_attempted_ok"
    )[0]
    assert "_require_pg_int" in chunk
    assert 'int(_as_row(row)["id"])' not in chunk


@pytest.mark.asyncio
async def test_mark_alert_attempt_rejects_bool_attempt_count() -> None:
    with pytest.raises(ValueError, match="attempt_count failed validation"):
        await _store(_Conn([{"attempt_count": True}])).mark_alert_attempt(1)
    with pytest.raises(ValueError, match="attempt_count failed validation"):
        await _store(_Conn([{"attempt_count": "3"}])).mark_alert_attempt(1)
    assert await _store(_Conn([{"attempt_count": 3}])).mark_alert_attempt(1) == 3

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def mark_alert_attempt")[1].split(
        "async def dead_letter"
    )[0]
    assert "_require_pg_int" in chunk
    assert 'int(_as_row(row)["attempt_count"])' not in chunk


@pytest.mark.asyncio
async def test_count_helpers_reject_bool_n() -> None:
    assert await _store(_Conn([{"n": True}])).delete_old_non_watchlist_snapshots(7) == 0
    assert await _store(_Conn([{"n": -1}])).delete_old_non_watchlist_snapshots(7) == 0
    assert await _store(_Conn([{"n": 4}])).delete_old_non_watchlist_snapshots(7) == 4

    with pytest.raises(ValueError, match="count_briefs_today"):
        await _store(_Conn([{"n": True}])).count_briefs_today()
    assert await _store(_Conn([{"n": 2}])).count_briefs_today() == 2

    with pytest.raises(ValueError, match="count_pending_disclosure_briefs"):
        await _store(_Conn([{"n": False}])).count_pending_disclosure_briefs()
    assert await _store(_Conn([{"n": 7}])).count_pending_disclosure_briefs() == 7

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    assert "def _pg_count" in src
    assert 'int(_as_row(row).get("n") or 0)' not in src
    assert 'int(_as_row(row)["n"])' not in src


@pytest.mark.asyncio
async def test_claim_pending_briefs_skips_poisoned_used_count() -> None:
    # Queue: xact lock result, then poisoned used COUNT → empty claim.
    conn = _Conn([{"pg_advisory_xact_lock": None}, {"n": True}])
    out = await _store(conn).claim_pending_briefs(max_briefs_per_day=10, limit=5)
    assert out == []

    conn2 = _Conn([{"pg_advisory_xact_lock": None}, None])
    assert await _store(conn2).claim_pending_briefs(max_briefs_per_day=10, limit=5) == []


@pytest.mark.asyncio
async def test_try_advisory_lock_requires_locked_is_true() -> None:
    store = Storage("postgresql://unused", min_size=1, max_size=2)

    class _FakeCM:
        def __init__(self, conn: Any) -> None:
            self._conn = conn
            self.exited = False

        async def __aenter__(self) -> Any:
            return self._conn

        async def __aexit__(self, *_a: object) -> None:
            self.exited = True

    # Integer 1 must not soft-accept as a held lock.
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=_Cursor(one={"locked": 1}))
    cm = _FakeCM(conn)
    store._pool = MagicMock()
    store._pool.connection = MagicMock(return_value=cm)
    assert await store.try_advisory_lock(42) is False
    assert cm.exited is True
    assert store._lock_conn is None

    # Real bool True holds the lock.
    conn2 = MagicMock()
    conn2.execute = AsyncMock(return_value=_Cursor(one={"locked": True}))
    cm2 = _FakeCM(conn2)
    store2 = Storage("postgresql://unused", min_size=1, max_size=2)
    store2._pool = MagicMock()
    store2._pool.connection = MagicMock(return_value=cm2)
    assert await store2.try_advisory_lock(42) is True
    assert store2._lock_conn is conn2
    await store2.advisory_unlock(42)

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def try_advisory_lock")[1].split(
        "async def advisory_unlock"
    )[0]
    assert ".get(\"locked\") is True" in chunk or ".get('locked') is True" in chunk
    assert 'bool(row and _as_row(row)["locked"])' not in chunk


@pytest.mark.asyncio
async def test_health_check_rejects_bool_ok() -> None:
    assert await _store(_Conn([{"ok": True}])).health_check() is False
    assert await _store(_Conn([{"ok": 1}])).health_check() is True
    assert await _store(_Conn([{"ok": 0}])).health_check() is False
    assert await _store(_Conn([None])).health_check() is False

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def health_check")[1].split(
        "async def count_pending_disclosure_briefs"
    )[0]
    assert "not isinstance(raw_ok, bool)" in chunk
    assert 'bool(row and _as_row(row)["ok"] == 1)' not in chunk


def test_pool_health_snapshot_rejects_bool_stats() -> None:
    store = _store(_Conn([]))

    class _StatsPool:
        def get_stats(self) -> dict[str, Any]:
            return {
                "pool_min": True,
                "pool_max": 4,
                "pool_size": False,
                "pool_available": 1,
                "requests_waiting": 0,
            }

    store._pool = _StatsPool()  # type: ignore[assignment]
    store._last_health_checkout_wait_ms = 1.0
    snap = store.pool_health_snapshot()
    assert "pool_min" not in snap
    assert "pool_size" not in snap
    assert snap["pool_max"] == 4
    assert snap["pool_available"] == 1
    assert snap["requests_waiting"] == 0

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("def pool_health_snapshot")[1].split("def _row_to_snapshot")[0]
    assert "isinstance(value, bool)" in chunk
