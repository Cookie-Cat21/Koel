"""Telegram send helpers with RetryAfter / NetworkError handling."""

from __future__ import annotations

import asyncio
import math
from datetime import timedelta
from enum import StrEnum
from typing import Any

from telegram import Bot
from telegram.error import NetworkError, RetryAfter, TelegramError, TimedOut

from chime.logging_setup import get_logger

log = get_logger(__name__)

_SEND_KWARGS: dict[str, Any] = {"disable_web_page_preview": False}
_RETRY_AFTER_CAP_SECONDS = 30.0


class SendResult(StrEnum):
    """Outcome of a Telegram send attempt.

    ``deferred`` is a transient RetryAfter when the caller asked not to block.
    Callers may still bump attempt_count toward a deferred dead-letter ceiling.
    """

    OK = "ok"
    DEFERRED = "deferred"
    FAILED = "failed"


def _retry_delay_seconds(retry_after: int | float | timedelta) -> float:
    """Bounded RetryAfter sleep seconds: finite, ``>= 0``, capped at 30s.

    ``min(nan, 30)`` is nan and would poison ``asyncio.sleep``; negative or
    non-finite Telegram values fail closed to ``0`` before the cap.
    """
    if isinstance(retry_after, timedelta):
        delay = retry_after.total_seconds()
    else:
        try:
            delay = float(retry_after)
        except (TypeError, ValueError):
            return 0.0
    if not math.isfinite(delay) or delay < 0:
        return 0.0
    return min(delay, _RETRY_AFTER_CAP_SECONDS)


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    block_on_retry_after: bool = True,
) -> SendResult:
    """Send a Telegram message.

    When ``block_on_retry_after`` is False (poller holds the DB advisory lock),
    a ``RetryAfter`` returns ``SendResult.DEFERRED`` immediately so the lock is
    not held for the flood wait — ``alert_log.message_sent=False`` lets a later
    cycle retry without incrementing ``attempt_count``.
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text, **_SEND_KWARGS)
        return SendResult.OK
    except RetryAfter as exc:
        if not block_on_retry_after:
            log.warning(
                "telegram_retry_after_deferred",
                chat_id=chat_id,
                retry_after=str(exc.retry_after),
            )
            return SendResult.DEFERRED
        # Cap sleep so a RetryAfter storm cannot pin a caller indefinitely.
        delay = _retry_delay_seconds(exc.retry_after)
        await asyncio.sleep(delay + 0.5)
        try:
            await bot.send_message(chat_id=chat_id, text=text, **_SEND_KWARGS)
            return SendResult.OK
        except TelegramError as retry_exc:
            log.warning("telegram_retry_failed", error=str(retry_exc), chat_id=chat_id)
            return SendResult.FAILED
    except (TimedOut, NetworkError) as exc:
        log.warning("telegram_transient", error=str(exc), chat_id=chat_id)
        return SendResult.FAILED
    except TelegramError as exc:
        log.error("telegram_error", error=str(exc), chat_id=chat_id)
        return SendResult.FAILED
