"""Wave14: cover remaining briefs/worker.py partial branches."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.adapters.cse import CDN_BASE
from koel.briefs import BriefSettings
from koel.briefs.worker import (
    _notify_brief_followups,
    _title_only_input_text,
    claim_pending_briefs,
)
from koel.notify import SendResult


def _enabled_settings(**kwargs: Any) -> BriefSettings:
    base = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        pdf_grace_seconds=0,
        skipped_promote_hours=24,
        sleep_seconds=0,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


def _pending_row(**kwargs: Any) -> dict[str, Any]:
    row = {
        "disclosure_id": 7,
        "external_id": "99",
        "symbol": "JKH.N0000",
        "title": "AGM Notice",
        "url": "https://www.cse.lk/announcements#99",
        "pdf_url": None,
    }
    row.update(kwargs)
    return row


def test_title_only_input_text_falls_back_to_single_field() -> None:
    """Line 176: when only title or only symbol is present."""
    assert _title_only_input_text({"symbol": "", "title": "Solo title"}) == "Solo title"
    assert _title_only_input_text({"symbol": "JKH.N0000", "title": ""}) == "JKH.N0000"
    assert _title_only_input_text({"symbol": None, "title": None}) == ""


@pytest.mark.asyncio
async def test_empty_pdf_extract_falls_back_to_title() -> None:
    """Successful CDN fetch + empty extract → title-only prompt (image-only PDF)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    pdf_url = f"{CDN_BASE}/uploadAnnounceFiles/image-only.pdf"
    storage.claim_pending_briefs = AsyncMock(
        return_value=[_pending_row(pdf_url=pdf_url)]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="title brief")

    with (
        patch("koel.briefs.worker.fetch_cdn_pdf", AsyncMock(return_value=b"%PDF-empty")),
        patch("koel.briefs.worker.extract_pdf_text", return_value=""),
    ):
        n = await claim_pending_briefs(
            storage,
            settings=_enabled_settings(),
            provider=provider,
            http_client=AsyncMock(),
        )

    assert n == 1
    provider.summarize.assert_awaited_once()
    prompt = provider.summarize.await_args.args[0]
    assert "JKH.N0000" in prompt
    assert "AGM Notice" in prompt
    storage.mark_brief_ready.assert_awaited_once()


@pytest.mark.asyncio
async def test_followup_skips_when_claim_fn_missing() -> None:
    """No claim_brief_followups on storage → silent no-op (line 262)."""
    storage = MagicMock()
    storage.claim_brief_followups = None

    async def notify(_chat_id: int, _text: str) -> SendResult:
        raise AssertionError("notify must not run")

    await _notify_brief_followups(
        storage,
        notify=notify,
        row=_pending_row(),
        brief="Board met.",
    )


@pytest.mark.asyncio
async def test_followup_mark_failed_fail_soft() -> None:
    """Telegram OK but mark_delivery/mark_sent raises → warn, do not raise."""
    storage = MagicMock()
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {
                "id": 501,
                "rule_id": 9,
                "telegram_id": 1001,
                "message_text": "follow-up body",
            }
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock(side_effect=RuntimeError("db down"))
    storage.mark_alert_sent = AsyncMock()

    async def notify(_chat_id: int, _text: str) -> SendResult:
        return SendResult.OK

    await _notify_brief_followups(
        storage,
        notify=notify,
        row=_pending_row(),
        brief="Board met.",
    )
    storage.mark_delivery_attempted_ok.assert_awaited_once_with(501)
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_followup_outer_exception_fail_soft() -> None:
    """claim_brief_followups boom → outer brief_followup_failed, never raises."""
    storage = MagicMock()
    storage.claim_brief_followups = AsyncMock(side_effect=RuntimeError("claim boom"))

    async def notify(_chat_id: int, _text: str) -> SendResult:
        raise AssertionError("notify must not run")

    await _notify_brief_followups(
        storage,
        notify=notify,
        row=_pending_row(),
        brief="Board met.",
    )


@pytest.mark.asyncio
async def test_promote_skipped_hours_zero_skips() -> None:
    """skipped_promote_hours=0 → do not call promote (line 350)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=9)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(skipped_promote_hours=0),
        provider=AsyncMock(),
        http_client=AsyncMock(),
    )
    assert n == 0
    storage.promote_recent_skipped_briefs.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_skipped_missing_or_noncallable() -> None:
    """Missing / non-callable promote → skip (line 353)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = None
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=AsyncMock(),
        http_client=AsyncMock(),
    )
    assert n == 0

    storage.promote_recent_skipped_briefs = "not-callable"
    n2 = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=AsyncMock(),
        http_client=AsyncMock(),
    )
    assert n2 == 0


@pytest.mark.asyncio
async def test_promote_skipped_exception_fail_soft() -> None:
    """promote raises → warn and continue drain (lines 359-360)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(side_effect=RuntimeError("promote boom"))
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=AsyncMock(),
        http_client=AsyncMock(),
    )
    assert n == 0
    storage.claim_pending_briefs.assert_awaited_once()


@pytest.mark.asyncio
async def test_sweep_skips_when_list_fn_missing() -> None:
    """No list_ready_briefs_for_followup_sweep → sweep no-op (line 372)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=50)  # cap → no claim
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = None

    async def notify(_chat_id: int, _text: str) -> SendResult:
        raise AssertionError("notify must not run")

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(max_briefs_per_day=50),
        provider=AsyncMock(),
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 0


@pytest.mark.asyncio
async def test_sweep_list_exception_fail_soft() -> None:
    """list_ready_briefs_for_followup_sweep raises → warn and return (376-378)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=50)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(
        side_effect=RuntimeError("list boom")
    )

    async def notify(_chat_id: int, _text: str) -> SendResult:
        raise AssertionError("notify must not run")

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(max_briefs_per_day=50),
        provider=AsyncMock(),
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 0


@pytest.mark.asyncio
async def test_sweep_skips_non_dict_and_empty_brief_rows() -> None:
    """Sweep ignores non-dict rows and blank briefs (lines 381, 384)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=50)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(
        return_value=[
            "not-a-dict",
            {"disclosure_id": 1, "brief": "   ", "symbol": "X", "external_id": "1"},
            {"disclosure_id": 2, "brief": None, "symbol": "Y", "external_id": "2"},
            {
                "disclosure_id": 7,
                "brief": "Real brief",
                "external_id": "99",
                "symbol": "JKH.N0000",
                "title": "AGM",
                "url": "https://www.cse.lk/announcements#99",
            },
        ]
    )
    storage.claim_brief_followups = AsyncMock(return_value=[])

    async def notify(_chat_id: int, _text: str) -> SendResult:
        return SendResult.OK

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(max_briefs_per_day=50),
        provider=AsyncMock(),
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 0
    storage.claim_brief_followups.assert_awaited_once()
    assert storage.claim_brief_followups.await_args.kwargs["brief"] == "Real brief"


@pytest.mark.asyncio
async def test_cdn_transient_without_requeue_marks_failed() -> None:
    """CDN miss + no requeue_brief_pending → permanent mark_brief_failed (line 480)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    pdf_url = f"{CDN_BASE}/uploadAnnounceFiles/missing.pdf"
    storage.claim_pending_briefs = AsyncMock(
        return_value=[_pending_row(pdf_url=pdf_url)]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.requeue_brief_pending = None
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="should not run")

    with patch("koel.briefs.worker.fetch_cdn_pdf", AsyncMock(return_value=None)):
        n = await claim_pending_briefs(
            storage,
            settings=_enabled_settings(),
            provider=provider,
            http_client=AsyncMock(),
        )

    assert n == 1
    provider.summarize.assert_not_awaited()
    storage.mark_brief_ready.assert_not_awaited()
    storage.mark_brief_failed.assert_awaited_once()
    err = storage.mark_brief_failed.await_args.kwargs["error"]
    assert "CDN PDF fetch failed" in err
