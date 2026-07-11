"""Integration: synthetic crossing → claim once → Telegram send once (real Postgres).

Requires DATABASE_URL. Skips if unset.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from chime.domain import AlertType, PriceSnapshot
from chime.migrate import apply_migrations
from chime.poller import Poller
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


class FakeCSE:
    def __init__(self, snaps: list[PriceSnapshot]) -> None:
        self._snaps = snaps
        self.calls = 0

    async def fetch_trade_summary(self) -> list[PriceSnapshot]:
        self.calls += 1
        return list(self._snaps)

    async def fetch_announcements_for_symbol(self, *args: object, **kwargs: object) -> list:
        return []


@pytest.mark.asyncio
async def test_crossing_fires_telegram_once(storage: Storage) -> None:
    user_id = await storage.ensure_user(telegram_id=9_001_001)
    await storage.upsert_stock("TEST.N0000", "TEST CO")
    await storage.add_watch(user_id, "TEST.N0000")
    rule = await storage.create_alert_rule(
        user_id, "TEST.N0000", AlertType.PRICE_ABOVE, 100.0
    )

    # Baseline below threshold (no fire)
    baseline = PriceSnapshot(
        symbol="TEST.N0000",
        price=95.0,
        previous_close=94.0,
        change=1.0,
        change_pct=1.06,
        ts=datetime(2026, 7, 11, 4, 0, tzinfo=UTC),
    )
    await storage.insert_snapshot(baseline)

    sent: list[tuple[int, str]] = []

    async def send(chat_id: int, text: str) -> bool:
        sent.append((chat_id, text))
        return True

    # Crossing snapshot
    cross = PriceSnapshot(
        symbol="TEST.N0000",
        price=105.0,
        previous_close=94.0,
        change=11.0,
        change_pct=11.7,
        ts=datetime(2026, 7, 11, 4, 5, tzinfo=UTC),
    )
    cse = FakeCSE([cross])
    from chime.config import Settings

    settings = Settings(
        telegram_bot_token="dummy",
        database_url=DATABASE_URL,
        poll_interval_seconds=60,
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, send)  # type: ignore[arg-type]
    events = await poller.run_once(force=True)

    assert len(events) == 1
    assert events[0].rule_id == rule.id
    assert len(sent) == 1
    assert sent[0][0] == 9_001_001
    assert "TEST.N0000" in sent[0][1]
    assert "crossed above" in sent[0][1]
    assert "Not financial advice" in sent[0][1]

    # Re-run same price (still above, disarmed) — no duplicate send
    cse2 = FakeCSE(
        [
            PriceSnapshot(
                symbol="TEST.N0000",
                price=106.0,
                previous_close=94.0,
                change=12.0,
                change_pct=12.7,
                ts=datetime(2026, 7, 11, 4, 6, tzinfo=UTC),
            )
        ]
    )
    poller2 = Poller(settings, storage, cse2, send)  # type: ignore[arg-type]
    events2 = await poller2.run_once(force=True)
    assert events2 == []
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_kill_restart_no_double_send(storage: Storage) -> None:
    """CORE-001 / TEST-INT-001: claim+failed send still disarms; one eventual delivery."""
    user_id = await storage.ensure_user(telegram_id=9_001_002)
    await storage.upsert_stock("KILL.N0000", "KILL CO")
    await storage.add_watch(user_id, "KILL.N0000")
    rule = await storage.create_alert_rule(
        user_id, "KILL.N0000", AlertType.PRICE_BELOW, 50.0
    )
    await storage.insert_snapshot(
        PriceSnapshot(
            symbol="KILL.N0000",
            price=55.0,
            previous_close=54.0,
            ts=datetime(2026, 7, 11, 5, 0, tzinfo=UTC),
        )
    )

    attempts = {"n": 0}
    sent_ok: list[str] = []

    async def flaky_send(chat_id: int, text: str) -> bool:
        attempts["n"] += 1
        # Fail the claim-time send AND the same-cycle _retry_unsent
        if attempts["n"] <= 2:
            return False
        sent_ok.append(text)
        return True

    from chime.config import Settings

    settings = Settings(
        telegram_bot_token="dummy",
        database_url=DATABASE_URL,
        poll_jitter_seconds=0,
    )
    cross = PriceSnapshot(
        symbol="KILL.N0000",
        price=45.0,
        previous_close=54.0,
        ts=datetime(2026, 7, 11, 5, 1, tzinfo=UTC),
    )
    poller = Poller(settings, storage, FakeCSE([cross]), flaky_send)  # type: ignore[arg-type]
    events = await poller.run_once(force=True)
    # Claim succeeds even when Telegram fails — event may be non-empty.
    assert len(events) == 1
    assert events[0].rule_id == rule.id
    assert attempts["n"] == 2
    assert sent_ok == []
    alerts = await storage.list_alerts(user_id)
    assert len(alerts) == 1
    assert alerts[0].armed is False

    # Restart mid-cycle recovery: retry unsent → send once
    poller2 = Poller(settings, storage, FakeCSE([]), flaky_send)  # type: ignore[arg-type]
    await poller2._retry_unsent()
    assert len(sent_ok) == 1
    assert "crossed below" in sent_ok[0]

    await poller2._retry_unsent()
    assert len(sent_ok) == 1  # no duplicate
