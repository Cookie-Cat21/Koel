"""M1: unsent_alerts excludes rows whose alert_rules.active is FALSE."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from chime.domain import AlertEvent, AlertType, PriceSnapshot
from chime.migrate import apply_migrations
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
async def test_unsent_alerts_filters_inactive_rules(storage: Storage) -> None:
    user_id = await storage.ensure_user(telegram_id=9_004_001)
    await storage.upsert_stock("UNSA.N0000", "UNSA CO")
    rule = await storage.create_alert_rule(user_id, "UNSA.N0000", AlertType.PRICE_ABOVE, 100.0)
    snap = await storage.insert_snapshot(
        PriceSnapshot(
            symbol="UNSA.N0000",
            price=105.0,
            previous_close=94.0,
            ts=datetime(2026, 7, 11, 8, 0, tzinfo=UTC),
        )
    )
    assert snap.id is not None

    event = AlertEvent(
        rule_id=rule.id,
        user_id=user_id,
        telegram_id=9_004_001,
        symbol="UNSA.N0000",
        type=AlertType.PRICE_ABOVE,
        trigger="cross_above",
        threshold=100.0,
        current_price=105.0,
        event_key=f"unsa:above:100.0:s{snap.id}",
        snapshot_id=snap.id,
    )
    log_id = await storage.claim_alert(event, "pending while active")
    assert log_id is not None
    # Clear claim lease so the row is visible to unsent_alerts.
    await storage.mark_alert_attempt(log_id)
    assert any(int(r["id"]) == log_id for r in await storage.unsent_alerts())

    deactivated = await storage.deactivate_alert(user_id, rule.id)
    assert deactivated is True

    pending = await storage.unsent_alerts()
    assert all(int(r["id"]) != log_id for r in pending)
