"""E2-C07: one-shot Telegram notify when an alert is dead-lettered."""

from __future__ import annotations

from unittest.mock import AsyncMock, call

import pytest

from chime.config import Settings
from chime.domain import AlertEvent, AlertType, format_dead_letter_notify
from chime.notify import SendResult
from chime.poller import MAX_DEFERRED_ATTEMPTS, MAX_SEND_ATTEMPTS, Poller
from tests.conftest import claim_unsent_deque


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


def _event(*, rule_id: int = 1, telegram_id: int = 1001, symbol: str = "JKH.N0000") -> AlertEvent:
    return AlertEvent(
        rule_id=rule_id,
        user_id=10,
        telegram_id=telegram_id,
        symbol=symbol,
        type=AlertType.PRICE_ABOVE,
        trigger="cross_above",
        threshold=100.0,
        current_price=105.0,
        event_key="above:100.0:s42",
        snapshot_id=42,
    )


def _poller(*, send: AsyncMock, storage: AsyncMock | None = None) -> Poller:
    storage = storage or AsyncMock()
    return Poller(_settings(), storage, AsyncMock(), send)


def test_format_dead_letter_notify_includes_symbol_attempts_nfa() -> None:
    msg = format_dead_letter_notify("JKH.N0000", 5)
    assert msg == (
        "koel could not deliver an alert for JKH.N0000 after 5 tries. Not financial advice."
    )
    assert "Not financial advice" in msg


def test_format_dead_letter_notify_strips_controls_from_symbol() -> None:
    """Wave15: hostile/parsed symbols must not inject C0 controls into Telegram."""
    msg = format_dead_letter_notify("JKH\x00.N0000\n", 3)
    assert "\x00" not in msg
    assert "\n" not in msg
    assert "JKH.N0000" in msg
    assert "after 3 tries" in msg
    assert "Not financial advice" in msg


def test_format_dead_letter_notify_control_only_symbol_falls_back() -> None:
    msg = format_dead_letter_notify("\x00\x01", 2)
    assert "alert for ? after 2 tries" in msg


@pytest.mark.asyncio
async def test_record_send_failure_notifies_once_at_ceiling() -> None:
    storage = AsyncMock()
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_SEND_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.OK)

    poller = _poller(send=send, storage=storage)
    await poller._record_send_failure(
        55,
        rule_id=3,
        telegram_id=1001,
        symbol="JKH.N0000",
    )

    storage.dead_letter.assert_awaited_once_with(55)
    send.assert_awaited_once_with(1001, format_dead_letter_notify("JKH.N0000", MAX_SEND_ATTEMPTS))


@pytest.mark.asyncio
async def test_record_send_deferred_notifies_once_at_ceiling() -> None:
    storage = AsyncMock()
    storage.mark_alert_deferred_attempt = AsyncMock(return_value=MAX_DEFERRED_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=True)

    poller = _poller(send=send, storage=storage)
    await poller._record_send_deferred(
        66,
        rule_id=4,
        telegram_id=2002,
        symbol="COMB.N0000",
    )

    storage.dead_letter.assert_awaited_once_with(66)
    send.assert_awaited_once_with(
        2002, format_dead_letter_notify("COMB.N0000", MAX_DEFERRED_ATTEMPTS)
    )


@pytest.mark.asyncio
async def test_dead_letter_notify_path_attempted_once_per_alert_log_id() -> None:
    storage = AsyncMock()
    storage.mark_alert_attempt = AsyncMock(side_effect=[MAX_SEND_ATTEMPTS, MAX_SEND_ATTEMPTS + 1])
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.OK)

    poller = _poller(send=send, storage=storage)
    for _ in range(2):
        await poller._record_send_failure(
            55,
            rule_id=3,
            telegram_id=1001,
            symbol="JKH.N0000",
        )

    assert storage.dead_letter.await_count == 2
    send.assert_awaited_once_with(1001, format_dead_letter_notify("JKH.N0000", MAX_SEND_ATTEMPTS))


@pytest.mark.asyncio
async def test_dead_letter_notify_failure_is_log_only_no_attempt_bump() -> None:
    """Notify send failure must not call mark_alert_attempt / dead_letter again."""
    storage = AsyncMock()
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_SEND_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.FAILED)

    poller = _poller(send=send, storage=storage)
    await poller._record_send_failure(
        77,
        rule_id=5,
        telegram_id=1001,
        symbol="JKH.N0000",
    )

    storage.mark_alert_attempt.assert_awaited_once_with(77)
    storage.dead_letter.assert_awaited_once_with(77)
    send.assert_awaited_once()


@pytest.mark.asyncio
async def test_dead_letter_notify_exception_is_swallowed() -> None:
    storage = AsyncMock()
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_SEND_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(side_effect=RuntimeError("telegram down"))

    poller = _poller(send=send, storage=storage)
    await poller._record_send_failure(
        78,
        rule_id=5,
        telegram_id=1001,
        symbol="JKH.N0000",
    )

    storage.dead_letter.assert_awaited_once_with(78)
    assert storage.mark_alert_attempt.await_count == 1


@pytest.mark.asyncio
async def test_below_ceiling_does_not_notify() -> None:
    storage = AsyncMock()
    storage.mark_alert_attempt = AsyncMock(return_value=2)
    storage.dead_letter = AsyncMock()
    send = AsyncMock()

    poller = _poller(send=send, storage=storage)
    await poller._record_send_failure(
        79,
        rule_id=5,
        telegram_id=1001,
        symbol="JKH.N0000",
    )

    storage.dead_letter.assert_not_awaited()
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_and_send_dead_letter_sends_alert_then_notify() -> None:
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=88)
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_SEND_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=False)

    poller = _poller(send=send, storage=storage)
    event = _event()
    claimed = await poller._claim_and_send(event)

    assert claimed is True
    assert send.await_count == 2
    # First call: formatted alert; second: dead-letter notify (no attempt loop).
    notify_text = format_dead_letter_notify(event.symbol, MAX_SEND_ATTEMPTS)
    assert send.await_args_list[1] == call(event.telegram_id, notify_text)
    storage.mark_alert_attempt.assert_awaited_once_with(88)
    storage.dead_letter.assert_awaited_once_with(88)


@pytest.mark.asyncio
async def test_retry_unsent_parses_symbol_for_notify() -> None:
    storage = AsyncMock()
    alert_body = "🔔 SAMP.N0000\nTrigger: cross_above\n\nNot financial advice — informational only."
    batch = [
        {
            "id": 11,
            "rule_id": 2,
            "message_text": alert_body,
            "telegram_id": 1001,
            "attempt_count": 4,
        }
    ]
    storage.unsent_alerts = AsyncMock(return_value=batch)
    storage.claim_unsent_batch = claim_unsent_deque(batch)
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_SEND_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(side_effect=[SendResult.FAILED, SendResult.OK])

    poller = _poller(send=send, storage=storage)
    await poller._retry_unsent()

    assert send.await_count == 2
    assert send.await_args_list[0] == call(1001, alert_body)
    assert send.await_args_list[1] == call(
        1001, format_dead_letter_notify("SAMP.N0000", MAX_SEND_ATTEMPTS)
    )
