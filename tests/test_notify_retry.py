"""WS-083: notify.send_message retries once after RetryAfter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from telegram.error import RetryAfter

from chime.notify import send_message


@pytest.mark.asyncio
async def test_send_message_retry_after_then_succeeds() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(
        side_effect=[RetryAfter(1), None]  # first flood, then ok
    )

    with patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep:
        ok = await send_message(bot, chat_id=1001, text="hello")

    assert ok is True
    assert bot.send_message.await_count == 2
    sleep.assert_awaited_once()
    # first call includes disable_web_page_preview; retry is bare send
    first_kwargs = bot.send_message.await_args_list[0].kwargs
    assert first_kwargs["chat_id"] == 1001
    assert first_kwargs["text"] == "hello"


@pytest.mark.asyncio
async def test_retry_after_sleep_is_capped() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=[RetryAfter(999), None])

    with patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep:
        ok = await send_message(bot, chat_id=1001, text="hello")

    assert ok is True
    # Cap is 30s + 0.5 buffer — must not sleep ~999s
    slept = sleep.await_args.args[0]
    assert slept <= 30.5 + 0.01
