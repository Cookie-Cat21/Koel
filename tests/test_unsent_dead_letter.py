"""WS-006 / M4: dead-letter unsent alerts after send or deferred ceilings."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from chime.config import Settings
from chime.domain import AlertEvent, AlertType
from chime.notify import SendResult
from chime.poller import MAX_DEFERRED_ATTEMPTS, MAX_SEND_ATTEMPTS, Poller


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


def _event(*, rule_id: int = 1, telegram_id: int = 1001) -> AlertEvent:
    return AlertEvent(
        rule_id=rule_id,
        user_id=10,
        telegram_id=telegram_id,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        trigger="cross_above",
        threshold=100.0,
        current_price=105.0,
        event_key="above:100.0:s42",
        snapshot_id=42,
    )


def _poller(*, send: AsyncMock, storage: AsyncMock | None = None) -> Poller:
    storage = storage or AsyncMock()
    cse = AsyncMock()
    return Poller(_settings(), storage, cse, send)


@pytest.mark.asyncio
async def test_claim_and_send_failure_increments_attempt() -> None:
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=77)
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=False)

    poller = _poller(send=send, storage=storage)
    claimed = await poller._claim_and_send(_event())

    # Claim succeeded — True even when Telegram send failed (disarm may proceed).
    assert claimed is True
    storage.mark_alert_attempt.assert_awaited_once_with(77)
    storage.dead_letter.assert_not_awaited()
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_and_send_dead_letters_at_max_attempts() -> None:
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=88)
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_SEND_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=False)

    poller = _poller(send=send, storage=storage)
    claimed = await poller._claim_and_send(_event(rule_id=9))

    assert claimed is True
    storage.mark_alert_attempt.assert_awaited_once_with(88)
    storage.dead_letter.assert_awaited_once_with(88)


@pytest.mark.asyncio
async def test_claim_conflict_returns_false() -> None:
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=None)
    send = AsyncMock(return_value=True)

    poller = _poller(send=send, storage=storage)
    claimed = await poller._claim_and_send(_event())

    assert claimed is False
    send.assert_not_awaited()
    storage.mark_alert_sent.assert_not_awaited()
    storage.mark_alert_attempt.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_failure_increments_and_dead_letters() -> None:
    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(
        return_value=[
            {
                "id": 11,
                "rule_id": 2,
                "message_text": "alert body",
                "telegram_id": 1001,
                "attempt_count": 4,
            }
        ]
    )
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_SEND_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=False)

    poller = _poller(send=send, storage=storage)
    await poller._retry_unsent()

    send.assert_awaited_once_with(1001, "alert body")
    storage.mark_alert_attempt.assert_awaited_once_with(11)
    storage.dead_letter.assert_awaited_once_with(11)
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_success_marks_sent_without_attempt() -> None:
    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(
        return_value=[
            {
                "id": 12,
                "rule_id": 3,
                "message_text": "ok",
                "telegram_id": 2002,
                "attempt_count": 2,
            }
        ]
    )
    send = AsyncMock(return_value=True)

    poller = _poller(send=send, storage=storage)
    await poller._retry_unsent()

    storage.mark_alert_sent.assert_awaited_once_with(12)
    storage.mark_alert_attempt.assert_not_awaited()
    storage.dead_letter.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_below_max_does_not_dead_letter() -> None:
    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(
        return_value=[
            {
                "id": 13,
                "rule_id": 4,
                "message_text": "pending",
                "telegram_id": 3003,
                "attempt_count": 1,
            }
        ]
    )
    storage.mark_alert_attempt = AsyncMock(return_value=2)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=False)

    poller = _poller(send=send, storage=storage)
    await poller._retry_unsent()

    storage.mark_alert_attempt.assert_awaited_once_with(13)
    storage.dead_letter.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_and_send_deferred_increments_attempt() -> None:
    """RetryAfter deferred bumps attempt_count (M4 ceiling), not FAILED threshold."""
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=99)
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.DEFERRED)

    poller = _poller(send=send, storage=storage)
    claimed = await poller._claim_and_send(_event())

    assert claimed is True
    storage.mark_alert_attempt.assert_awaited_once_with(99)
    storage.dead_letter.assert_not_awaited()
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_and_send_deferred_dead_letters_at_max() -> None:
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=101)
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_DEFERRED_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.DEFERRED)

    poller = _poller(send=send, storage=storage)
    claimed = await poller._claim_and_send(_event(rule_id=7))

    assert claimed is True
    storage.mark_alert_attempt.assert_awaited_once_with(101)
    storage.dead_letter.assert_awaited_once_with(101)


@pytest.mark.asyncio
async def test_claim_and_send_deferred_below_max_does_not_dead_letter() -> None:
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=102)
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_SEND_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.DEFERRED)

    poller = _poller(send=send, storage=storage)
    claimed = await poller._claim_and_send(_event())

    assert claimed is True
    storage.mark_alert_attempt.assert_awaited_once_with(102)
    # FAILED ceiling (5) must not dead-letter deferred path.
    storage.dead_letter.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_and_send_network_error_increments_attempt() -> None:
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=100)
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.FAILED)

    poller = _poller(send=send, storage=storage)
    claimed = await poller._claim_and_send(_event())

    assert claimed is True
    storage.mark_alert_attempt.assert_awaited_once_with(100)
    storage.dead_letter.assert_not_awaited()
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_deferred_increments_attempt() -> None:
    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(
        return_value=[
            {
                "id": 14,
                "rule_id": 5,
                "message_text": "wait",
                "telegram_id": 4004,
                "attempt_count": 0,
            }
        ]
    )
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.DEFERRED)

    poller = _poller(send=send, storage=storage)
    await poller._retry_unsent()

    send.assert_awaited_once_with(4004, "wait")
    storage.mark_alert_attempt.assert_awaited_once_with(14)
    storage.dead_letter.assert_not_awaited()
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_deferred_dead_letters_at_max() -> None:
    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(
        return_value=[
            {
                "id": 15,
                "rule_id": 6,
                "message_text": "wait forever",
                "telegram_id": 5005,
                "attempt_count": 29,
            }
        ]
    )
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_DEFERRED_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.DEFERRED)

    poller = _poller(send=send, storage=storage)
    await poller._retry_unsent()

    storage.mark_alert_attempt.assert_awaited_once_with(15)
    storage.dead_letter.assert_awaited_once_with(15)
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_send_deferred_dead_letters_at_ceiling() -> None:
    storage = AsyncMock()
    storage.mark_alert_attempt = AsyncMock(return_value=MAX_DEFERRED_ATTEMPTS)
    storage.dead_letter = AsyncMock()
    send = AsyncMock()

    poller = _poller(send=send, storage=storage)
    await poller._record_send_deferred(44, rule_id=8)

    storage.mark_alert_attempt.assert_awaited_once_with(44)
    storage.dead_letter.assert_awaited_once_with(44)


def test_max_send_attempts_is_five() -> None:
    assert MAX_SEND_ATTEMPTS == 5


def test_max_deferred_attempts_is_thirty() -> None:
    assert MAX_DEFERRED_ATTEMPTS == 30
