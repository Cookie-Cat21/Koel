"""WS-083: notify.send_message retries once after RetryAfter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from structlog.testing import capture_logs
from telegram.error import NetworkError, RetryAfter, TimedOut

from chime.notify import SendResult, send_message


@pytest.mark.asyncio
async def test_send_message_retry_after_then_succeeds() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(
        side_effect=[RetryAfter(1), None]  # first flood, then ok
    )

    with patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep:
        result = await send_message(bot, chat_id=1001, text="hello")

    assert result is SendResult.OK
    assert bot.send_message.await_count == 2
    sleep.assert_awaited_once()
    first_kwargs = bot.send_message.await_args_list[0].kwargs
    retry_kwargs = bot.send_message.await_args_list[1].kwargs
    assert first_kwargs["chat_id"] == 1001
    assert first_kwargs["text"] == "hello"
    assert first_kwargs.get("disable_web_page_preview") is False
    assert retry_kwargs.get("disable_web_page_preview") is False


@pytest.mark.asyncio
async def test_retry_after_sleep_is_capped() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=[RetryAfter(999), None])

    with patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep:
        result = await send_message(bot, chat_id=1001, text="hello")

    assert result is SendResult.OK
    sleep.assert_awaited_once()
    # Cap 30s + 0.5 buffer — never sleep the full RetryAfter(999).
    assert sleep.await_args.args[0] == pytest.approx(30.5)


@pytest.mark.asyncio
async def test_retry_after_deferred_when_nonblocking() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=RetryAfter(60))

    with patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep:
        result = await send_message(bot, chat_id=1001, text="hello", block_on_retry_after=False)

    assert result is SendResult.DEFERRED
    sleep.assert_not_awaited()
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_nonblocking_retry_after_returns_deferred_without_retrying() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=[RetryAfter(60), None])

    with (
        capture_logs() as logs,
        patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await send_message(bot, chat_id=1001, text="hello", block_on_retry_after=False)

    assert result is SendResult.DEFERRED
    assert bot.send_message.await_count == 1
    sleep.assert_not_awaited()
    assert {
        "event": "telegram_retry_after_deferred",
        "log_level": "warning",
        "chat_id": 1001,
        "retry_after": "60",
    } in logs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [TimedOut("t"), NetworkError("n")],
)
async def test_transient_errors_return_failed(exc: Exception) -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=exc)
    assert await send_message(bot, chat_id=1, text="x") is SendResult.FAILED
