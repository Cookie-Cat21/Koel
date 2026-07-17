"""E4-C01: Storage unit tests with a mock pool (no Postgres)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from psycopg.errors import UniqueViolation

from chime.domain import AlertEvent, AlertType, Disclosure, PriceSnapshot, SectorSnapshot
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
async def test_health_check_records_real_pool_checkout_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks = iter([10.0, 10.125])
    monkeypatch.setattr("chime.storage.perf_counter", lambda: next(ticks))
    conn = _Conn([{"ok": 1}])
    store = _store(conn)

    assert await store.health_check() is True

    snapshot = store.pool_health_snapshot()
    assert snapshot["health_checkout_wait_ms"] == pytest.approx(125.0)


@pytest.mark.asyncio
async def test_upsert_stock_normalizes_symbol() -> None:
    conn = _Conn([None])
    store = _store(conn)
    await store.upsert_stock("jkh.n0000", "John Keells", "Conglomerates")
    assert "INSERT INTO stocks" in conn.sql[0]
    assert conn.params[0][0] == "JKH.N0000"


@pytest.mark.asyncio
async def test_insert_snapshot_returns_id() -> None:
    # one stocks upsert + one snapshots INSERT RETURNING (via persist_market_snapshots)
    conn = _Conn([None, [{"id": 42}]])
    store = _store(conn)
    out = await store.insert_snapshot(_snap())
    assert out.id == 42
    assert out.symbol == "JKH.N0000"
    assert len(conn.sql) == 2
    assert "INSERT INTO stocks" in conn.sql[0]
    assert "price_snapshots" in conn.sql[1]
    assert "RETURNING id" in conn.sql[1]


@pytest.mark.asyncio
async def test_persist_market_snapshots_empty_and_batch() -> None:
    store = _store(_Conn([]))
    assert await store.persist_market_snapshots([]) == []

    # Two round-trips total regardless of board size: stocks upsert + snapshots RETURNING.
    conn = _Conn([None, [{"id": 1}, {"id": 2}]])
    store = _store(conn)
    out = await store.persist_market_snapshots(
        [_snap(symbol="jkh.n0000"), _snap(symbol="comb.n0000", price=90.0)]
    )
    assert [s.id for s in out] == [1, 2]
    assert [s.symbol for s in out] == ["JKH.N0000", "COMB.N0000"]
    assert len(conn.sql) == 2
    assert sum(1 for s in conn.sql if "INSERT INTO stocks" in s) == 1
    assert sum(1 for s in conn.sql if "price_snapshots" in s) == 1
    assert "UNNEST" in conn.sql[0]
    assert "UNNEST" in conn.sql[1]
    assert "RETURNING id" in conn.sql[1]
    assert "VALUES (" not in conn.sql[0]
    assert "VALUES (" not in conn.sql[1]
    # Column-wise arrays (no dynamic VALUES concat).
    assert conn.params[0][0] == ["JKH.N0000", "COMB.N0000"]
    assert conn.params[0][1] == ["John Keells", "John Keells"]
    assert conn.params[1][0] == ["JKH.N0000", "COMB.N0000"]
    assert conn.params[1][1] == [100.0, 90.0]


@pytest.mark.asyncio
async def test_persist_market_snapshots_last_wins_dedupes_symbol() -> None:
    """Duplicate symbols in one board → one snapshot (last-wins), one stock row."""
    conn = _Conn([None, [{"id": 10}]])
    store = _store(conn)
    out = await store.persist_market_snapshots(
        [
            _snap(symbol="jkh.n0000", price=100.0, name="First"),
            _snap(symbol="JKH.N0000", price=101.0, name="Second"),
        ]
    )
    assert len(out) == 1
    assert out[0].id == 10
    assert out[0].symbol == "JKH.N0000"
    assert out[0].price == 101.0
    assert "UNNEST" in conn.sql[0] and "UNNEST" in conn.sql[1]
    # symbols, names, sectors, cse ids (cse_stock_id column landed later)
    assert conn.params[0] == (["JKH.N0000"], ["Second"], [None], [None])
    assert conn.params[1][0] == ["JKH.N0000"]
    assert conn.params[1][1] == [101.0]


@pytest.mark.asyncio
async def test_persist_market_snapshots_skips_blank_symbols() -> None:
    store = _store(_Conn([]))
    assert (
        await store.persist_market_snapshots(
            [_snap(symbol="  ", price=1.0), _snap(symbol="", price=2.0)]
        )
        == []
    )

    conn = _Conn([None, [{"id": 3}]])
    store = _store(conn)
    out = await store.persist_market_snapshots(
        [_snap(symbol="  ", price=1.0), _snap(symbol="COMB.N0000", price=90.0)]
    )
    assert len(out) == 1 and out[0].symbol == "COMB.N0000" and out[0].id == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
async def test_persist_market_snapshots_skips_nonfinite_prices(price: float) -> None:
    """Defense in depth: NaN/±Inf must not reach price_snapshots (storage.py:145)."""
    store = _store(_Conn([]))
    assert await store.persist_market_snapshots([_snap(symbol="BAD.N0000", price=price)]) == []

    conn = _Conn([None, [{"id": 4}]])
    store = _store(conn)
    out = await store.persist_market_snapshots(
        [
            _snap(symbol="BAD.N0000", price=price),
            _snap(symbol="COMB.N0000", price=90.0),
        ]
    )
    assert len(out) == 1 and out[0].symbol == "COMB.N0000" and out[0].id == 4
    assert conn.params[1][1] == [90.0]


@pytest.mark.asyncio
async def test_insert_snapshot_rejects_blank_symbol() -> None:
    store = _store(_Conn([]))
    with pytest.raises(ValueError, match="invalid snapshot symbol"):
        await store.insert_snapshot(_snap(symbol="   "))


@pytest.mark.asyncio
async def test_persist_market_snapshots_scales_to_board_size() -> None:
    """~300-symbol tradeSummary board stays two SQL round-trips."""
    n = 300
    board = [_snap(symbol=f"S{i:04d}.N0000", price=float(i)) for i in range(n)]
    ids = [{"id": i + 1} for i in range(n)]
    conn = _Conn([None, ids])
    store = _store(conn)
    out = await store.persist_market_snapshots(board)
    assert len(out) == n
    assert out[0].id == 1 and out[-1].id == n
    assert out[0].symbol == "S0000.N0000"
    assert len(conn.sql) == 2
    assert "UNNEST" in conn.sql[0] and "UNNEST" in conn.sql[1]
    assert len(conn.params[0][0]) == n
    assert len(conn.params[1][0]) == n
    assert len(conn.params[1][1]) == n


@pytest.mark.asyncio
async def test_delete_old_non_watchlist_snapshots_noop_when_days_le_zero() -> None:
    conn = _Conn([{"n": 99}])
    store = _store(conn)
    assert await store.delete_old_non_watchlist_snapshots(0) == 0
    assert await store.delete_old_non_watchlist_snapshots(-3) == 0
    assert conn.sql == []


@pytest.mark.asyncio
async def test_delete_old_non_watchlist_snapshots_sql_and_count() -> None:
    conn = _Conn([{"n": 42}])
    store = _store(conn)
    assert await store.delete_old_non_watchlist_snapshots(7) == 42
    assert len(conn.sql) == 1
    sql = conn.sql[0]
    assert "DELETE FROM price_snapshots" in sql
    assert "watchlist_items" in sql
    assert "NOT EXISTS" in sql
    assert "interval '1 day'" in sql
    assert "LIMIT %s" in sql
    assert conn.params[0] == (7, 5_000)


@pytest.mark.asyncio
async def test_delete_old_non_watchlist_snapshots_custom_limit() -> None:
    conn = _Conn([{"n": 3}])
    store = _store(conn)
    assert await store.delete_old_non_watchlist_snapshots(14, limit=100) == 3
    assert conn.params[0] == (14, 100)


@pytest.mark.asyncio
async def test_delete_old_non_watchlist_snapshots_null_row_returns_zero() -> None:
    conn = _Conn([None])
    store = _store(conn)
    assert await store.delete_old_non_watchlist_snapshots(1) == 0


def _sector(**kwargs: Any) -> SectorSnapshot:
    base = dict(
        sector_id=1,
        symbol="BFI.I0000",
        name="Banks Finance and Insurance",
        index_code="BFI",
        index_code_sp=None,
        index_name="Banks Finance and Insurance",
        index_value=100.0,
        change=1.0,
        change_pct=1.0,
        trade_today=10.0,
        volume_today=1000.0,
        turnover_today=1e5,
        previous_close=99.0,
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        cse_row_id=7,
    )
    base.update(kwargs)
    return SectorSnapshot(**base)


@pytest.mark.asyncio
async def test_persist_sectors_empty_blank_and_unnest() -> None:
    store = _store(_Conn([]))
    assert await store.persist_sectors([]) == []
    assert await store.persist_sectors([_sector(symbol="  ")]) == []

    conn = _Conn([None])
    store = _store(conn)
    out = await store.persist_sectors(
        [
            _sector(sector_id=1, symbol="bfi.i0000", name="First"),
            _sector(sector_id=1, symbol="BFI.I0000", name="Last", index_value=101.0),
            _sector(sector_id=2, symbol="  "),
            _sector(sector_id=3, symbol="CON.I0000", name="Construction"),
        ]
    )
    assert len(out) == 2
    assert out[0].sector_id == 1 and out[0].name == "Last" and out[0].index_value == 101.0
    assert out[1].sector_id == 3 and out[1].symbol == "CON.I0000"
    assert len(conn.sql) == 1
    assert "INSERT INTO sectors" in conn.sql[0]
    assert "UNNEST" in conn.sql[0]
    assert "%s::" in conn.sql[0]
    assert "VALUES (" not in conn.sql[0]
    assert conn.params[0][0] == [1, 3]
    assert conn.params[0][1] == ["BFI.I0000", "CON.I0000"]
    assert conn.params[0][2] == ["Last", "Construction"]
    assert conn.params[0][6] == [101.0, 100.0]


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
    # upsert_stock + insert disclosure (inserted=True) + briefs enqueue
    conn = _Conn([None, {"id": 7, "inserted": True}, None])
    store = _store(conn)
    out = await store.upsert_disclosure(disc)
    assert out.id == 7
    assert out.just_inserted is True
    assert any("disclosure_briefs" in s for s in conn.sql)

    conn2 = _Conn([None, {"id": 8, "inserted": False}])
    store2 = _store(conn2)
    again = await store2.insert_disclosure_if_new(disc)
    assert again is not None and again.id == 8
    assert again.just_inserted is False
    assert not any("disclosure_briefs" in s for s in conn2.sql)


@pytest.mark.asyncio
async def test_get_ready_filing_brief_by_disclosure_id() -> None:
    brief = "Company declared an interim dividend of 1.50 LKR."
    conn = _Conn([{"brief": brief}])
    store = _store(conn)
    assert await store.get_ready_filing_brief(disclosure_id=55) == brief
    assert "disclosure_briefs" in conn.sql[0]
    assert "status = 'ready'" in conn.sql[0]
    assert conn.params[0] == (55,)


@pytest.mark.asyncio
async def test_get_ready_filing_brief_by_external_id() -> None:
    brief = "Rights issue of 1:10 approved by the board."
    conn = _Conn([{"brief": brief}])
    store = _store(conn)
    out = await store.get_ready_filing_brief(
        external_id="25040",
        symbol="jkh.n0000",
    )
    assert out == brief
    assert "JOIN disclosures" in conn.sql[0]
    assert conn.params[0] == ("25040", "JKH.N0000")


@pytest.mark.asyncio
async def test_get_ready_filing_brief_missing_or_blank_returns_none() -> None:
    assert await _store(_Conn([None])).get_ready_filing_brief(disclosure_id=1) is None
    assert await _store(_Conn([{"brief": "   "}])).get_ready_filing_brief(disclosure_id=1) is None
    # No keys → no query
    conn = _Conn([{"brief": "x"}])
    assert await _store(conn).get_ready_filing_brief() is None
    assert conn.sql == []


@pytest.mark.asyncio
async def test_get_ready_filing_brief_fail_soft_on_db_error() -> None:
    conn = _Conn([RuntimeError("briefs table missing")])
    store = _store(conn)
    assert await store.get_ready_filing_brief(disclosure_id=9) is None




@pytest.mark.asyncio
async def test_get_latest_ready_brief_for_symbol() -> None:
    brief = "AGM scheduled for August."
    conn = _Conn(
        [
            {
                "brief": brief,
                "symbol": "JKH.N0000",
                "title": "AGM Notice",
                "url": "https://cdn.cse.lk/a.pdf",
                "external_id": "99",
                "disclosure_id": 7,
            }
        ]
    )
    store = _store(conn)
    out = await store.get_latest_ready_brief("jkh.n0000")
    assert out is not None
    assert out["brief"] == brief
    assert out["symbol"] == "JKH.N0000"
    assert out["title"] == "AGM Notice"
    assert "disclosure_briefs" in conn.sql[0]
    assert "status = 'ready'" in conn.sql[0]
    assert "ORDER BY d.published_at DESC" in conn.sql[0]
    assert conn.params[0] == ("JKH.N0000",)


@pytest.mark.asyncio
async def test_get_latest_ready_brief_none_or_fail_soft() -> None:
    assert await _store(_Conn([None])).get_latest_ready_brief("JKH.N0000") is None
    assert await _store(_Conn([{"brief": "  "}])).get_latest_ready_brief("JKH.N0000") is None
    assert await _store(_Conn([])).get_latest_ready_brief("") is None
    conn = _Conn([RuntimeError("db down")])
    assert await _store(conn).get_latest_ready_brief("JKH.N0000") is None

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
    assert (
        await _store(_Conn([[{"id": 1}, {"id": 2}]])).deactivate_rules_for_symbol(3, "jkh.n0000")
        == 2
    )


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


@pytest.mark.asyncio
async def test_create_alert_rule_disclosure_with_category() -> None:
    inserted = {
        "id": 12,
        "user_id": 3,
        "symbol": "JKH.N0000",
        "type": "disclosure",
        "threshold": None,
        "category": "Financial",
        "active": True,
        "armed": True,
        "created_at": "2026-07-11T06:00:00+00:00",
    }
    conn = _Conn([None, None, None, None, inserted, {"telegram_id": 1001}])
    store = _store(conn)
    rule = await store.create_alert_rule(
        3, "JKH.N0000", AlertType.DISCLOSURE, None, category="Financial"
    )
    assert rule.id == 12
    assert rule.category == "Financial"
    # Baseline watermark for evaluate_disclosure_rules — must survive RETURNING.
    assert rule.created_at == datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC)
    insert_sql = [s for s in conn.sql if "INSERT INTO alert_rules" in s][0]
    assert "category" in insert_sql
    assert "created_at" in insert_sql
    assert conn.params[-2][4] == "Financial" or any(
        isinstance(p, tuple) and len(p) >= 5 and p[4] == "Financial" for p in conn.params
    )


def test_row_to_rule_strips_category() -> None:
    disc_rule = _row_to_rule(
        {
            "id": 2,
            "user_id": 2,
            "telegram_id": 3,
            "symbol": "JKH.N0000",
            "type": "disclosure",
            "threshold": None,
            "category": "  Dividend  ",
            "active": True,
            "created_at": "2026-07-11T06:00:00+00:00",
        }
    )
    assert disc_rule.category == "Dividend"
