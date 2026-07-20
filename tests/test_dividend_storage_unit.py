"""Unit coverage for dividend_events storage paths (mock pool, no Postgres)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from tests.test_storage_unit import _Conn, _store


def _div_row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 11,
        "symbol": "JKH.N0000",
        "disclosure_id": 55,
        "d_ann": date(2026, 7, 10),
        "d_xd": date(2026, 7, 24),
        "d_pay": date(2026, 8, 1),
        "dps": 2.0,
        "kind": "interim",
        "fy": "2025/2026",
        "dates_tbd": False,
        "title": "Interim Dividend",
        "source": "cse_disclosure",
        "raw_hash": "abc123",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_upsert_dividend_skips_non_dividend() -> None:
    store = _store(_Conn([]))
    out = await store.upsert_dividend_event_from_disclosure(
        symbol="JKH.N0000",
        disclosure_id=1,
        title="AGM Notice",
        category="Meeting",
    )
    assert out is None


@pytest.mark.asyncio
async def test_upsert_dividend_skips_empty_hints() -> None:
    store = _store(_Conn([]))
    out = await store.upsert_dividend_event_from_disclosure(
        symbol="JKH.N0000",
        disclosure_id=1,
        title="Cash Dividend",
        category="Dividend",
        brief=None,
    )
    assert out is None


@pytest.mark.asyncio
async def test_upsert_dividend_with_disclosure_id() -> None:
    conn = _Conn([_div_row()])
    store = _store(conn)
    out = await store.upsert_dividend_event_from_disclosure(
        symbol="JKH.N0000",
        disclosure_id=55,
        title="Interim Dividend — Rs. 2.00 per share",
        category="Cash Dividend",
        brief="XD: - 24.Jul.2026 Payment: - 01.Aug.2026",
        published_at=datetime(2026, 7, 10, 4, 0, 0, tzinfo=UTC),
    )
    assert out is not None
    assert out.id == 11
    assert out.symbol == "JKH.N0000"
    assert out.dps == 2.0
    assert out.d_xd == date(2026, 7, 24)
    assert "INSERT INTO dividend_events" in conn.sql[0]
    assert "ON CONFLICT (disclosure_id)" in conn.sql[0]


@pytest.mark.asyncio
async def test_upsert_dividend_without_disclosure_requires_xd() -> None:
    store = _store(_Conn([]))
    out = await store.upsert_dividend_event_from_disclosure(
        symbol="JKH.N0000",
        disclosure_id=None,
        title="Cash Dividend (DATES TO BE NOTIFIED)",
        category="Dividend",
    )
    assert out is None


@pytest.mark.asyncio
async def test_upsert_dividend_null_disclosure_with_xd() -> None:
    conn = _Conn([_div_row(disclosure_id=None)])
    store = _store(conn)
    out = await store.upsert_dividend_event_from_disclosure(
        symbol="JKH.N0000",
        disclosure_id=None,
        title="Final Dividend Rs. 1.50 per share XD: - 01.Aug.2026",
        category="Cash Dividend",
    )
    assert out is not None
    assert out.disclosure_id is None
    assert "disclosure_id IS NULL" in conn.sql[0]


@pytest.mark.asyncio
async def test_list_upcoming_dividend_events_all_and_symbols() -> None:
    conn = _Conn(
        [
            [_div_row()],
            [_div_row(id=12, symbol="COMB.N0000")],
        ]
    )
    store = _store(conn)
    all_rows = await store.list_upcoming_dividend_events(horizon_days=14, limit=10)
    assert len(all_rows) == 1
    assert all_rows[0].symbol == "JKH.N0000"

    filtered = await store.list_upcoming_dividend_events(
        symbols=["COMB.N0000"],
        horizon_days=14,
        limit=10,
    )
    assert len(filtered) == 1
    assert filtered[0].symbol == "COMB.N0000"

    # Blank tokens only → early return, no SQL.
    empty = await store.list_upcoming_dividend_events(symbols=[""], horizon_days=7)
    assert empty == []
    assert len(conn.sql) == 2


@pytest.mark.asyncio
async def test_list_upcoming_skips_bad_rows() -> None:
    conn = _Conn([[{"id": "bad", "symbol": "X"}, _div_row()]])
    store = _store(conn)
    rows = await store.list_upcoming_dividend_events()
    assert len(rows) == 1
    assert rows[0].id == 11


@pytest.mark.asyncio
async def test_list_dividend_events_for_symbol() -> None:
    conn = _Conn([[_div_row(), _div_row(id=12, d_xd=date(2025, 1, 1))]])
    store = _store(conn)
    rows = await store.list_dividend_events_for_symbol("JKH.N0000", limit=40)
    assert len(rows) == 2
    assert "WHERE symbol = %s" in conn.sql[0]
    assert conn.params[0] == ("JKH.N0000", 40)


@pytest.mark.asyncio
async def test_sync_dividend_events_from_recent_disclosures() -> None:
    disc_rows = [
        {
            "id": 55,
            "symbol": "JKH.N0000",
            "title": "Interim Dividend — Rs. 2.00 per share XD: - 24.Jul.2026",
            "category": "Cash Dividend",
            "published_at": datetime(2026, 7, 10, 4, 0, 0, tzinfo=UTC),
            "brief": "Payment: - 01.Aug.2026",
            "brief_status": "ready",
        },
        {
            "id": 56,
            "symbol": "COMB.N0000",
            "title": "AGM",
            "category": "Meeting",
            "published_at": datetime(2026, 7, 9, 4, 0, 0, tzinfo=UTC),
            "brief": None,
            "brief_status": None,
        },
    ]
    # sync SELECT → upsert INSERT RETURNING for first row; second skips early
    conn = _Conn([disc_rows, _div_row()])
    store = _store(conn)
    n = await store.sync_dividend_events_from_recent_disclosures(limit=50)
    assert n == 1
    assert any("FROM disclosures" in s for s in conn.sql)
