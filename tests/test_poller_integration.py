"""Integration: synthetic crossing → claim once → Telegram send once (real Postgres).

Requires DATABASE_URL. Skips if unset.
"""

from __future__ import annotations

import os
import uuid
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


def _uniq(prefix: str) -> str:
    """Unique CSE-ish symbol so parallel/re-runs do not collide on shared Postgres."""
    return f"{prefix}{uuid.uuid4().hex[:6].upper()}.N0000"


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
    symbol = _uniq("X")
    tg_id = 9_100_000 + (uuid.uuid4().int % 90_000)
    user_id = await storage.ensure_user(telegram_id=tg_id)
    await storage.upsert_stock(symbol, "TEST CO")
    await storage.add_watch(user_id, symbol)
    rule = await storage.create_alert_rule(
        user_id, symbol, AlertType.PRICE_ABOVE, 100.0
    )

    # Baseline below threshold (no fire)
    baseline = PriceSnapshot(
        symbol=symbol,
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
        symbol=symbol,
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
    mine = [s for s in sent if s[0] == tg_id]
    assert len(mine) == 1
    assert symbol in mine[0][1]
    assert "crossed above" in mine[0][1]
    assert "Not financial advice" in mine[0][1]

    # Re-run same price (still above, disarmed) — no duplicate send
    cse2 = FakeCSE(
        [
            PriceSnapshot(
                symbol=symbol,
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
    mine2 = [s for s in sent if s[0] == tg_id]
    assert len(mine2) == 1


@pytest.mark.asyncio
async def test_kill_restart_no_double_send(storage: Storage) -> None:
    """CORE-001 / TEST-INT-001: claim+failed send still disarms; one eventual delivery."""
    symbol = _uniq("K")
    tg_id = 9_200_000 + (uuid.uuid4().int % 90_000)
    user_id = await storage.ensure_user(telegram_id=tg_id)
    await storage.upsert_stock(symbol, "KILL CO")
    await storage.add_watch(user_id, symbol)
    rule = await storage.create_alert_rule(
        user_id, symbol, AlertType.PRICE_BELOW, 50.0
    )
    await storage.insert_snapshot(
        PriceSnapshot(
            symbol=symbol,
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
        symbol=symbol,
        price=45.0,
        previous_close=54.0,
        ts=datetime(2026, 7, 11, 5, 1, tzinfo=UTC),
    )
    poller = Poller(settings, storage, FakeCSE([cross]), flaky_send)  # type: ignore[arg-type]
    events = await poller.run_once(force=True)
    # Claim succeeds even when Telegram fails — event may be non-empty.
    assert len(events) == 1
    assert events[0].rule_id == rule.id
    # Claim-time send + same-cycle unsent drain may attempt ≥2 times; a third
    # attempt can succeed in-cycle after unlock-before-send + retry (E12+).
    assert attempts["n"] >= 2
    alerts = await storage.list_alerts(user_id)
    assert len(alerts) == 1
    assert alerts[0].armed is False

    if not sent_ok:
        # Restart mid-cycle recovery: retry unsent → send once
        poller2 = Poller(settings, storage, FakeCSE([]), flaky_send)  # type: ignore[arg-type]
        await poller2._retry_unsent()
        assert len(sent_ok) == 1
        assert "crossed below" in sent_ok[0]
        await poller2._retry_unsent()
        assert len(sent_ok) == 1  # no duplicate
    else:
        # Delivered during first run_once — still exactly one Telegram body.
        assert len(sent_ok) == 1
        assert "crossed below" in sent_ok[0]
        poller2 = Poller(settings, storage, FakeCSE([]), flaky_send)  # type: ignore[arg-type]
        await poller2._retry_unsent()
        assert len(sent_ok) == 1  # no duplicate
