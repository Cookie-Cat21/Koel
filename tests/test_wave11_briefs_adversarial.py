"""Wave11 adversarial: CDN permanent vs backoff, Telegram URL egress."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.adapters.cse import CDN_BASE
from koel.briefs import BriefSettings
from koel.briefs.extract import CdnPdfPermanentError
from koel.briefs.worker import claim_pending_briefs
from koel.domain import (
    AlertEvent,
    AlertType,
    disclaimer,
    format_alert_message,
    format_brief_followup,
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


def test_brief_settings_cdn_backoff_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIEF_CDN_BACKOFF_SECONDS", "120")
    cfg = BriefSettings.from_env()
    assert cfg.cdn_backoff_seconds == 120


def test_brief_settings_cdn_backoff_invalid_soft_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIEF_CDN_BACKOFF_SECONDS", "nope")
    cfg = BriefSettings.from_env()
    assert cfg.cdn_backoff_seconds == 300


@pytest.mark.asyncio
async def test_claim_pending_briefs_cdn_backoff_sql() -> None:
    """Pending+error+pdf_url must wait cdn_backoff before reclaim (no hammer)."""
    conn = _Conn(
        [
            None,
            {"n": 0},
            [],
        ]
    )
    store = _store(conn)
    await store.claim_pending_briefs(
        limit=1,
        max_briefs_per_day=10,
        pdf_grace_seconds=90,
        cdn_backoff_seconds=180,
    )
    claim_sql = next(s for s in conn.sql if "FOR UPDATE OF b SKIP LOCKED" in s)
    assert "b.error IS NULL" in claim_sql
    assert conn.params[-1] == (15, 90, 180, 1)


@pytest.mark.asyncio
async def test_claim_pending_briefs_passes_cdn_backoff() -> None:
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(cdn_backoff_seconds=90),
        provider=AsyncMock(),
        http_client=AsyncMock(),
    )
    assert n == 0
    kwargs = storage.claim_pending_briefs.await_args.kwargs
    assert kwargs["cdn_backoff_seconds"] == 90


@pytest.mark.asyncio
async def test_claim_pending_briefs_oversized_pdf_marks_failed() -> None:
    """Oversized CDN body is permanent — must not requeue-poison the queue."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 44,
                "symbol": "JKH.N0000",
                "title": "AGM Notice",
                "external_id": "101",
                "pdf_url": f"{CDN_BASE}/uploadAnnounceFiles/huge.pdf",
            }
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.requeue_brief_pending = AsyncMock(return_value=True)

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="should not run")

    with patch(
        "koel.briefs.worker.fetch_cdn_pdf",
        AsyncMock(side_effect=CdnPdfPermanentError("CDN PDF too large")),
    ):
        n = await claim_pending_briefs(
            storage,
            settings=_enabled_settings(),
            provider=provider,
            http_client=AsyncMock(),
        )

    assert n == 1
    provider.summarize.assert_not_awaited()
    storage.requeue_brief_pending.assert_not_awaited()
    storage.mark_brief_failed.assert_awaited_once()
    err = storage.mark_brief_failed.await_args.kwargs["error"]
    assert "too large" in err


@pytest.mark.asyncio
async def test_claim_pending_briefs_redirect_marks_failed() -> None:
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 45,
                "symbol": "JKH.N0000",
                "title": "AGM Notice",
                "external_id": "102",
                "pdf_url": f"{CDN_BASE}/uploadAnnounceFiles/redir.pdf",
            }
        ]
    )
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.requeue_brief_pending = AsyncMock(return_value=True)
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="nope")

    with patch(
        "koel.briefs.worker.fetch_cdn_pdf",
        AsyncMock(side_effect=CdnPdfPermanentError("CDN PDF redirect rejected")),
    ):
        await claim_pending_briefs(
            storage,
            settings=_enabled_settings(),
            provider=provider,
            http_client=AsyncMock(),
        )

    storage.requeue_brief_pending.assert_not_awaited()
    storage.mark_brief_failed.assert_awaited_once()
    assert "redirect" in storage.mark_brief_failed.await_args.kwargs["error"]


def test_format_brief_followup_strips_hostile_url() -> None:
    msg = format_brief_followup(
        symbol="JKH.N0000",
        brief="Board met.",
        title="AGM",
        url="https://evil.example/phish",
    )
    assert "evil.example" not in msg
    assert "Board met." in msg
    assert disclaimer() in msg


def test_format_brief_followup_keeps_cse_url() -> None:
    msg = format_brief_followup(
        symbol="JKH.N0000",
        brief="Board met.",
        url="https://www.cse.lk/announcements#99",
    )
    assert "https://www.cse.lk/announcements#99" in msg


def test_format_alert_message_strips_hostile_disclosure_url() -> None:
    event = AlertEvent(
        rule_id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        trigger="new disclosure",
        disclosure_title="AGM",
        disclosure_url="javascript:alert(1)",
        event_key="disclosure:1:99",
    )
    msg = format_alert_message(event)
    assert "javascript:" not in msg
    assert disclaimer() in msg
