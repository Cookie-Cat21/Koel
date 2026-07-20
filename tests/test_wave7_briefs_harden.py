"""Wave7: PDF grace, skipped promote, late follow-up sweep, BriefSettings harden."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.briefs import BriefSettings
from koel.briefs.worker import claim_pending_briefs
from koel.domain import format_brief_followup
from koel.notify import SendResult
from tests.test_storage_unit import _Conn, _store


def _enabled_settings(**kwargs: Any) -> BriefSettings:
    base = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        pdf_grace_seconds=120,
        skipped_promote_hours=24,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


def test_brief_settings_from_env_soft_parses_bad_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_BRIEFS_ENABLED", "0")
    monkeypatch.setenv("AI_MAX_BRIEFS_PER_DAY", "not-a-number")
    monkeypatch.setenv("AI_MAX_INPUT_CHARS", "")
    monkeypatch.setenv("PDF_MAX_BYTES", "nope")
    monkeypatch.setenv("AI_HTTP_TIMEOUT_SECONDS", "abc")
    monkeypatch.setenv("BRIEF_PDF_GRACE_SECONDS", "xyz")
    monkeypatch.setenv("BRIEF_SKIPPED_PROMOTE_HOURS", "NaN")
    cfg = BriefSettings.from_env()
    assert cfg.max_briefs_per_day == 50
    assert cfg.max_input_chars == 12_000
    assert cfg.pdf_max_bytes == 5_242_880
    assert cfg.http_timeout_seconds == 30.0
    assert cfg.pdf_grace_seconds == 120
    assert cfg.skipped_promote_hours == 24


@pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "+inf", "-inf"])
def test_brief_settings_rejects_nonfinite_float_env(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    """Wave14: nan/inf must not pass max() clamps (max(1.0, nan) is nan)."""
    monkeypatch.setenv("AI_HTTP_TIMEOUT_SECONDS", raw)
    monkeypatch.setenv("AI_BRIEF_SLEEP_SECONDS", raw)
    cfg = BriefSettings.from_env()
    assert cfg.http_timeout_seconds == 30.0
    assert cfg.sleep_seconds == 0.5


def test_brief_settings_from_env_reads_grace_and_promote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIEF_PDF_GRACE_SECONDS", "90")
    monkeypatch.setenv("BRIEF_SKIPPED_PROMOTE_HOURS", "6")
    cfg = BriefSettings.from_env()
    assert cfg.pdf_grace_seconds == 90
    assert cfg.skipped_promote_hours == 6


@pytest.mark.asyncio
async def test_promote_recent_skipped_briefs_sql() -> None:
    conn = _Conn([[{"disclosure_id": 1}, {"disclosure_id": 2}]])
    store = _store(conn)
    assert await store.promote_recent_skipped_briefs(max_age_hours=24, limit=50) == 2
    sql = conn.sql[0]
    assert "status = 'skipped'" in sql
    assert "status = 'pending'" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert conn.params[0] == (24, 50)


@pytest.mark.asyncio
async def test_promote_recent_skipped_briefs_noop_when_hours_zero() -> None:
    conn = _Conn([])
    store = _store(conn)
    assert await store.promote_recent_skipped_briefs(max_age_hours=0) == 0
    assert conn.sql == []


@pytest.mark.asyncio
async def test_list_ready_briefs_for_followup_sweep_sql() -> None:
    conn = _Conn(
        [
            [
                {
                    "disclosure_id": 7,
                    "brief": "Board met.",
                    "external_id": "99",
                    "symbol": "JKH.N0000",
                    "title": "AGM",
                    "url": "https://www.cse.lk/announcements#99",
                }
            ]
        ]
    )
    store = _store(conn)
    rows = await store.list_ready_briefs_for_followup_sweep(limit=10)
    assert len(rows) == 1
    assert rows[0]["disclosure_id"] == 7
    assert "status = 'ready'" in conn.sql[0]
    assert "brief_followup:" in conn.sql[0]
    assert "ORDER BY b.updated_at ASC" in conn.sql[0]
    assert conn.params[0] == (7, 10)


@pytest.mark.asyncio
async def test_claim_pending_briefs_passes_pdf_grace() -> None:
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(pdf_grace_seconds=45),
        provider=AsyncMock(),
        http_client=AsyncMock(),
    )
    assert n == 0
    kwargs = storage.claim_pending_briefs.await_args.kwargs
    assert kwargs["pdf_grace_seconds"] == 45
    storage.promote_recent_skipped_briefs.assert_awaited_once()


@pytest.mark.asyncio
async def test_claim_pending_briefs_sweep_followup_when_cap_blocks_claim() -> None:
    """Daily cap must not block late follow-up after primary finally delivers."""
    brief = "AGM set for August."
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=50)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(
        return_value=[
            {
                "disclosure_id": 7,
                "brief": brief,
                "external_id": "99",
                "symbol": "JKH.N0000",
                "title": "AGM Notice",
                "url": "https://www.cse.lk/announcements#99",
            }
        ]
    )
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {
                "id": 501,
                "rule_id": 9,
                "telegram_id": 1001,
                "message_text": format_brief_followup(
                    symbol="JKH.N0000",
                    brief=brief,
                    title="AGM Notice",
                ),
            }
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()

    sent: list[tuple[int, str]] = []

    async def notify(chat_id: int, text: str) -> SendResult:
        sent.append((chat_id, text))
        return SendResult.OK

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(max_briefs_per_day=50),
        provider=AsyncMock(),
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 0
    storage.claim_pending_briefs.assert_not_awaited()
    storage.list_ready_briefs_for_followup_sweep.assert_awaited_once()
    storage.claim_brief_followups.assert_awaited_once()
    assert len(sent) == 1
    assert sent[0][0] == 1001
    assert brief in sent[0][1]
    storage.mark_alert_sent.assert_awaited_once_with(501)


@pytest.mark.asyncio
async def test_claim_pending_briefs_promotes_skipped_then_drains() -> None:
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=3)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[])
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(skipped_promote_hours=12),
        provider=AsyncMock(),
        http_client=AsyncMock(),
    )
    assert n == 0
    storage.promote_recent_skipped_briefs.assert_awaited_once_with(max_age_hours=12)


@pytest.mark.asyncio
async def test_claim_pending_briefs_closes_owned_provider() -> None:
    """Worker must aclose owned HTTP providers (Gemini or Groq), not only Gemini."""
    from unittest.mock import patch

    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 2,
                "symbol": "JKH.N0000",
                "title": "Notice",
                "pdf_url": None,
                "external_id": "2",
                "url": "https://www.cse.lk/announcements#2",
            }
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    owned = AsyncMock()
    owned.summarize = AsyncMock(return_value="ok")
    owned.aclose = AsyncMock()

    with patch("koel.briefs.worker.make_brief_provider", return_value=owned):
        n = await claim_pending_briefs(
            storage,
            settings=_enabled_settings(provider="groq", pdf_grace_seconds=0),
            provider=None,
            http_client=AsyncMock(),
        )
    assert n == 1
    owned.summarize.assert_awaited_once()
    owned.aclose.assert_awaited_once()
