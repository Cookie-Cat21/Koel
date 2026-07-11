"""H3: send OK + mark_alert_sent raises → still claimed; no send-failure path."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from chime.config import Settings
from chime.domain import AlertEvent, AlertType
from chime.poller import Poller


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


def _event() -> AlertEvent:
    return AlertEvent(
        rule_id=1,
        user_id=10,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        trigger="cross_above",
        threshold=100.0,
        current_price=105.0,
        event_key="above:100.0:s42",
        snapshot_id=42,
    )


@pytest.mark.asyncio
async def test_claim_mark_fail_still_returns_true_no_send_failure() -> None:
    """Telegram OK but mark raises twice → return True, dead-letter, no attempt bump."""
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=77)
    storage.mark_alert_sent = AsyncMock(side_effect=RuntimeError("db down"))
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=True)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    claimed = await poller._claim_and_send(_event())

    assert claimed is True
    assert storage.mark_alert_sent.await_count == 2
    storage.dead_letter.assert_awaited_once_with(77)
    storage.mark_alert_attempt.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_mark_fail_retry_succeeds_treats_as_sent() -> None:
    """First mark fails, retry succeeds → treat as sent; no dead-letter."""
    storage = AsyncMock()
    storage.claim_alert = AsyncMock(return_value=88)
    storage.mark_alert_sent = AsyncMock(
        side_effect=[RuntimeError("transient"), None]
    )
    storage.mark_alert_attempt = AsyncMock()
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=True)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    claimed = await poller._claim_and_send(_event())

    assert claimed is True
    assert storage.mark_alert_sent.await_count == 2
    storage.dead_letter.assert_not_awaited()
    storage.mark_alert_attempt.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_mark_fail_dead_letters_no_attempt() -> None:
    """Retry path must use best-effort mark (H3 parity) — no bare mark_alert_sent."""
    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(
        return_value=[
            {
                "id": 91,
                "rule_id": 3,
                "message_text": "retry body",
                "telegram_id": 1001,
                "attempt_count": 1,
            }
        ]
    )
    storage.mark_alert_sent = AsyncMock(side_effect=RuntimeError("db down"))
    storage.mark_alert_attempt = AsyncMock()
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=True)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller._retry_unsent()

    assert storage.mark_alert_sent.await_count == 2
    storage.dead_letter.assert_awaited_once_with(91)
    storage.mark_alert_attempt.assert_not_awaited()
