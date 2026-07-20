"""Wave12 adversarial: Telegram brief-body cap + CDN permanent HTTP/host."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.adapters.cse import CDN_BASE
from koel.briefs import BriefSettings
from koel.briefs.extract import CdnPdfPermanentError
from koel.briefs.worker import claim_pending_briefs
from koel.domain import (
    BRIEF_BODY_MAX,
    AlertEvent,
    AlertType,
    disclaimer,
    format_alert_message,
    format_brief_followup,
    sanitize_brief_body,
)
from tests.test_storage_unit import _Conn, _store


def _enabled_settings(**kwargs: Any) -> BriefSettings:
    base = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        sleep_seconds=0,
        cdn_backoff_seconds=300,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


def test_sanitize_brief_body_strips_controls_and_caps() -> None:
    assert sanitize_brief_body("  ok  ") == "ok"
    assert sanitize_brief_body("\x00\x01") is None
    assert sanitize_brief_body(None) is None
    huge = "Z" * (BRIEF_BODY_MAX + 500)
    out = sanitize_brief_body(huge)
    assert out is not None
    assert len(out) == BRIEF_BODY_MAX
    assert out.endswith("…")


def test_format_alert_message_caps_huge_filing_brief() -> None:
    event = AlertEvent(
        rule_id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        trigger="new disclosure",
        disclosure_title="AGM",
        disclosure_url="https://www.cse.lk/announcements#1",
        filing_brief="X" * 8000,
        event_key="disclosure:1:1",
    )
    msg = format_alert_message(event)
    assert len(msg) < 4096
    assert "…" in msg
    assert disclaimer() in msg
    assert "\x00" not in msg


def test_format_alert_message_strips_control_only_brief() -> None:
    event = AlertEvent(
        rule_id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        trigger="new disclosure",
        filing_brief="\x00\x07\x1f",
        event_key="disclosure:1:2",
    )
    msg = format_alert_message(event)
    assert "\x00" not in msg
    assert disclaimer() in msg


def test_format_brief_followup_caps_and_strips_controls() -> None:
    msg = format_brief_followup(
        symbol="JKH.N0000",
        brief="A\x00" + ("B" * 9000),
        title="AGM",
        url="https://www.cse.lk/announcements#9",
    )
    assert "\x00" not in msg
    assert len(msg) < 4096
    assert "…" in msg
    assert disclaimer() in msg


@pytest.mark.asyncio
async def test_mark_brief_ready_sanitizes_and_caps_sql() -> None:
    conn = _Conn([{"disclosure_id": 3}])
    store = _store(conn)
    huge = "Q" * (BRIEF_BODY_MAX + 200)
    assert await store.mark_brief_ready(3, brief=huge, model="m") is True
    stored = conn.params[0][0]
    assert isinstance(stored, str)
    assert len(stored) == BRIEF_BODY_MAX
    assert stored.endswith("…")


@pytest.mark.asyncio
async def test_mark_brief_ready_rejects_control_only() -> None:
    conn = _Conn([])
    store = _store(conn)
    with pytest.raises(ValueError, match="empty after sanitize"):
        await store.mark_brief_ready(3, brief="\x00\x01", model="m")
    assert conn.sql == []


@pytest.mark.asyncio
async def test_claim_pending_briefs_cdn_403_marks_failed() -> None:
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 77,
                "symbol": "JKH.N0000",
                "title": "AGM",
                "external_id": "77",
                "pdf_url": f"{CDN_BASE}/uploadAnnounceFiles/x.pdf",
            }
        ]
    )
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.requeue_brief_pending = AsyncMock(return_value=True)
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="nope")

    with patch(
        "koel.briefs.worker.fetch_cdn_pdf",
        AsyncMock(side_effect=CdnPdfPermanentError("CDN PDF permanent HTTP 403")),
    ):
        await claim_pending_briefs(
            storage,
            settings=_enabled_settings(),
            provider=provider,
            http_client=AsyncMock(),
        )

    storage.requeue_brief_pending.assert_not_awaited()
    storage.mark_brief_failed.assert_awaited_once()
    assert "403" in storage.mark_brief_failed.await_args.kwargs["error"]
