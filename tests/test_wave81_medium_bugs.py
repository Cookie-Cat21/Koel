"""Wave81: medium+ bugs — notify RetryAfter/chat_id + disclosure external_id.

1. ``_retry_delay_seconds`` must reject bool (``float(True)==1.0`` soft-accept
   used to sleep ~1.5s on a poisoned RetryAfter).
2. ``send_message`` must isinstance-guard ``chat_id`` / ``text`` (no bool
   chat_id → Telegram API / ``str()`` soft-accept).
3. ``announcement_to_disclosure`` must reject bool/non-int external ids before
   ``str()`` (``str(True)=="True"`` poisoned disclosure identity).
4. ``legacy_pdf_urls_by_id`` must reject bool ``announcementId`` before
   ``str()`` map keys.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.adapters.cse import (
    AnnouncementRow,
    LegacyAnnouncementRow,
    announcement_to_disclosure,
    legacy_pdf_urls_by_id,
)
from koel.notify import SendResult, _retry_delay_seconds, send_message

ROOT = Path(__file__).resolve().parents[1]


def test_retry_delay_rejects_bool_soft_accept() -> None:
    assert _retry_delay_seconds(True) == 0.0  # type: ignore[arg-type]
    assert _retry_delay_seconds(False) == 0.0  # type: ignore[arg-type]
    assert _retry_delay_seconds(5) == 5.0
    assert _retry_delay_seconds(2.5) == pytest.approx(2.5)
    assert _retry_delay_seconds(timedelta(seconds=3)) == pytest.approx(3.0)

    src = (ROOT / "koel" / "notify.py").read_text(encoding="utf-8")
    chunk = src.split("def _retry_delay_seconds")[1].split("async def send_message")[0]
    assert "isinstance(retry_after, bool)" in chunk
    assert "float(retry_after)" in chunk


@pytest.mark.asyncio
async def test_send_message_rejects_bool_chat_id_and_non_str_text() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()

    assert await send_message(bot, True, "hi") == SendResult.FAILED  # type: ignore[arg-type]
    assert await send_message(bot, False, "hi") == SendResult.FAILED  # type: ignore[arg-type]
    assert await send_message(bot, "9", "hi") == SendResult.FAILED  # type: ignore[arg-type]
    assert await send_message(bot, 9, 123) == SendResult.FAILED  # type: ignore[arg-type]
    assert await send_message(bot, 9, "") == SendResult.FAILED
    bot.send_message.assert_not_awaited()

    bot.send_message = AsyncMock(return_value=None)
    assert await send_message(bot, 9, "hi") == SendResult.OK
    bot.send_message.assert_awaited_once()

    src = (ROOT / "koel" / "notify.py").read_text(encoding="utf-8")
    chunk = src.split("async def send_message")[1]
    assert "isinstance(chat_id, bool)" in chunk
    assert "isinstance(text, str)" in chunk


def test_announcement_to_disclosure_rejects_bool_external_id() -> None:
    base = AnnouncementRow.model_construct(
        announcementId=None,
        id=None,
        company="John Keells",
        announcementCategory="Filing",
        remarks=None,
        createdDate=1_720_000_000_000,
        dateOfAnnouncement=None,
    )
    poisoned = base.model_copy(update={"announcementId": True})
    assert announcement_to_disclosure(poisoned, symbol="JKH.N0000") is None

    ok = base.model_copy(update={"announcementId": 42})
    disc = announcement_to_disclosure(ok, symbol="JKH.N0000")
    assert disc is not None
    assert disc.external_id == "42"
    assert "True" not in disc.url

    src = (ROOT / "koel" / "adapters" / "cse.py").read_text(encoding="utf-8")
    chunk = src.split("def announcement_to_disclosure")[1].split(
        "def normalize_company_name"
    )[0]
    assert "isinstance(external, bool)" in chunk
    assert "external_id=str(external)" in chunk or "external_id = str(external)" in chunk


def test_legacy_pdf_urls_rejects_bool_announcement_id() -> None:
    rows = [
        LegacyAnnouncementRow.model_construct(
            announcementId=True,
            filePath="/files/a.pdf",
        ),
        LegacyAnnouncementRow.model_construct(
            announcementId=99,
            filePath="/files/b.pdf",
        ),
    ]
    out = legacy_pdf_urls_by_id(rows)  # type: ignore[arg-type]
    assert "True" not in out
    assert "99" in out

    src = (ROOT / "koel" / "adapters" / "cse.py").read_text(encoding="utf-8")
    chunk = src.split("def legacy_pdf_urls_by_id")[1].split("def _retryable")[0]
    assert "isinstance(raw_id, bool)" in chunk
    assert "str(raw_id)" in chunk
