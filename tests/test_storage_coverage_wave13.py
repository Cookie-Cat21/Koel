"""Wave13: unit coverage push for remaining storage.py branches (mock pool)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
from psycopg.errors import UniqueViolation

from koel.domain import AlertType
from koel.storage import Storage
from tests.test_storage_unit import _Conn, _store


@pytest.mark.asyncio
async def test_close_unlocks_held_advisory_lock() -> None:
    conn = _Conn([{"locked": True}, None])
    store = _store(conn)
    assert await store.try_advisory_lock(99) is True
    assert store._lock_conn is conn
    await store.close()
    assert store._lock_conn is None
    assert store._pool.closed is True  # type: ignore[attr-defined]
    assert any("pg_advisory_unlock" in s for s in conn.sql)


@pytest.mark.asyncio
async def test_connection_context_yields_pool_conn() -> None:
    conn = _Conn([])
    store = _store(conn)
    async with store.connection() as got:
        assert got is conn


@pytest.mark.asyncio
async def test_list_stock_names_filters_blank_rows() -> None:
    conn = _Conn(
        [
            [
                {"symbol": "jkh.n0000", "name": "  John Keells  "},
                {"symbol": "  ", "name": "Blank Sym"},
                {"symbol": "COMB.N0000", "name": "   "},
                {"symbol": "LOLC.N0000", "name": "LOLC"},
            ]
        ]
    )
    store = _store(conn)
    out = await store.list_stock_names()
    assert out == [("JKH.N0000", "John Keells"), ("LOLC.N0000", "LOLC")]
    assert "FROM stocks" in conn.sql[0]
    assert "btrim(name)" in conn.sql[0]


@pytest.mark.asyncio
async def test_latest_snapshot_none_when_missing() -> None:
    conn = _Conn([None])
    store = _store(conn)
    assert await store.latest_snapshot("JKH.N0000") is None
    assert conn.params[0] == ("JKH.N0000",)


@pytest.mark.asyncio
async def test_get_ready_filing_brief_non_string_brief() -> None:
    conn = _Conn([{"brief": 123}])
    store = _store(conn)
    assert await store.get_ready_filing_brief(disclosure_id=7) is None


@pytest.mark.asyncio
async def test_get_latest_ready_brief_non_string_brief() -> None:
    conn = _Conn(
        [
            {
                "brief": None,
                "symbol": "JKH.N0000",
                "title": "AGM",
                "url": None,
                "external_id": "1",
                "disclosure_id": 7,
            }
        ]
    )
    store = _store(conn)
    assert await store.get_latest_ready_brief("JKH.N0000") is None


@pytest.mark.asyncio
async def test_create_alert_rule_unique_violation_reraise_when_race_lost() -> None:
    conn = _Conn()
    conn.rollback = AsyncMock()  # type: ignore[attr-defined]
    # upsert, add_watch x2, fetch None, UniqueViolation, fetch None → raise
    conn._results = [None, None, None, None, UniqueViolation("dup"), None]
    store = _store(conn)
    with pytest.raises(UniqueViolation):
        await store.create_alert_rule(3, "JKH.N0000", AlertType.DAILY_MOVE, 5.0)
    conn.rollback.assert_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_advisory_unlock_noop_when_no_lock_held() -> None:
    store = _store(_Conn([]))
    assert store._lock_conn is None
    await store.advisory_unlock()
    assert store._lock_conn is None


@pytest.mark.asyncio
async def test_health_check_records_wait_when_checkout_fails() -> None:
    class _BoomPool:
        @asynccontextmanager
        async def connection(self) -> Any:
            raise RuntimeError("pool exhausted")
            yield  # pragma: no cover

    store = Storage("postgresql://unused", min_size=1, max_size=2)
    store._pool = _BoomPool()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="pool exhausted"):
        await store.health_check()
    assert store._last_health_checkout_wait_ms is not None
    assert store._last_health_checkout_wait_ms >= 0


@pytest.mark.asyncio
async def test_health_check_reraises_execute_failure() -> None:
    conn = _Conn([RuntimeError("select failed")])
    store = _store(conn)
    with pytest.raises(RuntimeError, match="select failed"):
        await store.health_check()
    assert store._last_health_checkout_wait_ms is not None


def test_pool_health_snapshot_copies_int_stats() -> None:
    store = _store(_Conn([]))

    class _StatsPool:
        def get_stats(self) -> dict[str, Any]:
            return {
                "pool_min": 1,
                "pool_max": 4,
                "pool_size": 2,
                "pool_available": 1,
                "requests_waiting": 0,
                "ignored": "x",
                "pool_size_float": 1.5,
            }

    store._pool = _StatsPool()  # type: ignore[assignment]
    store._last_health_checkout_wait_ms = 12.5
    snap = store.pool_health_snapshot()
    assert snap["health_checkout_wait_ms"] == 12.5
    assert snap["pool_min"] == 1
    assert snap["pool_max"] == 4
    assert snap["pool_size"] == 2
    assert snap["pool_available"] == 1
    assert snap["requests_waiting"] == 0
    assert "ignored" not in snap
    assert "pool_size_float" not in snap


def test_pool_health_snapshot_non_dict_stats() -> None:
    store = _store(_Conn([]))

    class _WeirdPool:
        def get_stats(self) -> list[int]:
            return [1, 2, 3]

    store._pool = _WeirdPool()  # type: ignore[assignment]
    store._last_health_checkout_wait_ms = None
    assert store.pool_health_snapshot() == {"health_checkout_wait_ms": None}
