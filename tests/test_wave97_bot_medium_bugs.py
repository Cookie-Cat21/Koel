"""Wave97: medium+ Telegram notify delivery boundary regressions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import RetryAfter

from chime.notify import SendResult, send_message


@pytest.mark.asyncio
async def test_send_message_unexpected_client_error_returns_failed() -> None:
    """Unexpected client failures must not abort poller retry/dead-letter accounting."""
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("http client exploded"))

    result = await send_message(bot, chat_id=1001, text="hello")

    assert result is SendResult.FAILED
    bot.send_message.assert_awaited_once_with(
        chat_id=1001,
        text="hello",
        disable_web_page_preview=False,
    )


@pytest.mark.asyncio
async def test_send_message_retry_unexpected_client_error_returns_failed() -> None:
    """The RetryAfter retry path has the same fail-closed boundary."""
    bot = MagicMock()
    bot.send_message = AsyncMock(
        side_effect=[RetryAfter(1), RuntimeError("retry transport exploded")]
    )

    with patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep:
        result = await send_message(bot, chat_id=1001, text="hello")

    assert result is SendResult.FAILED
    assert bot.send_message.await_count == 2
    sleep.assert_awaited_once()
