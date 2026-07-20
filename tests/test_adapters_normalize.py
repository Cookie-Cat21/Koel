"""CSE adapter normalization helpers — no network."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from structlog.testing import capture_logs

from koel.adapters.cse import (
    ANNOUNCEMENTS_PAGE,
    AnnouncementRow,
    CSEClient,
    TradeSummaryRow,
    _announcement_url,
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
    assert snap is not None
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
    assert snap is not None
    assert snap.ts == now
    assert snap.symbol == "COMB.N0000"


@pytest.mark.asyncio
async def test_fetch_trade_summary_empty_ok_log_includes_endpoint_name() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value={"reqTradeSummery": [], "serverTime": "2026-07-11T09:30:00+05:30"}
    )

    with capture_logs() as logs:
        assert await client.fetch_trade_summary() == []

    assert {
        "event": "cse_trade_summary_empty_ok",
        "log_level": "warning",
        "endpoint": "tradeSummary",
        "response_keys": ["reqTradeSummery", "serverTime"],
    } in logs


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
    assert disc.doa_display is None


def test_announcement_url_uses_public_announcements_anchor() -> None:
    url = _announcement_url("12345")

    assert url == f"{ANNOUNCEMENTS_PAGE}#12345"
    assert "/api/" not in url


def test_announcement_falls_back_to_id_field() -> None:
    row = AnnouncementRow(id=55, announcementCategory="Other")
    disc = announcement_to_disclosure(row, symbol="COMB.N0000")
    assert disc is not None
    assert disc.external_id == "55"
    assert disc.title == "Other"
    assert disc.url == f"{ANNOUNCEMENTS_PAGE}#55"
    # Missing createdDate and dateOfAnnouncement → epoch (not "now")
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert disc.doa_display is None


def test_announcement_doa_only_fail_closed_for_gating() -> None:
    """E2-C01: DOA alone must not set published_at — epoch fail-closed for alerts."""
    row = AnnouncementRow(
        announcementId=42,
        announcementCategory="Financial",
        createdDate=None,
        dateOfAnnouncement="30 Jun 2026",
    )
    disc = announcement_to_disclosure(row, symbol="JKH.N0000")
    assert disc is not None
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)
    # Asia/Colombo midnight (UTC+5:30) → 2026-06-29 18:30:00 UTC — display only
    expected_doa = datetime(2026, 6, 30, 0, 0, 0, tzinfo=_COLOMBO).astimezone(UTC)
    assert disc.doa_display == expected_doa
    assert disc.doa_display == datetime(2026, 6, 29, 18, 30, 0, tzinfo=UTC)


def test_announcement_doa_only_logs_display_catch_up_without_gating() -> None:
    """E12-C02: DOA-only rows are display catch-up, not alert gating inputs."""
    row = AnnouncementRow(
        announcementId=47,
        announcementCategory="Financial",
        createdDate=None,
        dateOfAnnouncement="10 Jul 2026",
    )

    with capture_logs() as caps:
        disc = announcement_to_disclosure(row, symbol="jkh.n0000")

    assert disc is not None
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert disc.doa_display == datetime(2026, 7, 9, 18, 30, 0, tzinfo=UTC)
    events = [event for event in caps if event.get("event") == "cse_disclosure_doa_display_only"]
    assert events == [
        {
            "event": "cse_disclosure_doa_display_only",
            "log_level": "warning",
            "external_id": "47",
            "symbol": "JKH.N0000",
            "date_of_announcement": "10 Jul 2026",
            "doa_display": "2026-07-09T18:30:00+00:00",
            "published_at": "1970-01-01T00:00:00+00:00",
        }
    ]


def test_announcement_doa_when_created_date_non_positive_fail_closed() -> None:
    """createdDate <= 0 is missing — DOA is display-only, published_at stays epoch."""
    row = AnnouncementRow(
        announcementId=45,
        announcementCategory="Financial",
        createdDate=0,
        dateOfAnnouncement="30 Jun 2026",
    )
    disc = announcement_to_disclosure(row, symbol="JKH.N0000")
    assert disc is not None
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert disc.doa_display == datetime(2026, 6, 29, 18, 30, 0, tzinfo=UTC)


def test_announcement_created_date_preferred_doa_still_parsed() -> None:
    """Valid createdDate gates; DOA still parsed into doa_display when present."""
    row = AnnouncementRow(
        announcementId=46,
        announcementCategory="Financial",
        createdDate=1_720_000_000_000,
        dateOfAnnouncement="30 Jun 2026",
    )
    disc = announcement_to_disclosure(row, symbol="JKH.N0000")
    assert disc is not None
    assert disc.published_at == datetime.fromtimestamp(1_720_000_000_000 / 1000.0, tz=UTC)
    assert disc.doa_display == datetime(2026, 6, 29, 18, 30, 0, tzinfo=UTC)


def test_announcement_undated_still_epoch_fail_closed() -> None:
    """Neither createdDate nor parseable dateOfAnnouncement → epoch."""
    row = AnnouncementRow(
        announcementId=43,
        announcementCategory="Other",
        createdDate=None,
        dateOfAnnouncement=None,
    )
    disc = announcement_to_disclosure(row, symbol="COMB.N0000")
    assert disc is not None
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert disc.doa_display is None


def test_announcement_unparseable_date_of_announcement_epoch() -> None:
    row = AnnouncementRow(
        announcementId=44,
        createdDate=None,
        dateOfAnnouncement="not-a-date",
    )
    disc = announcement_to_disclosure(row, symbol="COMB.N0000")
    assert disc is not None
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert disc.doa_display is None


def test_announcement_with_no_ids_returns_none() -> None:
    row = AnnouncementRow(announcementCategory="X", remarks="y")
    assert announcement_to_disclosure(row, symbol="JKH.N0000") is None
