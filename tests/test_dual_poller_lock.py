"""TEST-DPOL-001: two concurrent Poller.run_once share one Postgres advisory lock.

Requires DATABASE_URL. Skips if unset.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from chime.config import Settings
from chime.domain import PriceSnapshot
from chime.migrate import apply_migrations
from chime.poller import Poller
from chime.storage import Storage

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


class HoldingCSE:
    """CSE adapter that blocks inside fetch so the winner holds the poll lock."""

    def __init__(self, entered: asyncio.Event, release: asyncio.Event) -> None:
        self.entered = entered
        self.release = release
        self.calls = 0

    async def fetch_trade_summary(self) -> list[PriceSnapshot]:
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        return []

    async def fetch_announcements_for_symbol(self, *args: object, **kwargs: object) -> list:
        return []


@pytest.mark.asyncio
async def test_dual_poller_run_once_one_holds_lock() -> None:
    apply_migrations(DATABASE_URL)
    store_a = Storage(DATABASE_URL, min_size=1, max_size=2)
    store_b = Storage(DATABASE_URL, min_size=1, max_size=2)
    await store_a.open()
    await store_b.open()
    entered = asyncio.Event()
    release = asyncio.Event()
    try:
        # Need a watched symbol so the lock holder enters _poll_prices → CSE
        # (empty watchlist returns before fetch and unlocks immediately).
        user_id = await store_a.ensure_user(telegram_id=9_002_001)
        await store_a.upsert_stock("DPOL.N0000", "DPOL CO")
        await store_a.add_watch(user_id, "DPOL.N0000")

        cse = HoldingCSE(entered, release)

        async def send(chat_id: int, text: str) -> bool:
            return True

        settings = Settings(
            telegram_bot_token="dummy",
            database_url=DATABASE_URL,
            poll_jitter_seconds=0,
        )
        poller_a = Poller(settings, store_a, cse, send)  # type: ignore[arg-type]
        poller_b = Poller(settings, store_b, cse, send)  # type: ignore[arg-type]

        async def tracked(poller: Poller) -> bool:
            await poller.run_once(force=True)
            if poller.lock_held_skip:
                release.set()
            return poller.lock_held_skip

        skip_a, skip_b = await asyncio.gather(tracked(poller_a), tracked(poller_b))

        assert entered.is_set()
        assert cse.calls == 1
        assert (skip_a, skip_b) in {(True, False), (False, True)}
        assert poller_a.lock_held_skip != poller_b.lock_held_skip
    finally:
        release.set()
        await store_a.close()
        await store_b.close()
