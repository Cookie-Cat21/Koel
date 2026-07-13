"""Wave95: medium storage list-method bugs pinned in owned paths."""

from __future__ import annotations

import pytest

from tests.test_storage_unit import _Conn, _store


@pytest.mark.asyncio
async def test_list_watchlist_rejects_poisoned_symbols() -> None:
    """Do not let legacy/poisoned watchlist rows reach Telegram rendering."""
    conn = _Conn(
        [
            [
                {"symbol": " jkh.n0000 "},
                {"symbol": 123},
                {"symbol": True},
                {"symbol": None},
                {"symbol": "   "},
                {"symbol": "COMB.N0000"},
            ]
        ]
    )
    store = _store(conn)

    assert await store.list_watchlist(7) == ["JKH.N0000", "COMB.N0000"]

    assert "btrim(symbol) <> ''" in conn.sql[0]


@pytest.mark.asyncio
async def test_watched_symbols_rejects_poisoned_and_case_duplicate_symbols() -> None:
    """Poller watch symbols must be canonical before CSE fetch/rule evaluation."""
    conn = _Conn(
        [
            [
                {"symbol": "jkh.n0000"},
                {"symbol": " JKH.N0000 "},
                {"symbol": ["COMB.N0000"]},
                {"symbol": False},
                {"symbol": ""},
                {"symbol": "COMB.N0000"},
            ]
        ]
    )
    store = _store(conn)

    assert await store.watched_symbols() == ["JKH.N0000", "COMB.N0000"]

    assert "SELECT DISTINCT symbol FROM watchlist_items" in conn.sql[0]
    assert "btrim(symbol) <> ''" in conn.sql[0]
