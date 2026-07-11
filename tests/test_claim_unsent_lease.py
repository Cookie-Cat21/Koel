"""E2-C05: claim_unsent_batch SKIP LOCKED + lease; unsent drain without advisory lock."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from chime.config import Settings
from chime.domain import AlertEvent, AlertType, PriceSnapshot
from chime.migrate import apply_migrations
from chime.notify import SendResult
from chime.poller import Poller
from chime.storage import Storage

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


@pytest.mark.asyncio
async def test_retry_unsent_uses_claim_batch_not_advisory_lock() -> None:
    """Unsent drain claims via lease; does not acquire the poll advisory lock."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(
        return_value=[
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
    with patch("chime.poller.is_market_open", return_value=False):
        events = await poller.run_once(force=False)

    assert events == []
    send.assert_awaited_once_with(1001, "pending overnight")
    storage.claim_unsent_batch.assert_awaited_once()
    storage.mark_alert_sent.assert_awaited_once_with(44)
    storage.try_advisory_lock.assert_not_awaited()
    storage.advisory_unlock.assert_not_awaited()


@pytest.mark.asyncio
async def test_market_hours_unsent_no_advisory_rehold() -> None:
    """After CSE unlock, unsent drain must not re-acquire advisory (E2-C05)."""
    lock_cycles = {"n": 0}

    async def try_lock(_lock_id: int) -> bool:
        lock_cycles["n"] += 1
        return True

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(side_effect=try_lock)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(
        return_value=[
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

    send = AsyncMock(return_value=SendResult.OK)
    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller.run_once(force=True)

    # CSE phase only — unsent no longer re-locks.
    assert lock_cycles["n"] == 1
    assert storage.advisory_unlock.await_count == 1
    send.assert_awaited_once_with(1001, "retry me")
    storage.claim_unsent_batch.assert_awaited_once()
    storage.mark_alert_sent.assert_awaited_once_with(99)


@pytest.mark.asyncio
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
async def test_claim_unsent_batch_leases_and_excludes() -> None:
    assert DATABASE_URL
    apply_migrations(DATABASE_URL)
    store = Storage(DATABASE_URL, min_size=1, max_size=2)
    await store.open()
    try:
        user_id = await store.ensure_user(telegram_id=9_005_001)
        await store.upsert_stock("C05A.N0000", "C05A")
        rule = await store.create_alert_rule(
            user_id, "C05A.N0000", AlertType.PRICE_ABOVE, 10.0
        )
        snap = await store.insert_snapshot(
            PriceSnapshot(
                symbol="C05A.N0000",
                price=12.0,
                previous_close=9.0,
                ts=datetime(2026, 7, 11, 8, 0, tzinfo=UTC),
            )
        )
        assert snap.id is not None
        event = AlertEvent(
            rule_id=rule.id,
            user_id=user_id,
            telegram_id=9_005_001,
            symbol="C05A.N0000",
            type=AlertType.PRICE_ABOVE,
            threshold=10.0,
            trigger="cross_above",
            current_price=12.0,
            event_key=f"c05-lease-{rule.id}",
            snapshot_id=snap.id,
        )
        log_id = await store.claim_alert(event, "lease me")
        assert log_id is not None

        first = await store.claim_unsent_batch(limit=10, lease_seconds=120)
        assert any(int(r["id"]) == log_id for r in first)

        # Active lease: not in unsent_alerts or a second claim.
        assert all(int(r["id"]) != log_id for r in await store.unsent_alerts())
        second = await store.claim_unsent_batch(limit=10, lease_seconds=120)
        assert all(int(r["id"]) != log_id for r in second)

        await store.mark_alert_sent(log_id)
        assert all(int(r["id"]) != log_id for r in await store.unsent_alerts())
    finally:
        await store.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
async def test_claim_unsent_batch_skip_locked_concurrent() -> None:
    """Two concurrent claimers get disjoint rows (SKIP LOCKED)."""
    assert DATABASE_URL
    apply_migrations(DATABASE_URL)
    store_a = Storage(DATABASE_URL, min_size=1, max_size=2)
    store_b = Storage(DATABASE_URL, min_size=1, max_size=2)
    await store_a.open()
    await store_b.open()
    try:
        user_id = await store_a.ensure_user(telegram_id=9_005_002)
        await store_a.upsert_stock("C05B.N0000", "C05B")
        rule = await store_a.create_alert_rule(
            user_id, "C05B.N0000", AlertType.PRICE_BELOW, 50.0
        )
        snap = await store_a.insert_snapshot(
            PriceSnapshot(
                symbol="C05B.N0000",
                price=40.0,
                previous_close=55.0,
                ts=datetime(2026, 7, 11, 8, 5, tzinfo=UTC),
            )
        )
        assert snap.id is not None
        ids: list[int] = []
        for i in range(4):
            event = AlertEvent(
                rule_id=rule.id,
                user_id=user_id,
                telegram_id=9_005_002,
                symbol="C05B.N0000",
                type=AlertType.PRICE_BELOW,
                threshold=50.0,
                trigger="cross_below",
                current_price=40.0,
                event_key=f"c05-skip-{rule.id}-{i}",
                snapshot_id=snap.id,
            )
            log_id = await store_a.claim_alert(event, f"row-{i}")
            assert log_id is not None
            ids.append(log_id)

        batch_a, batch_b = await asyncio.gather(
            store_a.claim_unsent_batch(limit=2, lease_seconds=120),
            store_b.claim_unsent_batch(limit=2, lease_seconds=120),
        )
        got_a = {int(r["id"]) for r in batch_a}
        got_b = {int(r["id"]) for r in batch_b}
        assert got_a.isdisjoint(got_b)
        assert got_a | got_b <= set(ids)
        assert len(got_a) + len(got_b) == 4
    finally:
        await store_a.close()
        await store_b.close()
