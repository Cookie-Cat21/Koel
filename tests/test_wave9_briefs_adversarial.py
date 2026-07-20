"""Wave9 adversarial: blank pdf_url enrich, CDN fail≠title-only, prompt truncate."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from koel.adapters.cse import CDN_BASE
from koel.briefs import BriefSettings, build_brief_prompt
from koel.briefs.provider import GeminiBriefProvider
from koel.briefs.worker import claim_pending_briefs
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
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_set_disclosure_pdf_url_fills_blank_as_missing() -> None:
    """Blank/whitespace pdf_url must not permanently block enrich (grace parity)."""
    conn = _Conn([{"id": 7}])
    store = _store(conn)
    assert await store.set_disclosure_pdf_url(7, f"{CDN_BASE}/uploadAnnounceFiles/a.pdf") is True
    assert "NULLIF(btrim(pdf_url), '') IS NULL" in conn.sql[0]


def test_build_brief_prompt_truncates_body_not_end_marker() -> None:
    prompt = build_brief_prompt(
        symbol="JKH.N0000",
        title="AGM",
        extracted_text="Z" * 500,
        max_chars=40,
    )
    assert "<<<FILING>>>" in prompt
    assert "<<<END_FILING>>>" in prompt
    assert "Z" * 40 in prompt
    assert "Z" * 41 not in prompt


@pytest.mark.asyncio
async def test_sanitize_preserves_end_marker_when_truncating_wrapped() -> None:
    """Small AI_MAX_INPUT_CHARS must not chop <<<END_FILING>>> and re-wrap badly."""
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}
                ]
            },
        )

    wrapped = (
        "Symbol: JKH.N0000\nTitle: AGM\n\n<<<FILING>>>\n"
        + ("Q" * 200)
        + "\n<<<END_FILING>>>\n\nNot financial advice — informational only."
    )
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiBriefProvider(
            _enabled_settings(max_input_chars=30),
            client=client,
        )
        await provider.summarize(wrapped)

    user_text = bodies[0]["contents"][0]["parts"][0]["text"]
    assert user_text.count("<<<FILING>>>") == 1
    assert user_text.count("<<<END_FILING>>>") == 1
    assert "Q" * 30 in user_text
    assert "Q" * 31 not in user_text
    assert user_text.index("<<<FILING>>>") < user_text.index("<<<END_FILING>>>")


@pytest.mark.asyncio
async def test_claim_pending_briefs_cdn_fetch_fail_requeues_not_failed() -> None:
    """pdf_url set + CDN miss must requeue pending (no daily-cap burn), not fail."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 42,
                "symbol": "JKH.N0000",
                "title": "AGM Notice",
                "external_id": "99",
                "pdf_url": f"{CDN_BASE}/uploadAnnounceFiles/missing.pdf",
            }
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.requeue_brief_pending = AsyncMock(return_value=True)

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
    storage.mark_brief_failed.assert_not_awaited()
    storage.requeue_brief_pending.assert_awaited_once()
    err = storage.requeue_brief_pending.await_args.kwargs["error"]
    assert "CDN PDF fetch failed" in err


@pytest.mark.asyncio
async def test_claim_pending_briefs_hostile_pdf_url_marks_failed() -> None:
    """Non-CDN pdf_url must permanent-fail (no requeue poison loop)."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 43,
                "symbol": "JKH.N0000",
                "title": "AGM Notice",
                "external_id": "100",
                "pdf_url": "https://evil.example/steal.pdf",
            }
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.requeue_brief_pending = AsyncMock(return_value=True)

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="should not run")

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
    assert "not allowlisted" in err
