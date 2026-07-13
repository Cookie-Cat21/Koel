"""Wave74: medium+ bugs — rule.type getattr + stock-name map + board guards.

1. Poller tick / disclosure filter / ``_ready_filing_brief_for`` must
   ``getattr(..., "value", ...)`` so non-enum types cannot abort the tick.
2. ``list_stock_names`` must isinstance-guard PG symbol/name (no ``str()``
   soft-accept of ints/None into the bulk disclosure name map).
3. ``market_persist_failed`` gap reporting must isinstance-guard snapshot
   symbols before ``.strip``.
4. Board normalize / persist / CSE fetch / ``get_previous_state`` /
   ``CSEClient`` base_url must fail-closed on non-string inputs (cov lock).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from chime.adapters.cse import (
    AnnouncementRow,
    CSEClient,
    SectorRow,
    SymbolInfo,
    TradeSummaryRow,
    announcement_to_disclosure,
    sector_row_to_snapshot,
    symbol_info_to_snapshot,
    trade_row_to_snapshot,
)
from chime.domain import AlertEvent, AlertRule, AlertType, PriceSnapshot, SectorSnapshot
from chime.poller import Poller
from chime.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_ready_filing_brief_non_enum_type_fail_closed() -> None:
    poller = object.__new__(Poller)
    poller.storage = SimpleNamespace(
        get_ready_filing_brief=AsyncMock(return_value="brief"),
    )
    event = AlertEvent.model_construct(
        rule_id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=123,  # type: ignore[arg-type]
        trigger="x",
        event_key="disclosure:1:ext",
    )
    assert await poller._ready_filing_brief_for(event) is None
    poller.storage.get_ready_filing_brief.assert_not_awaited()

    ok = AlertEvent.model_construct(
        rule_id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        trigger="x",
        event_key="disclosure:1:ext-9",
        disclosure_id=3,
    )
    assert await poller._ready_filing_brief_for(ok) == "brief"

    src = (ROOT / "chime" / "poller.py").read_text(encoding="utf-8")
    ready = src.split("async def _ready_filing_brief_for")[1].split(
        "async def _claim_only"
    )[0]
    assert 'getattr(event.type, "value", event.type)' in ready
    tick = src.split("needs_disclosure = any")[1].split("ok = True")[0]
    assert 'getattr(r.type, "value", r.type)' in tick
    disc = src.split("async def _poll_disclosures")[1].split(
        "disclosure_symbols = sorted"
    )[0]
    assert 'getattr(r.type, "value", r.type)' in disc


@pytest.mark.asyncio
async def test_list_stock_names_rejects_non_string_rows() -> None:
    from contextlib import asynccontextmanager
    from typing import Any

    class _Cursor:
        async def fetchall(self) -> list[dict[str, Any]]:
            return [
                {"symbol": 123, "name": "Acme"},
                {"symbol": "BAD.N0000", "name": None},
                {"symbol": "JKH.N0000", "name": "John Keells"},
                {"symbol": True, "name": "Nope"},
            ]

    class _Conn:
        async def execute(self, *_a: object, **_k: object) -> _Cursor:
            return _Cursor()

    class _Pool:
        @asynccontextmanager
        async def connection(self) -> Any:
            yield _Conn()

    store = Storage("postgresql://unused", min_size=1, max_size=2)
    store._pool = _Pool()  # type: ignore[assignment]
    assert await store.list_stock_names() == [("JKH.N0000", "John Keells")]

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def list_stock_names")[1].split("async def insert_snapshot")[
        0
    ]
    assert "isinstance(raw_sym, str)" in chunk
    assert "isinstance(raw_name, str)" in chunk
    assert 'str(row["symbol"])' not in chunk


def test_market_persist_failed_present_set_isinstance_pin() -> None:
    src = (ROOT / "chime" / "poller.py").read_text(encoding="utf-8")
    chunk = src.split("market_persist_failed")[1].split("watched_missing")[0]
    assert "isinstance(s.symbol, str)" in chunk


def test_rule_type_getattr_pins_cover_disclosure_filter() -> None:
    good = AlertRule.model_construct(
        id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        active=True,
        armed=True,
    )
    bad = AlertRule.model_construct(
        id=2,
        user_id=1,
        telegram_id=1,
        symbol="COMB.N0000",
        type=99,  # type: ignore[arg-type]
        threshold=None,
        active=True,
        armed=True,
    )
    rules = [good, bad]
    disclosure_rules = [
        r for r in rules if getattr(r.type, "value", r.type) == "disclosure"
    ]
    assert disclosure_rules == [good]
    with pytest.raises(AttributeError):
        _ = bad.type.value  # type: ignore[union-attr]


def test_adapter_normalize_rejects_non_string_and_blank() -> None:
    assert (
        trade_row_to_snapshot(
            TradeSummaryRow.model_construct(symbol=123, price=10.0, name="X")
        )
        is None
    )
    assert (
        trade_row_to_snapshot(
            TradeSummaryRow.model_construct(symbol="  ", price=10.0, name="X")
        )
        is None
    )

    assert (
        sector_row_to_snapshot(
            SectorRow.model_construct(sectorId=1, symbol=5, name="Energy")
        )
        is None
    )
    assert (
        sector_row_to_snapshot(
            SectorRow.model_construct(sectorId=1, symbol="egy", name=9)
        )
        is None
    )
    assert (
        sector_row_to_snapshot(
            SectorRow.model_construct(sectorId=1, symbol="  ", name="Energy")
        )
        is None
    )
    assert (
        sector_row_to_snapshot(
            SectorRow.model_construct(sectorId=1, symbol="egy", name="  ")
        )
        is None
    )

    assert (
        symbol_info_to_snapshot(
            SymbolInfo.model_construct(symbol=None, lastTradedPrice=10.0)
        )
        is None
    )
    assert (
        symbol_info_to_snapshot(
            SymbolInfo.model_construct(symbol="  ", lastTradedPrice=10.0)
        )
        is None
    )

    ann = AnnouncementRow.model_construct(
        announcementId=1,
        createdDate=1_700_000_000_000,
        announcementCategory="Fin",
    )
    assert announcement_to_disclosure(ann, symbol=123) is None  # type: ignore[arg-type]
    assert announcement_to_disclosure(ann, symbol="  ") is None
    ok = announcement_to_disclosure(ann, symbol="jkh.n0000")
    assert ok is not None and ok.symbol == "JKH.N0000"


@pytest.mark.asyncio
async def test_cse_fetch_and_base_url_fail_closed() -> None:
    client = CSEClient(base_url=123, timeout=1.0, client=AsyncMock())  # type: ignore[arg-type]
    assert client.base_url == "https://www.cse.lk/api"
    blank = CSEClient(base_url="  ", timeout=1.0, client=AsyncMock())
    assert blank.base_url == "https://www.cse.lk/api"

    assert await client.fetch_company_info(123) is None  # type: ignore[arg-type]
    assert await client.fetch_company_info("") is None
    assert await client.fetch_company_info("  ") is None
    assert await client.fetch_announcements_for_symbol(True) == []  # type: ignore[arg-type]
    assert await client.fetch_announcements_for_symbol("  ") == []
    assert await client.fetch_legacy_announcements(None) == []  # type: ignore[arg-type]
    assert await client.fetch_legacy_announcements("") == []


@pytest.mark.asyncio
async def test_persist_and_previous_state_skip_non_string_symbols() -> None:
    from contextlib import asynccontextmanager
    from typing import Any

    class _Cursor:
        async def fetchall(self) -> list[Any]:
            return []

        async def fetchone(self) -> Any:
            return None

    class _Conn:
        def __init__(self) -> None:
            self.sql: list[str] = []

        async def execute(self, sql: str, params: Any = None) -> _Cursor:
            self.sql.append(sql)
            return _Cursor()

        @asynccontextmanager
        async def transaction(self) -> Any:
            yield

    class _Pool:
        def __init__(self, conn: _Conn) -> None:
            self._conn = conn

        @asynccontextmanager
        async def connection(self) -> Any:
            yield self._conn

    conn = _Conn()
    store = Storage("postgresql://unused", min_size=1, max_size=2)
    store._pool = _Pool(conn)  # type: ignore[assignment]

    snaps = [
        PriceSnapshot.model_construct(
            symbol=123,  # type: ignore[arg-type]
            price=10.0,
            ts=datetime.now(UTC),
        ),
        PriceSnapshot.model_construct(
            symbol="  ",
            price=10.0,
            ts=datetime.now(UTC),
        ),
    ]
    assert await store.persist_market_snapshots(snaps) == []
    assert conn.sql == []

    conn2 = _Conn()
    store2 = Storage("postgresql://unused", min_size=1, max_size=2)
    store2._pool = _Pool(conn2)  # type: ignore[assignment]
    sectors = [
        SectorSnapshot.model_construct(
            sector_id=1,
            symbol=99,  # type: ignore[arg-type]
            name="Energy",
            ts=datetime.now(UTC),
        ),
        SectorSnapshot.model_construct(
            sector_id=2,
            symbol="  ",
            name="Energy",
            ts=datetime.now(UTC),
        ),
    ]
    assert await store2.persist_sectors(sectors) == []
    assert conn2.sql == []

    prev = await store.get_previous_state(123, before_id=1)  # type: ignore[arg-type]
    assert prev.price is None and prev.move_fired_keys == set()
    prev2 = await store.get_previous_state("  ", before_id=1)
    assert prev2.price is None and prev2.move_fired_keys == set()

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    assert "isinstance(snap.symbol, str)" in src.split("async def persist_market_snapshots")[
        1
    ].split("async def delete_old_non_watchlist_snapshots")[0]
    assert "isinstance(sector.symbol, str)" in src.split("async def persist_sectors")[
        1
    ].split("async def ")[0]
    assert "isinstance(symbol, str)" in src.split("async def get_previous_state")[1].split(
        "async def "
    )[0]
