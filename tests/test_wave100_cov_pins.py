"""Wave100: restore 100% cov after w96–w98 harden paths."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import RetryAfter

from koel.config import Settings
from koel.notify import send_message
from koel.poller import Poller

_DSN = "postgresql://koel:koel@localhost:5432/koel"


def test_market_tz_blank_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("MARKET_TZ", "   ")

    settings = Settings.from_env(require_token=True)
    assert settings.market_tz == "Asia/Colombo"


@pytest.mark.asyncio
async def test_send_message_cancelled_on_first_attempt_propagates() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await send_message(bot, chat_id=1001, text="hello")


@pytest.mark.asyncio
async def test_send_message_cancelled_on_retry_attempt_propagates() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=[RetryAfter(1), asyncio.CancelledError()])

    with (
        patch("koel.notify.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(asyncio.CancelledError),
    ):
        await send_message(bot, chat_id=1001, text="hello")


@pytest.mark.asyncio
async def test_run_once_outer_exception_marks_tick_failed() -> None:
    """Unexpected boom inside the locked cycle must set last_error + last_tick_ok."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    poller = Poller(
        Settings(telegram_bot_token="x", database_url=_DSN, poll_jitter_seconds=0),
        storage,
        AsyncMock(),
        AsyncMock(return_value=True),
    )
    poller._poll_prices = AsyncMock(side_effect=RuntimeError("cycle boom"))  # type: ignore[method-assign]

    events = await poller.run_once(force=True)

    assert events == []
    assert poller.last_tick_ok is False
    assert poller.last_error == "cycle boom"
    storage.advisory_unlock.assert_awaited()
