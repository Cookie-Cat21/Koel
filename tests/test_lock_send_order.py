"""CORE-004: advisory unlock must complete before any Telegram send."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from koel.config import Settings
from koel.domain import AlertType, PreviousPriceState, PriceSnapshot
from koel.notify import SendResult
from koel.poller import PendingSend, Poller
from tests.conftest import claim_unsent_deque, make_disclosure, make_rule


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


@pytest.mark.asyncio
async def test_deferred_send_result_does_not_mark_message_sent() -> None:
    """E17-Q01: RetryAfter/deferred sends remain retryable, not message_sent."""

    async def send(_chat_id: int, _text: str) -> SendResult:
        return SendResult.DEFERRED

    storage = AsyncMock()
    storage.mark_alert_deferred_attempt = AsyncMock(return_value=1)
    storage.mark_alert_sent = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock()

    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller._deliver_one(
        PendingSend(
            log_id=701,
            telegram_id=1001,
            message="retry later",
            already_claimed_new=True,
            rule_id=3,
            symbol="JKH.N0000",
        )
    )

    storage.mark_alert_deferred_attempt.assert_awaited_once_with(701)
    storage.mark_alert_sent.assert_not_awaited()
    storage.mark_delivery_attempted_ok.assert_not_awaited()


@pytest.mark.asyncio
async def test_unlock_before_send_on_new_price_claim() -> None:
    """New claim: unlock awaited before send; send never sees lock_held."""
    lock_held = {"value": False}
    unlock_before_send: list[bool] = []

    async def try_lock(_lock_id: int) -> bool:
        lock_held["value"] = True
        return True

    async def unlock(_lock_id: int) -> None:
        lock_held["value"] = False

    async def send(chat_id: int, text: str) -> SendResult:
        unlock_before_send.append(not lock_held["value"])
        assert lock_held["value"] is False, "Telegram send while advisory lock held"
        return SendResult.OK

    rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
    snap = PriceSnapshot(
        symbol="JKH.N0000",
        price=105.0,
        previous_close=98.0,
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        id=42,
    )

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(side_effect=try_lock)
    storage.advisory_unlock = AsyncMock(side_effect=unlock)
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[rule])
    storage.persist_market_snapshots = AsyncMock(side_effect=lambda snaps: list(snaps))
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=95.0))
    storage.claim_and_disarm = AsyncMock(return_value=501)
    storage.mark_alert_sent = AsyncMock()
    storage.set_rule_armed = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.upsert_disclosure = AsyncMock()

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[snap])
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, send)
    events = await poller.run_once(force=True)

    assert len(events) == 1
    storage.claim_and_disarm.assert_awaited_once()
    storage.set_rule_armed.assert_not_awaited()
    # CSE unlock only — unsent drain no longer re-locks (E2-C05)
    assert storage.advisory_unlock.await_count == 1
    assert unlock_before_send == [True]
    assert lock_held["value"] is False


@pytest.mark.asyncio
async def test_new_claim_unlocks_before_deferred_send_attempt_mark() -> None:
    """Regression: claimed alerts are sent and marked after advisory unlock."""
    order: list[str] = []

    async def try_lock(_lock_id: int) -> bool:
        order.append("lock")
        return True

    async def unlock(_lock_id: int) -> None:
        order.append("unlock")

    async def claim_and_disarm(*_args: object, **_kwargs: object) -> int:
        order.append("claim")
        return 601

    async def send(_chat_id: int, _text: str) -> SendResult:
        order.append("send")
        return SendResult.DEFERRED

    async def mark_attempt(_log_id: int) -> int:
        order.append("attempt")
        return 1

    async def claim_unsent_batch(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        order.append("retry_probe")
        return []

    rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
    snap = PriceSnapshot(
        symbol="JKH.N0000",
        price=105.0,
        previous_close=98.0,
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        id=42,
    )

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(side_effect=try_lock)
    storage.advisory_unlock = AsyncMock(side_effect=unlock)
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[rule])
    storage.persist_market_snapshots = AsyncMock(side_effect=lambda snaps: list(snaps))
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=95.0))
    storage.claim_and_disarm = AsyncMock(side_effect=claim_and_disarm)
    storage.mark_alert_deferred_attempt = AsyncMock(side_effect=mark_attempt)
    storage.mark_alert_sent = AsyncMock()
    storage.set_rule_armed = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(side_effect=claim_unsent_batch)
    storage.upsert_disclosure = AsyncMock()

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[snap])
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, send)
    events = await poller.run_once(force=True)

    assert len(events) == 1
    assert order == ["lock", "claim", "unlock", "send", "attempt", "retry_probe"]
    storage.advisory_unlock.assert_awaited_once()
    storage.mark_alert_deferred_attempt.assert_awaited_once_with(601)
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_no_advisory_rehold() -> None:
    """E2-C05: market-hours unsent drain uses claim lease, not advisory re-lock."""
    lock_held = {"value": False}
    lock_cycles = {"n": 0}
    send_calls: list[str] = []

    async def try_lock(_lock_id: int) -> bool:
        lock_held["value"] = True
        lock_cycles["n"] += 1
        return True

    async def unlock(_lock_id: int) -> None:
        lock_held["value"] = False

    async def send(chat_id: int, text: str) -> SendResult:
        assert lock_held["value"] is False, "unsent send while advisory lock held"
        send_calls.append(text)
        return SendResult.OK

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(side_effect=try_lock)
    storage.advisory_unlock = AsyncMock(side_effect=unlock)
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=lambda snaps: list(snaps))
    storage.claim_unsent_batch = claim_unsent_deque(
        [
            {
                "id": 99,
                "rule_id": 3,
                "telegram_id": 1001,
                "message_text": "retry me",
                "attempt_count": 0,
            }
        ]
    )
    storage.mark_alert_sent = AsyncMock()

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[])
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])
    poller = Poller(_settings(), storage, cse, send)
    await poller.run_once(force=True)

    # CSE phase only
    assert lock_cycles["n"] == 1
    assert storage.advisory_unlock.await_count == 1
    assert send_calls == ["retry me"]
    assert storage.claim_unsent_batch.await_count == 2
    assert storage.claim_unsent_batch.await_args_list[0].kwargs.get("limit") == 1
    storage.mark_alert_sent.assert_awaited_once_with(99)
    assert lock_held["value"] is False


@pytest.mark.asyncio
async def test_disclosure_fetch_all_then_claim_no_sleep_under_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disclosure path: no asyncio.sleep under lock; send after unlock."""
    lock_held = {"value": False}
    sleep_while_locked = 0

    async def try_lock(_lock_id: int) -> bool:
        lock_held["value"] = True
        return True

    async def unlock(_lock_id: int) -> None:
        lock_held["value"] = False

    async def tracking_sleep(_delay: float) -> None:
        nonlocal sleep_while_locked
        if lock_held["value"]:
            sleep_while_locked += 1

    monkeypatch.setattr("koel.poller.asyncio.sleep", tracking_sleep)

    async def send(chat_id: int, text: str) -> SendResult:
        assert lock_held["value"] is False, "disclosure send while lock held"
        return SendResult.OK

    published = datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC)
    created = published - timedelta(hours=2)
    disc_rule = make_rule(
        id=9,
        symbol="COMB.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=created,
    )
    disc = make_disclosure(
        external_id="ann-1",
        symbol="COMB.N0000",
        title="Board Meeting",
        published_at=published,
    ).model_copy(update={"id": 404})

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(side_effect=try_lock)
    storage.advisory_unlock = AsyncMock(side_effect=unlock)
    storage.watched_symbols = AsyncMock(return_value=["COMB.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[disc_rule])
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    storage.upsert_disclosure = AsyncMock(return_value=disc)
    storage.claim_alert = AsyncMock(return_value=9001)
    storage.mark_alert_sent = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(symbol="COMB.N0000", price=90.0, ts=datetime.now(UTC)),
        ]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(
        return_value=[
            make_disclosure(
                external_id="ann-1",
                symbol="COMB.N0000",
                title="Board Meeting",
                published_at=published,
            )
        ]
    )

    poller = Poller(_settings(), storage, cse, send)
    events = await poller.run_once(force=True)

    assert sleep_while_locked == 0
    assert len(events) == 1
    assert storage.advisory_unlock.await_count == 1
    storage.claim_alert.assert_awaited_once()
    storage.mark_alert_sent.assert_awaited_once_with(9001)
