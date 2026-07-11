"""Telegram send helpers with RetryAfter / NetworkError handling."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import structlog
from telegram import Bot
from telegram.error import NetworkError, RetryAfter, TelegramError, TimedOut

log = structlog.get_logger(__name__)


def _retry_delay_seconds(retry_after: int | float | timedelta) -> float:
    if isinstance(retry_after, timedelta):
        return retry_after.total_seconds()
    return float(retry_after)


async def send_message(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=False)
        return True
    except RetryAfter as exc:
        # Cap sleep so a RetryAfter storm cannot pin the poller advisory lock
        # for unbounded wall time; leave message_sent=False for later retry.
        delay = min(_retry_delay_seconds(exc.retry_after), 30.0)
        await asyncio.sleep(delay + 0.5)
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            return True
        except TelegramError as retry_exc:
            log.warning("telegram_retry_failed", error=str(retry_exc), chat_id=chat_id)
            return False
    except (TimedOut, NetworkError) as exc:
        log.warning("telegram_transient", error=str(exc), chat_id=chat_id)
        return False
    except TelegramError as exc:
        log.error("telegram_error", error=str(exc), chat_id=chat_id)
        return False
