"""L07: off-hours unsent drain; same-tick skip of already-delivered ids."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from koel.config import Settings
from koel.notify import SendResult
from koel.poller import Poller
from tests.conftest import claim_unsent_deque


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


@pytest.mark.asyncio
async def test_outside_hours_still_retries_unsent() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.claim_unsent_batch = claim_unsent_deque(
        [
            {
                "id": 44,
                "rule_id": 2,
                "message_text": "pending overnight",
                "telegram_id": 1001,
                "attempt_count": 1,
            }
        ]
    )
    storage.mark_alert_sent = AsyncMock()
    send = AsyncMock(return_value=SendResult.OK)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    with patch("koel.poller.is_market_open", return_value=False):
        events = await poller.run_once(force=False)

    assert events == []
    send.assert_awaited_once_with(1001, "pending overnight")
    storage.mark_alert_sent.assert_awaited_once_with(44)
    assert storage.claim_unsent_batch.await_args_list[0].kwargs.get("limit") == 1
    storage.try_advisory_lock.assert_not_awaited()
    storage.advisory_unlock.assert_not_awaited()


@pytest.mark.asyncio
async def test_outside_hours_unsent_drain_attempts_delivery_on_failure() -> None:
    """E16-Q02: outside market hours still attempts delivery for unsent rows."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.claim_unsent_batch = claim_unsent_deque(
        [
            {
                "id": 45,
                "rule_id": 3,
                "message_text": "try overnight",
                "telegram_id": 1002,
                "attempt_count": 0,
            }
        ]
    )
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.FAILED)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    with patch("koel.poller.is_market_open", return_value=False):
        events = await poller.run_once(force=False)

    assert events == []
    send.assert_awaited_once_with(1002, "try overnight")
    storage.mark_alert_attempt.assert_awaited_once_with(45)
    storage.dead_letter.assert_not_awaited()
    storage.mark_alert_sent.assert_not_awaited()
    storage.try_advisory_lock.assert_not_awaited()
    storage.advisory_unlock.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_tick_skips_retry_after_telegram_ok_mark_fail() -> None:
    """If mark+dead_letter fail after OK send, same-tick retry must not re-send."""
    storage = AsyncMock()
    storage.claim_unsent_batch = claim_unsent_deque(
        [
            {
                "id": 55,
                "rule_id": 1,
                "message_text": "body",
                "telegram_id": 9,
                "attempt_count": 0,
            }
        ]
    )
    storage.mark_alert_sent = AsyncMock(side_effect=RuntimeError("db"))
    storage.dead_letter = AsyncMock(side_effect=RuntimeError("db"))
    send = AsyncMock(return_value=SendResult.OK)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    from koel.poller import PendingSend

    await poller._deliver_one(
        PendingSend(
            log_id=55,
            telegram_id=9,
            message="body",
            already_claimed_new=True,
            rule_id=1,
            event=None,
        )
    )
    assert 55 in poller._delivered_ok_ids
    send.reset_mock()
    await poller._retry_unsent()
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_cross_tick_skips_retry_after_telegram_ok_mark_fail() -> None:
    """L08-001: delivered ids survive run_once resets — no re-push next tick."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = claim_unsent_deque(
        [
            {
                "id": 66,
                "rule_id": 1,
                "message_text": "body",
                "telegram_id": 9,
                "attempt_count": 0,
            }
        ]
    )
    storage.mark_alert_sent = AsyncMock(side_effect=RuntimeError("db"))
    storage.dead_letter = AsyncMock(side_effect=RuntimeError("db"))
    send = AsyncMock(return_value=SendResult.OK)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    from koel.poller import PendingSend

    await poller._deliver_one(
        PendingSend(
            log_id=66,
            telegram_id=9,
            message="body",
            already_claimed_new=True,
            rule_id=1,
            event=None,
        )
    )
    assert send.await_count == 1
    send.reset_mock()

    # Simulate next tick off-hours drain — must not re-send id 66.
    with patch("koel.poller.is_market_open", return_value=False):
        await poller.run_once(force=False)
    send.assert_not_awaited()
