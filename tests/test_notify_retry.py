"""WS-083: notify.send_message retries once after RetryAfter."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from structlog.testing import capture_logs
from telegram.error import NetworkError, RetryAfter, TelegramError, TimedOut

from chime.notify import SendResult, _retry_delay_seconds, send_message


def test_retry_delay_seconds_accepts_timedelta_and_numeric() -> None:
    assert _retry_delay_seconds(timedelta(seconds=2, milliseconds=500)) == pytest.approx(2.5)
    assert _retry_delay_seconds(3) == 3.0
    assert _retry_delay_seconds(1.25) == pytest.approx(1.25)


@pytest.mark.parametrize("raw", [float("nan"), float("inf"), float("-inf"), -1.0, -0.5])
def test_retry_delay_seconds_rejects_nonfinite_and_negative(raw: float) -> None:
    """Wave15: min(nan, 30) is nan — clamp non-finite / negative to 0."""
    assert _retry_delay_seconds(raw) == 0.0


def test_retry_delay_seconds_caps_large_values() -> None:
    assert _retry_delay_seconds(999) == 30.0
    assert _retry_delay_seconds(timedelta(seconds=120)) == 30.0


@pytest.mark.asyncio
async def test_send_message_ok_on_first_attempt() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=None)

    result = await send_message(bot, chat_id=1001, text="hello")

    assert result is SendResult.OK
    bot.send_message.assert_awaited_once_with(
        chat_id=1001,
        text="hello",
        disable_web_page_preview=False,
    )


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
async def test_retry_after_timedelta_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """PTB may surface retry_after as timedelta (PTB_TIMEDELTA / future default)."""
    monkeypatch.setenv("PTB_TIMEDELTA", "1")
    flood = RetryAfter(2)
    assert isinstance(flood.retry_after, timedelta)
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=[flood, None])

    with patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep:
        result = await send_message(bot, chat_id=1001, text="hello")

    assert result is SendResult.OK
    sleep.assert_awaited_once()
    assert sleep.await_args.args[0] == pytest.approx(2.5)


@pytest.mark.asyncio
async def test_retry_after_then_telegram_error_returns_failed() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=[RetryAfter(1), TelegramError("still blocked")])

    with (
        capture_logs() as logs,
        patch("chime.notify.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await send_message(bot, chat_id=1001, text="hello")

    assert result is SendResult.FAILED
    assert bot.send_message.await_count == 2
    sleep.assert_awaited_once()
    assert {
        "event": "telegram_retry_failed",
        "log_level": "warning",
        "error": "still blocked",
        "chat_id": 1001,
    } in logs


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


@pytest.mark.asyncio
async def test_telegram_error_returns_failed() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=TelegramError("forbidden"))

    with capture_logs() as logs:
        result = await send_message(bot, chat_id=42, text="x")

    assert result is SendResult.FAILED
    assert {
        "event": "telegram_error",
        "log_level": "error",
        "error": "forbidden",
        "chat_id": 42,
    } in logs
