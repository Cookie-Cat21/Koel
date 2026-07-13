"""Wave85: medium+ bugs — claim/lock/health/count fail-closed.

1. ``claim_alert`` / ``claim_and_disarm`` must isinstance-guard RETURNING id
   (no ``int(True)==1`` soft-accept mid deliver / disarm).
2. ``mark_alert_attempt`` must isinstance-guard ``attempt_count`` (no undercount
   delaying dead-letter via ``int(True)==1``).
3. ``try_advisory_lock`` must require ``locked is True`` (no ``bool(1)/"t"``).
4. ``health_check`` must require int ``ok == 1`` (no ``True == 1`` soft-accept).
5. PG COUNT helpers must reject bool/non-int/negative (no ``int(True)==1``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from chime.domain import AlertEvent, AlertType
from chime.storage import Storage, _pg_count, _require_pg_int

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
        event_key="w85:above:100",
        snapshot_id=5,
    )


def test_require_pg_int_and_pg_count_helpers() -> None:
    assert _require_pg_int(7, what="id") == 7
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
        await _store(_Conn([{"id": "9"}])).claim_alert(_event(), "hi")
    assert await _store(_Conn([{"id": 88}])).claim_alert(_event(), "hi") == 88

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def claim_alert")[1].split("async def claim_and_disarm")[0]
    assert "_require_pg_int" in chunk
    assert 'int(_as_row(row)["id"])' not in chunk


@pytest.mark.asyncio
async def test_claim_and_disarm_rejects_poisoned_id_before_disarm() -> None:
    conn = _Conn([{"id": True}])
    with pytest.raises(ValueError, match="claim_and_disarm RETURNING id"):
        await _store(conn).claim_and_disarm(_event(), "hi")
    assert not any("armed" in s.lower() for s in conn.sql)

    ok = _Conn([{"id": 91}, None])
    assert await _store(ok).claim_and_disarm(_event(), "hi") == 91
    assert any("armed" in s.lower() for s in ok.sql)

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def claim_and_disarm")[1].split(
        "async def mark_delivery_attempted_ok"
    )[0]
    assert "_require_pg_int" in chunk
    assert 'int(_as_row(row)["id"])' not in chunk


@pytest.mark.asyncio
async def test_mark_alert_attempt_rejects_bool_count() -> None:
    with pytest.raises(ValueError, match="attempt_count"):
        await _store(_Conn([{"attempt_count": True}])).mark_alert_attempt(1)
    with pytest.raises(ValueError, match="attempt_count"):
        await _store(_Conn([{"attempt_count": 2.5}])).mark_alert_attempt(1)
    assert await _store(_Conn([{"attempt_count": 4}])).mark_alert_attempt(1) == 4

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def mark_alert_attempt")[1].split("async def dead_letter")[0]
    assert "_require_pg_int" in chunk
    assert 'int(_as_row(row)["attempt_count"])' not in chunk


@pytest.mark.asyncio
async def test_try_advisory_lock_requires_locked_is_true() -> None:
    assert await _store(_Conn([{"locked": 1}])).try_advisory_lock(1) is False
    assert await _store(_Conn([{"locked": "t"}])).try_advisory_lock(1) is False
    assert await _store(_Conn([{"locked": False}])).try_advisory_lock(1) is False

    store = _store(_Conn([{"locked": True}]))
    assert await store.try_advisory_lock(42) is True
    assert store._lock_conn is not None
    await store.advisory_unlock()

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def try_advisory_lock")[1].split("async def advisory_unlock")[0]
    assert '.get("locked") is True' in chunk
    assert 'bool(row and _as_row(row)["locked"])' not in chunk


@pytest.mark.asyncio
async def test_health_check_rejects_bool_ok_soft_accept() -> None:
    assert await _store(_Conn([{"ok": True}])).health_check() is False
    assert await _store(_Conn([{"ok": "1"}])).health_check() is False
    assert await _store(_Conn([None])).health_check() is False
    assert await _store(_Conn([{"ok": 1}])).health_check() is True

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def health_check")[1].split(
        "async def count_pending_disclosure_briefs"
    )[0]
    assert "isinstance(raw_ok, int)" in chunk
    assert '["ok"] == 1)' not in chunk.replace(" ", "")


@pytest.mark.asyncio
async def test_count_pending_and_briefs_today_reject_poisoned_n() -> None:
    with pytest.raises(ValueError, match="count_pending_disclosure_briefs"):
        await _store(_Conn([{"n": True}])).count_pending_disclosure_briefs()
    with pytest.raises(ValueError, match="count_pending_disclosure_briefs"):
        await _store(_Conn([{"n": -1}])).count_pending_disclosure_briefs()
    assert await _store(_Conn([{"n": 6}])).count_pending_disclosure_briefs() == 6
    assert await _store(_Conn([None])).count_pending_disclosure_briefs() == 0

    with pytest.raises(ValueError, match="count_briefs_today"):
        await _store(_Conn([{"n": False}])).count_briefs_today()
    assert await _store(_Conn([{"n": 2}])).count_briefs_today() == 2

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    pending = src.split("async def count_pending_disclosure_briefs")[1].split(
        "def pool_health_snapshot"
    )[0]
    today = src.split("async def count_briefs_today")[1].split("async def upsert_disclosure")[0]
    assert "_pg_count" in pending
    assert "_pg_count" in today
    assert 'int(_as_row(row)["n"])' not in pending
    assert "int(_as_row(row).get(\"n\") or 0)" not in today


@pytest.mark.asyncio
async def test_claim_pending_briefs_fails_closed_on_poisoned_used_count() -> None:
    """Poisoned daily-use COUNT must not understate and over-claim past the cap."""
    store = _store(_Conn([None, {"n": True}]))
    rows = await store.claim_pending_briefs(limit=3, max_briefs_per_day=50)
    assert rows == []

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def claim_pending_briefs")[1].split(
        "async def requeue_brief"
    )[0]
    assert "_pg_count" in chunk
    assert "int(_as_row(used_row).get(\"n\") or 0)" not in chunk


def test_pool_health_snapshot_skips_bool_stats() -> None:
    class _StatsPool:
        def get_stats(self) -> dict[str, Any]:
            return {
                "pool_min": True,
                "pool_max": 4,
                "pool_size": False,
                "pool_available": 2,
                "requests_waiting": 0,
            }

    store = Storage.__new__(Storage)
    store._pool = _StatsPool()  # type: ignore[attr-defined]
    store._last_health_checkout_wait_ms = 1.0
    snap = store.pool_health_snapshot()
    assert "pool_min" not in snap
    assert "pool_size" not in snap
    assert snap["pool_max"] == 4
    assert snap["pool_available"] == 2
    assert snap["requests_waiting"] == 0

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("def pool_health_snapshot")[1].split("def _row_to_snapshot")[0]
    assert "isinstance(value, bool)" in chunk
