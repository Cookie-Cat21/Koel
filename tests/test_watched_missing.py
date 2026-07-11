"""E2-C06: watched symbols missing from tradeSummary → price_poll degraded."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from chime.config import Settings
from chime.domain import PriceSnapshot
from chime.poller import Poller


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


def _snap(symbol: str, price: float = 20.0) -> PriceSnapshot:
    return PriceSnapshot(symbol=symbol, price=price, ts=datetime.now(UTC))


@pytest.mark.asyncio
async def test_watched_missing_sets_price_ok_false(capsys: pytest.CaptureFixture[str]) -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000", "COMB.N0000", "SAMP.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.insert_snapshot = AsyncMock(
        side_effect=lambda s: s.model_copy(update={"id": 1})
    )
    from chime.domain import PreviousPriceState

    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    # tradeSummary omits COMB and SAMP — no per-symbol fallback.
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])
    cse.fetch_company_info = AsyncMock()

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.watched_missing == ["COMB.N0000", "SAMP.N0000"]
    assert poller.price_poll_ok is False
    assert poller.last_tick_ok is False
    assert poller.last_error == "poll_degraded"
    cse.fetch_company_info.assert_not_awaited()
    # structlog PrintLogger → stdout
    assert "watched_symbols_missing" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_all_watched_present_clears_missing() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000", "COMB.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.insert_snapshot = AsyncMock(
        side_effect=lambda s: s.model_copy(update={"id": 1})
    )
    from chime.domain import PreviousPriceState

    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[_snap("JKH.N0000"), _snap("COMB.N0000", 90.0)]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    poller.watched_missing = ["STALE.N0000"]
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.watched_missing == []
    assert poller.price_poll_ok is True
    assert poller.last_tick_ok is True
    assert poller.last_error is None


@pytest.mark.asyncio
async def test_empty_watchlist_clears_watched_missing() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    poller.watched_missing = ["JKH.N0000"]
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.watched_missing == []
    assert poller.price_poll_ok is True
    cse.fetch_trade_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_prices_missing_still_evaluates_present() -> None:
    """Partial summary: evaluate present snaps; still degrade on missing."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000", "COMB.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.insert_snapshot = AsyncMock(
        side_effect=lambda s: s.model_copy(update={"id": 42})
    )
    from chime.domain import PreviousPriceState

    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is False
    assert poller.watched_missing == ["COMB.N0000"]
    storage.insert_snapshot.assert_awaited_once()
    assert storage.insert_snapshot.await_args.args[0].symbol == "JKH.N0000"
