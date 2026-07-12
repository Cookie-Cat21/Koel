"""WS-077: Health honesty — poller last_tick_ok / lock_held_skip pins."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from chime.circuit import CircuitOpenError
from chime.config import Settings
from chime.poller import Poller


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


def test_fresh_poller_last_tick_ok_false() -> None:
    """M7: cold start must not report last_tick_ok until a tick succeeds."""
    poller = Poller(_settings(), AsyncMock(), AsyncMock(), AsyncMock())
    assert poller.last_tick_ok is False
    assert poller.last_tick_at is None


@pytest.mark.asyncio
async def test_circuit_open_with_watchlist_sets_last_tick_ok_false() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(side_effect=CircuitOpenError("open"))
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.last_tick_ok is False
    assert poller.lock_held_skip is False
    assert poller.last_error == "poll_degraded"


@pytest.mark.asyncio
async def test_lock_skip_sets_lock_held_skip() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=False)
    storage.advisory_unlock = AsyncMock()

    cse = AsyncMock()
    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.lock_held_skip is True
    assert poller.last_tick_ok is False
    assert poller.last_error == "poll_lock_held"
    assert poller.last_tick_at is not None
    storage.try_advisory_lock.assert_awaited_once()
    storage.advisory_unlock.assert_not_awaited()
    cse.fetch_trade_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_cycle_exception_fail_closes_poll_health_flags() -> None:
    """Mid-tick abort must not leave cold-start True on price/disclosure legs."""
    from datetime import UTC, datetime

    from chime.domain import AlertType, PriceSnapshot
    from tests.conftest import make_disclosure, make_rule

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(
        return_value=[make_rule(type=AlertType.DISCLOSURE, threshold=None)]
    )
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    from chime.domain import PreviousPriceState

    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.upsert_disclosure = AsyncMock(side_effect=RuntimeError("upsert boom"))

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(symbol="JKH.N0000", price=20.0, ts=datetime.now(UTC))
        ]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[make_disclosure()])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    assert poller.price_poll_ok is True
    assert poller.disclosure_poll_ok is True

    events = await poller.run_once(force=True)

    assert events == []
    assert poller.last_tick_ok is False
    assert poller.price_poll_ok is True  # prices completed before disclosure abort
    assert poller.disclosure_poll_ok is False
    assert "upsert boom" in (poller.last_error or "")
