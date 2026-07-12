"""Optional DISCLOSURE_BULK_FEED path: approvedAnnouncement + name map."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from chime.adapters.cse import (
    AnnouncementRow,
    build_unique_company_name_map,
    normalize_company_name,
    resolve_announcement_symbol,
)
from chime.config import Settings
from chime.domain import AlertType, Disclosure, PriceSnapshot
from chime.poller import Poller
from tests.conftest import make_disclosure, make_rule


def test_normalize_company_name_collapses_whitespace() -> None:
    assert normalize_company_name("  CITRUS   LEISURE  PLC ") == "CITRUS LEISURE PLC"


def test_build_unique_company_name_map_drops_ambiguous() -> None:
    mapping = build_unique_company_name_map(
        [
            ("JKH.N0000", "JOHN KEELLS HOLDINGS PLC"),
            ("COMB.N0000", "COMMERCIAL BANK OF CEYLON PLC"),
            ("AAA.N0000", "SAME NAME PLC"),
            ("BBB.N0000", "same   name  plc"),
        ]
    )
    assert mapping["JOHN KEELLS HOLDINGS PLC"] == "JKH.N0000"
    assert mapping["COMMERCIAL BANK OF CEYLON PLC"] == "COMB.N0000"
    assert "SAME NAME PLC" not in mapping


def test_resolve_announcement_symbol_prefers_explicit_then_name() -> None:
    name_map = {"JOHN KEELLS HOLDINGS PLC": "JKH.N0000"}
    allowed = {"JKH.N0000", "COMB.N0000"}

    by_symbol = AnnouncementRow(
        announcementId=1,
        company="OTHER",
        symbol="JKH.N0000",
        createdDate=1_700_000_000_000,
    )
    assert (
        resolve_announcement_symbol(
            by_symbol, name_map=name_map, allowed_symbols=allowed
        )
        == "JKH.N0000"
    )

    by_name = AnnouncementRow(
        announcementId=2,
        company="JOHN KEELLS HOLDINGS PLC",
        symbol=None,
        createdDate=1_700_000_000_000,
    )
    assert (
        resolve_announcement_symbol(by_name, name_map=name_map, allowed_symbols=allowed)
        == "JKH.N0000"
    )

    unmatched = AnnouncementRow(
        announcementId=3,
        company="UNKNOWN CO PLC",
        symbol=None,
        createdDate=1_700_000_000_000,
    )
    assert (
        resolve_announcement_symbol(
            unmatched, name_map=name_map, allowed_symbols=allowed
        )
        is None
    )


def test_disclosure_bulk_feed_env_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("DATABASE_URL", "postgresql://chime:chime@localhost:5432/chime")
    monkeypatch.delenv("DISCLOSURE_BULK_FEED", raising=False)
    assert Settings.from_env().disclosure_bulk_feed is False
    monkeypatch.setenv("DISCLOSURE_BULK_FEED", "1")
    assert Settings.from_env().disclosure_bulk_feed is True
    monkeypatch.setenv("DISCLOSURE_BULK_FEED", "0")
    assert Settings.from_env().disclosure_bulk_feed is False


def _poller_mocks(
    *,
    disc_symbols: list[str],
    bulk_feed: bool,
) -> tuple[Poller, AsyncMock, AsyncMock]:
    rules = [
        make_rule(id=i + 1, symbol=sym, type=AlertType.DISCLOSURE, threshold=None)
        for i, sym in enumerate(disc_symbols)
    ]
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=list(disc_symbols))
    storage.active_rules_for_symbols = AsyncMock(return_value=rules)
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    from chime.domain import PreviousPriceState

    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    storage.upsert_disclosure = AsyncMock(
        side_effect=lambda d: d.model_copy(update={"id": 99})
    )
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.list_stock_names = AsyncMock(
        return_value=[
            ("JKH.N0000", "JOHN KEELLS HOLDINGS PLC"),
            ("COMB.N0000", "COMMERCIAL BANK OF CEYLON PLC"),
        ]
    )

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(symbol=s, price=20.0, ts=datetime.now(UTC)) for s in disc_symbols
        ]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])
    cse.fetch_approved_announcements = AsyncMock(return_value=[])

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        disclosure_bulk_feed=bulk_feed,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    return poller, storage, cse


@pytest.mark.asyncio
async def test_bulk_feed_off_uses_per_symbol_only() -> None:
    poller, _storage, cse = _poller_mocks(
        disc_symbols=["JKH.N0000", "COMB.N0000"], bulk_feed=False
    )
    await poller.run_once(force=True)
    cse.fetch_approved_announcements.assert_not_called()
    assert cse.fetch_announcements_for_symbol.await_count == 2


@pytest.mark.asyncio
async def test_bulk_feed_on_skips_per_symbol_when_names_map() -> None:
    poller, storage, cse = _poller_mocks(
        disc_symbols=["JKH.N0000", "COMB.N0000"], bulk_feed=True
    )
    row = AnnouncementRow(
        announcementId=38004,
        company="JOHN KEELLS HOLDINGS PLC",
        symbol=None,
        announcementCategory="CORPORATE DISCLOSURE",
        remarks="Board changes",
        createdDate=1_783_683_888_000,
    )
    cse.fetch_approved_announcements = AsyncMock(return_value=[row])

    await poller.run_once(force=True)

    cse.fetch_approved_announcements.assert_awaited_once()
    storage.list_stock_names.assert_awaited_once()
    cse.fetch_announcements_for_symbol.assert_not_called()
    upserted = [
        c.args[0]
        for c in storage.upsert_disclosure.await_args_list
        if isinstance(c.args[0], Disclosure)
    ]
    assert any(d.symbol == "JKH.N0000" and d.external_id == "38004" for d in upserted)


@pytest.mark.asyncio
async def test_bulk_feed_fails_soft_to_per_symbol() -> None:
    poller, _storage, cse = _poller_mocks(
        disc_symbols=["JKH.N0000"], bulk_feed=True
    )
    cse.fetch_approved_announcements = AsyncMock(side_effect=RuntimeError("bulk down"))
    cse.fetch_announcements_for_symbol = AsyncMock(
        return_value=[make_disclosure(external_id="fallback-1")]
    )

    await poller.run_once(force=True)

    cse.fetch_announcements_for_symbol.assert_awaited_once()
    assert poller.disclosure_poll_ok is True


@pytest.mark.asyncio
async def test_bulk_feed_partial_fallback_for_unmapped_symbol() -> None:
    """Named symbols use bulk; unnamed / ambiguous fall back per-symbol."""
    poller, storage, cse = _poller_mocks(
        disc_symbols=["JKH.N0000", "XYZ.N0000"], bulk_feed=True
    )
    storage.list_stock_names = AsyncMock(
        return_value=[
            ("JKH.N0000", "JOHN KEELLS HOLDINGS PLC"),
        ]
    )
    cse.fetch_approved_announcements = AsyncMock(return_value=[])
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    await poller.run_once(force=True)

    cse.fetch_announcements_for_symbol.assert_awaited_once()
    assert cse.fetch_announcements_for_symbol.await_args.args[0] == "XYZ.N0000"
