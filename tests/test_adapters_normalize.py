"""CSE adapter normalization helpers — no network."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from chime.adapters.cse import (
    ANNOUNCEMENTS_PAGE,
    AnnouncementRow,
    TradeSummaryRow,
    announcement_to_disclosure,
    trade_row_to_snapshot,
)

_COLOMBO = ZoneInfo("Asia/Colombo")


def test_trade_row_to_snapshot_maps_fields() -> None:
    row = TradeSummaryRow(
        symbol="jkh.n0000",
        name="John Keells",
        price=185.5,
        previousClose=180.0,
        change=5.5,
        percentageChange=3.06,
        sharevolume=12000,
        tradevolume=45,
        turnover=2_200_000,
        high=186.0,
        low=179.0,
        open=181.0,
        marketCap=1e11,
        lastTradedTime=1_720_000_000_000,
    )
    snap = trade_row_to_snapshot(row)
    assert snap.symbol == "JKH.N0000"
    assert snap.price == 185.5
    assert snap.previous_close == 180.0
    assert snap.change == 5.5
    assert snap.change_pct == 3.06
    assert snap.volume == 12000
    assert snap.trade_count == 45
    assert snap.turnover == 2_200_000
    assert snap.high == 186.0
    assert snap.low == 179.0
    assert snap.open == 181.0
    assert snap.market_cap == 1e11
    assert snap.name == "John Keells"
    assert snap.ts == datetime.fromtimestamp(1_720_000_000_000 / 1000.0, tz=UTC)


def test_trade_row_uses_now_when_no_last_traded_time() -> None:
    now = datetime(2026, 7, 11, 9, 0, 0, tzinfo=UTC)
    row = TradeSummaryRow(symbol="COMB.N0000", price=100.0)
    snap = trade_row_to_snapshot(row, now=now)
    assert snap.ts == now
    assert snap.symbol == "COMB.N0000"


def test_announcement_to_disclosure_builds_url_and_title() -> None:
    row = AnnouncementRow(
        announcementId=99,
        announcementCategory="Financial",
        remarks="Q1 Results",
        company="John Keells Holdings PLC",
        createdDate=1_720_000_000_000,
        symbol="JKH.N0000",
    )
    seen = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)
    disc = announcement_to_disclosure(row, symbol="jkh.n0000", seen_at=seen)
    assert disc is not None
    assert disc.external_id == "99"
    assert disc.symbol == "JKH.N0000"
    assert disc.title == "Financial: Q1 Results"
    assert disc.category == "Financial"
    assert disc.url == f"{ANNOUNCEMENTS_PAGE}#99"
    assert disc.company_name == "John Keells Holdings PLC"
    assert disc.seen_at == seen
    assert disc.published_at == datetime.fromtimestamp(1_720_000_000_000 / 1000.0, tz=UTC)


def test_announcement_falls_back_to_id_field() -> None:
    row = AnnouncementRow(id=55, announcementCategory="Other")
    disc = announcement_to_disclosure(row, symbol="COMB.N0000")
    assert disc is not None
    assert disc.external_id == "55"
    assert disc.title == "Other"
    assert disc.url == f"{ANNOUNCEMENTS_PAGE}#55"
    # Missing createdDate and dateOfAnnouncement → epoch (not "now")
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)


def test_announcement_uses_date_of_announcement_when_created_date_null() -> None:
    """WS-001: parse dateOfAnnouncement like '30 Jun 2026' as Colombo midnight → UTC."""
    row = AnnouncementRow(
        announcementId=42,
        announcementCategory="Financial",
        createdDate=None,
        dateOfAnnouncement="30 Jun 2026",
    )
    disc = announcement_to_disclosure(row, symbol="JKH.N0000")
    assert disc is not None
    # Asia/Colombo midnight (UTC+5:30) → 2026-06-29 18:30:00 UTC
    expected = datetime(2026, 6, 30, 0, 0, 0, tzinfo=_COLOMBO).astimezone(UTC)
    assert disc.published_at == expected
    assert disc.published_at == datetime(2026, 6, 29, 18, 30, 0, tzinfo=UTC)


def test_announcement_undated_still_epoch_fail_closed() -> None:
    """WS-001: neither createdDate nor parseable dateOfAnnouncement → epoch."""
    row = AnnouncementRow(
        announcementId=43,
        announcementCategory="Other",
        createdDate=None,
        dateOfAnnouncement=None,
    )
    disc = announcement_to_disclosure(row, symbol="COMB.N0000")
    assert disc is not None
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)


def test_announcement_unparseable_date_of_announcement_epoch() -> None:
    row = AnnouncementRow(
        announcementId=44,
        createdDate=None,
        dateOfAnnouncement="not-a-date",
    )
    disc = announcement_to_disclosure(row, symbol="COMB.N0000")
    assert disc is not None
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)


def test_announcement_with_no_ids_returns_none() -> None:
    row = AnnouncementRow(announcementCategory="X", remarks="y")
    assert announcement_to_disclosure(row, symbol="JKH.N0000") is None
