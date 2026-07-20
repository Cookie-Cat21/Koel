"""E2-C05: claim_unsent_batch SKIP LOCKED + lease; unsent drain without advisory lock."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from koel.config import Settings
from koel.domain import AlertEvent, AlertType, PriceSnapshot
from koel.migrate import apply_migrations
from koel.notify import SendResult
from koel.poller import DELIVERY_OK_LEDGER_ENV, MARK_DELIVERY_OK_ATTEMPTS, Poller
from koel.storage import Storage
from tests.conftest import claim_unsent_deque

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
    # limit=1 then empty probe
    assert storage.claim_unsent_batch.await_count == 2
    assert storage.claim_unsent_batch.await_args_list[0].kwargs.get("limit") == 1
    storage.mark_alert_sent.assert_awaited_once_with(44)
    storage.try_advisory_lock.assert_not_awaited()
    storage.advisory_unlock.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_claims_one_at_a_time() -> None:
    """Each unsent row is claimed with limit=1 so its lease starts at send time."""
    storage = AsyncMock()
    storage.claim_unsent_batch = claim_unsent_deque(
        [
            {
                "id": 1,
                "rule_id": 1,
                "message_text": "a",
                "telegram_id": 1001,
                "attempt_count": 0,
            },
            {
                "id": 2,
                "rule_id": 2,
                "message_text": "b",
                "telegram_id": 1002,
                "attempt_count": 0,
            },
        ]
    )
    storage.mark_alert_sent = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock()
    send = AsyncMock(return_value=SendResult.OK)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller._retry_unsent()

    assert send.await_count == 2
    # Two claim+send cycles + one empty probe.
    assert storage.claim_unsent_batch.await_count == 3
    for call in storage.claim_unsent_batch.await_args_list:
        assert call.kwargs.get("limit") == 1


@pytest.mark.asyncio
async def test_retry_unsent_lease_expiry_after_ok_does_not_double_deliver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a lease expires after Telegram OK, durable OK reconciliation skips re-send."""
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, str(tmp_path / "delivery-ok.jsonl"))
    row = {
        "id": 501,
        "rule_id": 7,
        "message_text": "lease can expire after ok",
        "telegram_id": 1001,
        "attempt_count": 0,
    }
    claims = 0

    async def claim_again_after_expiry(*, limit: int = 50, lease_seconds: int = 120) -> list[dict]:
        nonlocal claims
        claims += 1
        assert limit == 1
        assert lease_seconds == 120
        if claims <= 2:
            return [row]
        return []

    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(side_effect=claim_again_after_expiry)
    storage.mark_delivery_attempted_ok = AsyncMock(
        side_effect=[RuntimeError("db down")] * MARK_DELIVERY_OK_ATTEMPTS + [None]
    )
    storage.mark_alert_sent = AsyncMock(
        side_effect=[RuntimeError("db down"), RuntimeError("db down"), None]
    )
    storage.dead_letter = AsyncMock(side_effect=RuntimeError("db down"))
    send = AsyncMock(return_value=SendResult.OK)

    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller._retry_unsent()

    send.assert_awaited_once_with(1001, "lease can expire after ok")
    assert storage.claim_unsent_batch.await_count == 3
    assert storage.mark_delivery_attempted_ok.await_count == MARK_DELIVERY_OK_ATTEMPTS + 1
    assert storage.mark_alert_sent.await_count == 3


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

    send = AsyncMock(return_value=SendResult.OK)
    poller = Poller(_settings(), storage, AsyncMock(), send)
    await poller.run_once(force=True)

    # CSE phase only — unsent no longer re-locks.
    assert lock_cycles["n"] == 1
    assert storage.advisory_unlock.await_count == 1
    send.assert_awaited_once_with(1001, "retry me")
    assert storage.claim_unsent_batch.await_count == 2
    assert storage.claim_unsent_batch.await_args_list[0].kwargs.get("limit") == 1
    storage.mark_alert_sent.assert_awaited_once_with(99)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
async def test_claim_unsent_batch_leases_and_excludes() -> None:
    assert DATABASE_URL
    apply_migrations(DATABASE_URL)
    store = Storage(DATABASE_URL, min_size=1, max_size=2)
    await store.open()
    try:
        user_id = await store.ensure_user(telegram_id=9_005_001)
        await store.upsert_stock("C05A.N0000", "C05A")
        rule = await store.create_alert_rule(user_id, "C05A.N0000", AlertType.PRICE_ABOVE, 10.0)
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
            event_key=f"c05-lease-{rule.id}-{uuid.uuid4().hex[:8]}",
            snapshot_id=snap.id,
        )
        log_id = await store.claim_alert(event, "lease me")
        assert log_id is not None

        # Fresh claim holds a delivery lease — unsent drain must not pick it up.
        assert all(int(r["id"]) != log_id for r in await store.unsent_alerts())
        while_leased = await store.claim_unsent_batch(limit=10, lease_seconds=120)
        assert all(int(r["id"]) != log_id for r in while_leased)

        # Expire the claim lease (failed/deferred send clears it via mark_alert_attempt).
        await store.mark_alert_attempt(log_id)

        # Drain past older unsent pollution from other integration tests (shared DB).
        # Clear leases on non-matching rows so we do not strand them for 120s.
        found = False
        for _ in range(50):
            batch = await store.claim_unsent_batch(limit=10, lease_seconds=120)
            if not batch:
                break
            for row in batch:
                rid = int(row["id"])
                if rid == log_id:
                    found = True
                else:
                    await store.mark_alert_attempt(rid)
            if found:
                break
        assert found, f"expected claim_unsent to pick log_id={log_id}"

        # Active lease from claim_unsent_batch: not in unsent_alerts or a second claim.
        assert all(int(r["id"]) != log_id for r in await store.unsent_alerts())
        second = await store.claim_unsent_batch(limit=10, lease_seconds=120)
        assert all(int(r["id"]) != log_id for r in second)

        await store.mark_alert_sent(log_id)
        assert all(int(r["id"]) != log_id for r in await store.unsent_alerts())
    finally:
        await store.close()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
async def test_claim_alert_lease_blocks_claim_unsent_until_ok_or_expiry() -> None:
    """claim_alert lease: claim_unsent_batch empty until delivery_attempted_ok / expiry."""
    assert DATABASE_URL
    apply_migrations(DATABASE_URL)
    store = Storage(DATABASE_URL, min_size=1, max_size=2)
    await store.open()
    try:
        user_id = await store.ensure_user(telegram_id=9_005_011)
        await store.upsert_stock("C05C.N0000", "C05C")
        rule = await store.create_alert_rule(user_id, "C05C.N0000", AlertType.PRICE_ABOVE, 10.0)
        snap = await store.insert_snapshot(
            PriceSnapshot(
                symbol="C05C.N0000",
                price=12.0,
                previous_close=9.0,
                ts=datetime(2026, 7, 11, 8, 10, tzinfo=UTC),
            )
        )
        assert snap.id is not None

        # Path A: delivery_attempted_ok clears lease and durable-excludes.
        event_ok = AlertEvent(
            rule_id=rule.id,
            user_id=user_id,
            telegram_id=9_005_011,
            symbol="C05C.N0000",
            type=AlertType.PRICE_ABOVE,
            threshold=10.0,
            trigger="cross_above",
            current_price=12.0,
            event_key=f"c05-claim-lease-ok-{rule.id}-{uuid.uuid4().hex[:8]}",
            snapshot_id=snap.id,
        )
        log_ok = await store.claim_alert(event_ok, "in-flight send", lease_seconds=120)
        assert log_ok is not None
        assert all(int(r["id"]) != log_ok for r in await store.unsent_alerts())
        assert all(
            int(r["id"]) != log_ok
            for r in await store.claim_unsent_batch(limit=10, lease_seconds=120)
        )
        await store.mark_delivery_attempted_ok(log_ok)
        assert all(int(r["id"]) != log_ok for r in await store.unsent_alerts())
        assert all(
            int(r["id"]) != log_ok
            for r in await store.claim_unsent_batch(limit=10, lease_seconds=120)
        )

        # Path B: short lease expires → claim_unsent_batch can pick the row up.
        event_exp = AlertEvent(
            rule_id=rule.id,
            user_id=user_id,
            telegram_id=9_005_011,
            symbol="C05C.N0000",
            type=AlertType.PRICE_ABOVE,
            threshold=10.0,
            trigger="cross_above",
            current_price=12.0,
            event_key=f"c05-claim-lease-exp-{rule.id}-{uuid.uuid4().hex[:8]}",
            snapshot_id=snap.id,
        )
        log_exp = await store.claim_alert(event_exp, "lease expires", lease_seconds=1)
        assert log_exp is not None
        assert all(
            int(r["id"]) != log_exp
            for r in await store.claim_unsent_batch(limit=10, lease_seconds=120)
        )
        await asyncio.sleep(1.2)
        claimed = await store.claim_unsent_batch(limit=10, lease_seconds=120)
        assert any(int(r["id"]) == log_exp for r in claimed)
    finally:
        await store.close()


@pytest.mark.asyncio
@pytest.mark.integration
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
        rule = await store_a.create_alert_rule(user_id, "C05B.N0000", AlertType.PRICE_BELOW, 50.0)
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
                event_key=f"c05-skip-{rule.id}-{i}-{uuid.uuid4().hex[:8]}",
                snapshot_id=snap.id,
            )
            log_id = await store_a.claim_alert(event, f"row-{i}")
            assert log_id is not None
            # Clear claim lease so claim_unsent_batch can pick these up.
            await store_a.mark_alert_attempt(log_id)
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
