"""Resilience: poller survives CSE failures without crashing the loop."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from chime.circuit import CircuitOpenError
from chime.config import Settings
from chime.domain import AlertType, PriceSnapshot
from chime.poller import Poller, is_market_open
from tests.conftest import make_rule


def test_market_hours_weekday_boundaries() -> None:
    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        market_tz="Asia/Colombo",
        market_open="09:30",
        market_close="14:30",
    )
    # Friday 09:30 SLT = 04:00 UTC
    open_dt = datetime(2026, 7, 10, 4, 0, tzinfo=UTC)
    assert is_market_open(open_dt, settings)
    # Friday 14:31 SLT = 09:01 UTC
    after = datetime(2026, 7, 10, 9, 1, tzinfo=UTC)
    assert not is_market_open(after, settings)
    # Saturday
    sat = datetime(2026, 7, 11, 5, 0, tzinfo=UTC)
    assert not is_market_open(sat, settings)


@pytest.mark.asyncio
async def test_poller_survives_circuit_open() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(side_effect=CircuitOpenError("open"))
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    sent: list = []

    async def send(chat_id: int, text: str) -> bool:
        sent.append(text)
        return True

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, send)
    events = await poller.run_once(force=True)
    assert events == []
    assert poller.last_tick_ok is False  # watchlist present + price fetch failed


@pytest.mark.asyncio
async def test_poller_survives_junk_then_ok() -> None:
    disc_rule = make_rule(type=AlertType.DISCLOSURE, threshold=None)
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[disc_rule])
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    storage.get_previous_state = AsyncMock()
    from chime.domain import PreviousPriceState

    storage.get_previous_state.return_value = PreviousPriceState(price=None)
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(
                symbol="JKH.N0000",
                price=20.0,
                ts=datetime.now(UTC),
            )
        ]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(side_effect=RuntimeError("html error page"))

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)
    assert events == []
    assert poller.last_tick_at is not None
    assert poller.disclosure_poll_ok is False
    assert poller.last_tick_ok is False


@pytest.mark.asyncio
async def test_disclosure_poll_skips_price_only_symbols() -> None:
    """WS-020: no announcement HTTP when watchlist has only price rules."""
    price_rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0)
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000", "COMB.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[price_rule])
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    from chime.domain import PreviousPriceState

    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(symbol="JKH.N0000", price=20.0, ts=datetime.now(UTC)),
            PriceSnapshot(symbol="COMB.N0000", price=90.0, ts=datetime.now(UTC)),
        ]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)
    assert events == []
    cse.fetch_announcements_for_symbol.assert_not_called()
    assert poller.disclosure_poll_ok is True
    assert poller.last_tick_ok is True


@pytest.mark.asyncio
async def test_disclosure_poll_fetches_only_disclosure_symbols() -> None:
    """WS-020: announcement fetch limited to symbols with disclosure rules."""
    price_rule = make_rule(id=1, symbol="JKH.N0000", type=AlertType.PRICE_ABOVE, threshold=100.0)
    disc_rule = make_rule(id=2, symbol="COMB.N0000", type=AlertType.DISCLOSURE, threshold=None)
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000", "COMB.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[price_rule, disc_rule])
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    from chime.domain import PreviousPriceState

    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    storage.upsert_disclosure = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(symbol="JKH.N0000", price=20.0, ts=datetime.now(UTC)),
            PriceSnapshot(symbol="COMB.N0000", price=90.0, ts=datetime.now(UTC)),
        ]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    await poller.run_once(force=True)
    cse.fetch_announcements_for_symbol.assert_called_once()
    call_symbol = cse.fetch_announcements_for_symbol.call_args.args[0]
    assert call_symbol == "COMB.N0000"
