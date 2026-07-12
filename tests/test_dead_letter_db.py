"""TEST-DL-001: dead-letter path with real Postgres (claim → fail → exclude).

Requires DATABASE_URL. Skips if unset.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from chime.config import Settings
from chime.domain import AlertEvent, AlertType, PriceSnapshot
from chime.migrate import apply_migrations
from chime.poller import MAX_SEND_ATTEMPTS, Poller
from chime.storage import Storage

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


@pytest.fixture
async def storage() -> Storage:
    assert DATABASE_URL
    apply_migrations(DATABASE_URL)
    store = Storage(DATABASE_URL, min_size=1, max_size=2)
    await store.open()
    yield store
    await store.close()


@pytest.mark.asyncio
async def test_dead_letter_excludes_from_unsent_alerts(storage: Storage) -> None:
    user_id = await storage.ensure_user(telegram_id=9_003_001)
    await storage.upsert_stock("DLDB.N0000", "DLDB CO")
    rule = await storage.create_alert_rule(user_id, "DLDB.N0000", AlertType.PRICE_ABOVE, 100.0)
    snap = await storage.insert_snapshot(
        PriceSnapshot(
            symbol="DLDB.N0000",
            price=105.0,
            previous_close=94.0,
            ts=datetime(2026, 7, 11, 7, 0, tzinfo=UTC),
        )
    )
    assert snap.id is not None

    event = AlertEvent(
        rule_id=rule.id,
        user_id=user_id,
        telegram_id=9_003_001,
        symbol="DLDB.N0000",
        type=AlertType.PRICE_ABOVE,
        trigger="cross_above",
        threshold=100.0,
        current_price=105.0,
        event_key=f"dldb:above:100.0:s{snap.id}",
        snapshot_id=snap.id,
    )

    settings = Settings(
        telegram_bot_token="dummy",
        database_url=DATABASE_URL,
        poll_jitter_seconds=0,
    )
    send = AsyncMock(return_value=False)
    cse = AsyncMock()
    poller = Poller(settings, storage, cse, send)

    # Storage claim inserts unsent row (attempt_count=0) with a delivery lease.
    log_id = await storage.claim_alert(event, "dead-letter db integration")
    assert log_id is not None
    # Lease blocks unsent until cleared (failed send path clears via mark_alert_attempt).
    assert all(int(r["id"]) != log_id for r in await storage.unsent_alerts())

    # Poller._record_send_failure increments until MAX_SEND_ATTEMPTS → dead_letter.
    # First failure clears the claim lease and sets attempt_count=1.
    for expected in range(1, MAX_SEND_ATTEMPTS):
        await poller._record_send_failure(log_id, rule_id=rule.id)
        row = next(r for r in await storage.unsent_alerts() if int(r["id"]) == log_id)
        assert int(row["attempt_count"]) == expected

    await poller._record_send_failure(log_id, rule_id=rule.id)
    assert all(int(r["id"]) != log_id for r in await storage.unsent_alerts())

    # Retry path must not resurrect a dead-lettered row.
    await poller._retry_unsent()
    assert all(int(r["id"]) != log_id for r in await storage.unsent_alerts())
