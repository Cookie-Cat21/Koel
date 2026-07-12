"""E2-C04: durable delivery_attempted_ok survives restart after Telegram OK + mark fail."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from chime.config import Settings
from chime.domain import AlertEvent, AlertType, PriceSnapshot
from chime.migrate import apply_migrations
from chime.notify import SendResult
from chime.poller import (
    DELIVERY_OK_LEDGER_ENV,
    MARK_DELIVERY_OK_ATTEMPTS,
    PendingSend,
    Poller,
)
from chime.storage import Storage
from tests.conftest import claim_unsent_deque

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


@pytest.mark.asyncio
async def test_deliver_ok_sets_delivery_flag_before_mark_sent() -> None:
    """On SendResult.OK, durable flag is written before mark_alert_sent."""
    order: list[str] = []

    async def track_delivery(log_id: int) -> None:
        order.append("delivery")

    async def track_mark(log_id: int) -> None:
        order.append("mark")

    storage = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock(side_effect=track_delivery)
    storage.mark_alert_sent = AsyncMock(side_effect=track_mark)
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.OK)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller._deliver_one(
        PendingSend(
            log_id=101,
            telegram_id=9,
            message="body",
            already_claimed_new=True,
            rule_id=1,
            event=None,
        )
    )

    storage.mark_delivery_attempted_ok.assert_awaited_once_with(101)
    storage.mark_alert_sent.assert_awaited_once_with(101)
    assert order == ["delivery", "mark"]


@pytest.mark.asyncio
async def test_mark_fail_still_sets_delivery_flag() -> None:
    """Telegram OK + mark_alert_sent fail → delivery_attempted_ok still written."""
    storage = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock(side_effect=RuntimeError("db down"))
    storage.dead_letter = AsyncMock()
    send = AsyncMock(return_value=SendResult.OK)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller._deliver_one(
        PendingSend(
            log_id=102,
            telegram_id=9,
            message="body",
            already_claimed_new=True,
            rule_id=1,
            event=None,
        )
    )

    storage.mark_delivery_attempted_ok.assert_awaited_once_with(102)
    assert storage.mark_alert_sent.await_count == 2
    storage.dead_letter.assert_awaited_once_with(102)


@pytest.mark.asyncio
async def test_all_persist_fail_keeps_delivered_ok_ids_retry_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Telegram OK + mark_delivery, mark_sent, and dead_letter all fail.

    Process must retain the id in ``_delivered_ok_ids`` so ``_retry_unsent``
    does not re-push.
    """
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, str(tmp_path / "delivery-ok.jsonl"))
    storage = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock(side_effect=RuntimeError("delivery flag down"))
    storage.mark_alert_sent = AsyncMock(side_effect=RuntimeError("mark sent down"))
    storage.dead_letter = AsyncMock(side_effect=RuntimeError("dead letter down"))
    storage.claim_unsent_batch = claim_unsent_deque(
        [
            {
                "id": 103,
                "rule_id": 1,
                "message_text": "body",
                "telegram_id": 9,
                "attempt_count": 0,
            }
        ]
    )
    send = AsyncMock(return_value=SendResult.OK)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller._deliver_one(
        PendingSend(
            log_id=103,
            telegram_id=9,
            message="body",
            already_claimed_new=True,
            rule_id=1,
            event=None,
        )
    )

    assert 103 in poller._delivered_ok_ids
    assert storage.mark_delivery_attempted_ok.await_count == MARK_DELIVERY_OK_ATTEMPTS
    assert storage.mark_alert_sent.await_count == 2
    # Once from delivery abandon, once from mark_sent abandon.
    assert storage.dead_letter.await_count == 2

    send.reset_mock()
    await poller._retry_unsent()
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_skips_repush_after_total_post_send_db_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E12-C01: fsync'd Telegram-OK ledger bridges restart when DB marks all fail."""
    ledger = tmp_path / "delivery-ok.jsonl"
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, str(ledger))

    storage = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock(side_effect=RuntimeError("delivery flag down"))
    storage.mark_alert_sent = AsyncMock(side_effect=RuntimeError("mark sent down"))
    storage.dead_letter = AsyncMock(side_effect=RuntimeError("dead letter down"))
    send = AsyncMock(return_value=SendResult.OK)

    first = Poller(_settings(), storage, AsyncMock(), send)
    await first._deliver_one(
        PendingSend(
            log_id=222,
            telegram_id=9,
            message="body after restart",
            already_claimed_new=True,
            rule_id=1,
            event=None,
        )
    )

    assert ledger.exists()
    assert storage.mark_delivery_attempted_ok.await_count == MARK_DELIVERY_OK_ATTEMPTS
    assert storage.mark_alert_sent.await_count == 2

    restarted_storage = AsyncMock()
    restarted_storage.claim_unsent_batch = claim_unsent_deque(
        [
            {
                "id": 222,
                "rule_id": 1,
                "message_text": "body after restart",
                "telegram_id": 9,
                "attempt_count": 0,
            }
        ]
    )
    restarted_storage.mark_delivery_attempted_ok = AsyncMock()
    restarted_storage.mark_alert_sent = AsyncMock()
    restarted_storage.dead_letter = AsyncMock()
    restarted_send = AsyncMock(return_value=SendResult.OK)

    restarted = Poller(_settings(), restarted_storage, AsyncMock(), restarted_send)
    assert restarted._delivered_ok_ids == set()
    await restarted._retry_unsent()

    restarted_send.assert_not_awaited()
    restarted_storage.mark_delivery_attempted_ok.assert_awaited_once_with(222)
    restarted_storage.mark_alert_sent.assert_awaited_once_with(222)
    restarted_storage.dead_letter.assert_not_awaited()
    reconciled = Poller(_settings(), AsyncMock(), AsyncMock(), restarted_send)
    assert reconciled._delivered_ok_tokens == set()


@pytest.mark.asyncio
async def test_restart_skips_repush_when_delivery_flag_set() -> None:
    """New Poller (empty in-memory set) must not re-send if claim excludes flag."""
    storage = AsyncMock()
    # After restart, durable flag keeps the row out of claim_unsent_batch.
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.unsent_alerts = AsyncMock(return_value=[])
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    send = AsyncMock(return_value=SendResult.OK)

    restarted = Poller(_settings(), storage, AsyncMock(), send)
    assert restarted._delivered_ok_ids == set()
    await restarted._retry_unsent()
    send.assert_not_awaited()


@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
@pytest.mark.asyncio
async def test_delivery_attempted_ok_excludes_from_unsent_db() -> None:
    """Postgres: delivery_attempted_ok=TRUE excluded from unsent/claim (E2-C04)."""
    assert DATABASE_URL
    apply_migrations(DATABASE_URL)
    store = Storage(DATABASE_URL, min_size=1, max_size=2)
    await store.open()
    try:
        user_id = await store.ensure_user(telegram_id=9_005_001)
        await store.upsert_stock("DLOK.N0000", "DLOK CO")
        rule = await store.create_alert_rule(user_id, "DLOK.N0000", AlertType.PRICE_ABOVE, 100.0)
        snap = await store.insert_snapshot(
            PriceSnapshot(
                symbol="DLOK.N0000",
                price=105.0,
                previous_close=94.0,
                ts=datetime(2026, 7, 11, 9, 0, tzinfo=UTC),
            )
        )
        assert snap.id is not None
        event = AlertEvent(
            rule_id=rule.id,
            user_id=user_id,
            telegram_id=9_005_001,
            symbol="DLOK.N0000",
            type=AlertType.PRICE_ABOVE,
            trigger="cross_above",
            threshold=100.0,
            current_price=105.0,
            event_key=f"dlok:above:100.0:s{snap.id}",
            snapshot_id=snap.id,
        )
        log_id = await store.claim_alert(event, "telegram ok mark pending")
        assert log_id is not None
        # Claim holds a delivery lease — not visible to unsent until cleared.
        assert all(int(r["id"]) != log_id for r in await store.unsent_alerts())

        await store.mark_delivery_attempted_ok(log_id)
        pending = await store.unsent_alerts()
        assert all(int(r["id"]) != log_id for r in pending)

        if hasattr(store, "claim_unsent_batch"):
            claimed = await store.claim_unsent_batch()
            assert all(int(r["id"]) != log_id for r in claimed)

        # Simulate restart: fresh Poller, empty _delivered_ok_ids, no re-send.
        send = AsyncMock(return_value=SendResult.OK)
        poller = Poller(
            Settings(
                telegram_bot_token="dummy",
                database_url=DATABASE_URL,
                poll_jitter_seconds=0,
            ),
            store,
            AsyncMock(),
            send,
        )
        assert poller._delivered_ok_ids == set()
        await poller._retry_unsent()
        send.assert_not_awaited()
    finally:
        await store.close()
