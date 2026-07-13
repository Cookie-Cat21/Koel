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
    elif isinstance(retry_after, bool) or not isinstance(retry_after, (int, float)):
        # Fail closed — bool soft-accepts via float(True)==1.0 mid flood sleep.
        return 0.0
    else:
        delay = float(retry_after)
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
    not held for the flood wait. Callers leave ``alert_log.message_sent=False``
    and may bump ``attempt_count`` toward ``MAX_DEFERRED_ATTEMPTS``.
    """
    # Fail closed — bool chat_id soft-accepts via Telegram kwargs; non-str text
    # used to throw or coerce mid deliver.
    if isinstance(chat_id, bool) or not isinstance(chat_id, int):
        log.error("telegram_bad_chat_id", chat_id=chat_id)
        return SendResult.FAILED
    if not isinstance(text, str) or not text:
        log.error("telegram_bad_text", text_type=type(text).__name__)
        return SendResult.FAILED
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
        except asyncio.CancelledError:
            raise
        except RetryAfter as retry_exc:
            # Flood control is still active — this is a defer, not a failure.
            # Counting it as FAILED would burn down MAX_SEND_ATTEMPTS for an
            # alert that was never actually undeliverable.
            log.warning(
                "telegram_retry_after_still_active",
                chat_id=chat_id,
                retry_after=str(retry_exc.retry_after),
            )
            return SendResult.DEFERRED
        except TelegramError as retry_exc:
            log.warning("telegram_retry_failed", error=str(retry_exc), chat_id=chat_id)
            return SendResult.FAILED
        except Exception as retry_exc:
            log.exception(
                "telegram_retry_unexpected_error",
                error=str(retry_exc),
                chat_id=chat_id,
            )
            return SendResult.FAILED
    except (TimedOut, NetworkError) as exc:
        log.warning("telegram_transient", error=str(exc), chat_id=chat_id)
        return SendResult.FAILED
    except TelegramError as exc:
        log.error("telegram_error", error=str(exc), chat_id=chat_id)
        return SendResult.FAILED
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.exception("telegram_unexpected_error", error=str(exc), chat_id=chat_id)
        return SendResult.FAILED
