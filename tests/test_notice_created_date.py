"""Notice board createdDate may be epoch-ms or Colombo clock strings."""

from __future__ import annotations

from koel.adapters.cse import (
    FlexibleNoticeRow,
    _parse_notice_created_date,
    flexible_row_to_notice,
)


def test_parse_notice_created_date_string_clock() -> None:
    dt = _parse_notice_created_date("14 Jul 2026 05:10:30 PM")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 7
    assert dt.day == 14


def test_parse_notice_created_date_epoch_ms() -> None:
    dt = _parse_notice_created_date(1_720_000_000_000)
    assert dt is not None


def test_flexible_notice_accepts_string_created_date() -> None:
    row = FlexibleNoticeRow.model_validate(
        {
            "id": 1,
            "announcementId": 99,
            "createdDate": "10 Jul 2026 04:37:07 PM",
            "title": None,
            "company": "ACME PLC",
            "announcementCategory": "NON-COMPLIANCE OF MINIMUM PUBLIC HOLDING",
        }
    )
    notice = flexible_row_to_notice(row, notice_type="non_compliance")
    assert notice is not None
    assert notice.title == "ACME PLC"
    assert notice.published_at.year == 2026
