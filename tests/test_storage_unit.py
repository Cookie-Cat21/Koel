"""E4-C01: Storage unit tests with a mock pool (no Postgres)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from psycopg.errors import UniqueViolation

from chime.domain import AlertEvent, AlertType, Disclosure, PriceSnapshot
from chime.storage import Storage, _row_to_rule, _row_to_snapshot


class _Cursor:
    def __init__(self, *, one: Any = None, many: list[Any] | None = None) -> None:
        self._one = one
        self._many = many or []

    async def fetchone(self) -> Any:
        return self._one

    async def fetchall(self) -> list[Any]:
        return list(self._many)


class _Conn:
    """Minimal async connection: queued execute results + optional transaction."""

    def __init__(self, results: list[Any] | None = None) -> None:
        self._results = list(results or [])
        self.sql: list[str] = []
        self.params: list[Any] = []

    async def execute(self, sql: str, params: Any = None) -> _Cursor:
        self.sql.append(sql)
        self.params.append(params)
        if not self._results:
            return _Cursor()
        nxt = self._results.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        if isinstance(nxt, _Cursor):
            return nxt
        if isinstance(nxt, list):
            return _Cursor(many=nxt)
        return _Cursor(one=nxt)

    @asynccontextmanager
    async def transaction(self) -> Any:
        yield


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn
        self.opened = False
        self.closed = False

    async def open(self) -> None:
        self.opened = True

    async def wait(self) -> None:
        return None

    async def close(self) -> None:
        self.closed = True

    @asynccontextmanager
    async def connection(self) -> Any:
        yield self._conn


def _store(conn: _Conn) -> Storage:
    store = Storage("postgresql://unused", min_size=1, max_size=2)
    store._pool = _Pool(conn)  # type: ignore[assignment]
    return store


def _snap(**kwargs: Any) -> PriceSnapshot:
    base = dict(
        symbol="JKH.N0000",
        price=100.0,
        change=1.0,
        change_pct=1.0,
        previous_close=99.0,
        volume=1000.0,
        trade_count=10.0,
        turnover=1e5,
        high=101.0,
        low=99.0,
        open=99.5,
        market_cap=1e9,
        name="John Keells",
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    )
    base.update(kwargs)
    return PriceSnapshot(**base)


@pytest.mark.asyncio
async def test_open_close_and_health_check() -> None:
    conn = _Conn([{"ok": 1}])
    store = _store(conn)
    await store.open()
    assert store._pool.opened is True  # type: ignore[attr-defined]
    assert await store.health_check() is True
    await store.close()
    assert store._pool.closed is True  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_upsert_stock_normalizes_symbol() -> None:
    conn = _Conn([None])
    store = _store(conn)
    await store.upsert_stock("jkh.n0000", "John Keells", "Conglomerates")
    assert "INSERT INTO stocks" in conn.sql[0]
    assert conn.params[0][0] == "JKH.N0000"


@pytest.mark.asyncio
async def test_insert_snapshot_returns_id() -> None:
    # upsert_stock execute + insert RETURNING
    conn = _Conn([None, {"id": 42}])
    store = _store(conn)
    out = await store.insert_snapshot(_snap())
    assert out.id == 42
    assert any("price_snapshots" in s for s in conn.sql)


@pytest.mark.asyncio
async def test_latest_and_previous_snapshot() -> None:
    row = {
        "id": 5,
        "symbol": "JKH.N0000",
        "price": 100.0,
        "previous_close": 99.0,
        "change": 1.0,
        "change_pct": 1.0,
        "volume": 10.0,
        "trade_count": None,
        "turnover": None,
        "high": None,
        "low": None,
        "open": None,
        "market_cap": None,
        "ts": datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    }
    conn = _Conn([row, None])
    store = _store(conn)
    latest = await store.latest_snapshot("jkh.n0000")
    assert latest is not None and latest.id == 5
    assert await store.previous_snapshot("JKH.N0000", before_id=5) is None


@pytest.mark.asyncio
async def test_get_previous_state_with_and_without_prev() -> None:
    prev_row = {
        "id": 4,
        "symbol": "JKH.N0000",
        "price": 95.0,
        "previous_close": None,
        "change": None,
        "change_pct": 2.5,
        "volume": None,
        "trade_count": None,
        "turnover": None,
        "high": None,
        "low": None,
        "open": None,
        "market_cap": None,
        "ts": datetime(2026, 7, 11, 5, 0, 0, tzinfo=UTC),
    }
    # previous_snapshot + move keys query
    conn = _Conn([prev_row, [{"event_key": "move:2026-07-11"}]])
    store = _store(conn)
    state = await store.get_previous_state("JKH.N0000", before_id=9)
    assert state.price == 95.0
    assert state.change_pct == 2.5
    assert "move:2026-07-11" in state.move_fired_keys

    conn2 = _Conn([None, []])
    store2 = _store(conn2)
    empty = await store2.get_previous_state("JKH.N0000", before_id=1)
    assert empty.price is None


@pytest.mark.asyncio
async def test_upsert_disclosure_and_compat_wrapper() -> None:
    disc = Disclosure(
        external_id="ann-1",
        symbol="JKH.N0000",
        title="Results",
        url="https://www.cse.lk/a/1",
        published_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        seen_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        company_name="John Keells",
    )
    # upsert_stock + insert disclosure
    conn = _Conn([None, {"id": 7}])
    store = _store(conn)
    out = await store.upsert_disclosure(disc)
    assert out.id == 7

    conn2 = _Conn([None, {"id": 8}])
    store2 = _store(conn2)
    again = await store2.insert_disclosure_if_new(disc)
    assert again is not None and again.id == 8


@pytest.mark.asyncio
async def test_ensure_user_add_remove_watch_list() -> None:
    conn = _Conn([{"id": 3}, None, {"symbol": "JKH.N0000"}, [{"symbol": "JKH.N0000"}]])
    store = _store(conn)
    uid = await store.ensure_user(1001)
    assert uid == 3
    # add_watch: upsert_stock + insert
    conn2 = _Conn([None, None])
    store2 = _store(conn2)
    await store2.add_watch(3, "jkh.n0000")
    assert conn2.params[0][0] == "JKH.N0000"

    conn3 = _Conn([{"symbol": "JKH.N0000"}])
    store3 = _store(conn3)
    assert await store3.remove_watch(3, "JKH.N0000") is True

    conn4 = _Conn([None])
    store4 = _store(conn4)
    assert await store4.remove_watch(3, "MISSING") is False

    conn5 = _Conn([[{"symbol": "COMB.N0000"}, {"symbol": "JKH.N0000"}]])
    store5 = _store(conn5)
    assert await store5.list_watchlist(3) == ["COMB.N0000", "JKH.N0000"]

    conn6 = _Conn([[{"symbol": "JKH.N0000"}]])
    store6 = _store(conn6)
    assert await store6.watched_symbols() == ["JKH.N0000"]


@pytest.mark.asyncio
async def test_unwatch_symbol_returns_removed_and_count() -> None:
    conn = _Conn([{"symbol": "JKH.N0000"}, [{"id": 1}, {"id": 2}]])
    store = _store(conn)
    removed, n = await store.unwatch_symbol(3, "jkh.n0000")
    assert removed is True and n == 2

    conn2 = _Conn([None, []])
    store2 = _store(conn2)
    removed2, n2 = await store2.unwatch_symbol(3, "JKH.N0000")
    assert removed2 is False and n2 == 0


@pytest.mark.asyncio
async def test_create_alert_rule_existing_and_insert() -> None:
    existing = {
        "id": 9,
        "user_id": 3,
        "telegram_id": 1001,
        "symbol": "JKH.N0000",
        "type": "price_above",
        "threshold": 100.0,
        "active": True,
        "armed": True,
        "created_at": datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    }
    # upsert_stock, add_watch (upsert+insert), _fetch_active_rule → existing
    conn = _Conn([None, None, None, existing])
    store = _store(conn)
    rule = await store.create_alert_rule(3, "JKH.N0000", AlertType.PRICE_ABOVE, 100.0)
    assert rule.id == 9

    inserted = {
        "id": 10,
        "user_id": 3,
        "symbol": "JKH.N0000",
        "type": "price_below",
        "threshold": 50.0,
        "active": True,
        "armed": True,
        "created_at": "2026-07-11T06:00:00+00:00",
    }
    # upsert, add_watch x2 executes, fetch None, insert, user telegram
    conn2 = _Conn([None, None, None, None, inserted, {"telegram_id": 1001}])
    store2 = _store(conn2)
    rule2 = await store2.create_alert_rule(3, "JKH.N0000", AlertType.PRICE_BELOW, 50.0)
    assert rule2.id == 10 and rule2.telegram_id == 1001


@pytest.mark.asyncio
async def test_create_alert_rule_unique_violation_races_to_existing() -> None:
    raced = {
        "id": 11,
        "user_id": 3,
        "telegram_id": 1001,
        "symbol": "JKH.N0000",
        "type": "daily_move",
        "threshold": 5.0,
        "active": True,
        "armed": True,
        "created_at": datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    }
    conn = _Conn()
    conn.rollback = AsyncMock()  # type: ignore[attr-defined]
    # upsert, add_watch x2, fetch None, UniqueViolation, fetch raced
    conn._results = [None, None, None, None, UniqueViolation("dup"), raced]
    store = _store(conn)
    rule = await store.create_alert_rule(3, "JKH.N0000", AlertType.DAILY_MOVE, 5.0)
    assert rule.id == 11
    conn.rollback.assert_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_list_alerts_and_active_rules() -> None:
    row = {
        "id": 1,
        "user_id": 3,
        "telegram_id": 1001,
        "symbol": "JKH.N0000",
        "type": "disclosure",
        "threshold": None,
        "active": True,
        "armed": True,
        "created_at": datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    }
    conn = _Conn([[row]])
    store = _store(conn)
    rules = await store.list_alerts(3)
    assert len(rules) == 1 and rules[0].type == AlertType.DISCLOSURE

    assert await _store(_Conn([])).active_rules_for_symbols([]) == []
    conn2 = _Conn([[row]])
    store2 = _store(conn2)
    assert len(await store2.active_rules_for_symbols(["JKH.N0000"])) == 1


@pytest.mark.asyncio
async def test_set_armed_deactivate_paths() -> None:
    store = _store(_Conn([None]))
    await store.set_rule_armed(1, False)

    assert await _store(_Conn([{"id": 1}])).deactivate_alert(3, 1) is True
    assert await _store(_Conn([None])).deactivate_alert(3, 99) is False
    assert await _store(_Conn([[{"id": 1}, {"id": 2}]])).deactivate_rules_for_symbol(
        3, "jkh.n0000"
    ) == 2


@pytest.mark.asyncio
async def test_advisory_lock_hold_and_unlock() -> None:
    conn = _Conn([{"locked": True}, None])
    store = _store(conn)
    assert await store.try_advisory_lock(99) is True
    assert store._lock_conn is conn
    # second acquire while held
    assert await store.try_advisory_lock(99) is False
    await store.advisory_unlock()
    assert store._lock_conn is None

    conn2 = _Conn([{"locked": False}])
    store2 = _store(conn2)
    assert await store2.try_advisory_lock() is False
    assert store2._lock_conn is None


@pytest.mark.asyncio
async def test_advisory_lock_execute_error_releases_cm() -> None:
    conn = _Conn([RuntimeError("db down")])
    store = _store(conn)
    with pytest.raises(RuntimeError, match="db down"):
        await store.try_advisory_lock()
    assert store._lock_conn is None


@pytest.mark.asyncio
async def test_claim_alert_and_claim_and_disarm() -> None:
    event = AlertEvent(
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
    claim_conn = _Conn([{"id": 50}])
    assert await _store(claim_conn).claim_alert(event, "hi", lease_seconds=90) == 50
    assert "delivery_lease_until" in claim_conn.sql[0]
    assert claim_conn.params[0] == (1, 5, "above:100", "hi", 90)

    assert await _store(_Conn([None])).claim_alert(event, "hi") is None

    conn = _Conn([{"id": 51}, None])
    store = _store(conn)
    assert await store.claim_and_disarm(event, "hi", lease_seconds=60) == 51
    assert "delivery_lease_until" in conn.sql[0]
    assert conn.params[0][-1] == 60
    assert any("armed" in s.lower() for s in conn.sql)

    assert await _store(_Conn([None])).claim_and_disarm(event, "hi") is None


@pytest.mark.asyncio
async def test_claim_alert_lease_excludes_from_claim_unsent_batch() -> None:
    """After claim, claim_unsent_batch SQL filters active leases; cleared on delivery_ok."""
    event = AlertEvent(
        rule_id=1,
        user_id=3,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="cross",
        current_price=101.0,
        event_key="lease:above:100",
        snapshot_id=5,
    )

    # claim_alert INSERT must set delivery_lease_until (blocks concurrent unsent claim).
    claim_conn = _Conn([{"id": 77}])
    assert await _store(claim_conn).claim_alert(event, "sending…") == 77
    assert "delivery_lease_until" in claim_conn.sql[0]
    assert "now() + (%s * interval '1 second')" in claim_conn.sql[0]
    assert claim_conn.params[0][-1] == 120

    # claim_unsent_batch predicate excludes non-expired leases (same as after claim).
    batch_conn = _Conn([[]])
    assert await _store(batch_conn).claim_unsent_batch(limit=10, lease_seconds=30) == []
    claim_sql = batch_conn.sql[0]
    assert "delivery_lease_until IS NULL" in claim_sql
    assert "delivery_lease_until < now()" in claim_sql

    # delivery_attempted_ok clears lease so only the durable flag keeps the row out.
    ok_conn = _Conn([None])
    await _store(ok_conn).mark_delivery_attempted_ok(77)
    assert "delivery_attempted_ok = TRUE" in ok_conn.sql[0]
    assert "delivery_lease_until = NULL" in ok_conn.sql[0]


@pytest.mark.asyncio
async def test_mark_sent_attempt_dead_letter_unsent_claim_batch() -> None:
    ok_conn = _Conn([None])
    await _store(ok_conn).mark_delivery_attempted_ok(1)
    assert "delivery_lease_until = NULL" in ok_conn.sql[0]
    await _store(_Conn([None])).mark_alert_sent(1)
    assert await _store(_Conn([{"attempt_count": 3}])).mark_alert_attempt(1) == 3
    await _store(_Conn([None])).dead_letter(1)

    rows = [
        {
            "id": 1,
            "rule_id": 2,
            "message_text": "x",
            "attempt_count": 0,
            "telegram_id": 1001,
        }
    ]
    assert await _store(_Conn([rows])).unsent_alerts(limit=10) == rows
    assert await _store(_Conn([rows])).claim_unsent_batch(limit=1, lease_seconds=30) == rows


def test_row_helpers_parse_iso_created() -> None:
    snap = _row_to_snapshot(
        {
            "id": 1,
            "symbol": "JKH.N0000",
            "price": "12.5",
            "ts": "2026-07-11T06:00:00+00:00",
        }
    )
    assert snap.price == 12.5
    rule = _row_to_rule(
        {
            "id": 1,
            "user_id": 2,
            "telegram_id": 3,
            "symbol": "JKH.N0000",
            "type": "price_above",
            "threshold": 1.0,
            "active": True,
            "created_at": "2026-07-11T06:00:00+00:00",
        }
    )
    assert rule.created_at is not None
