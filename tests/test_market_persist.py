"""Market-wide persist on every price poll (empty watchlist still fetches)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from chime.briefs import BriefSettings, briefs_enabled
from chime.config import Settings
from chime.domain import PreviousPriceState, PriceSnapshot
from chime.poller import Poller


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


def _snap(symbol: str, price: float = 20.0) -> PriceSnapshot:
    return PriceSnapshot(symbol=symbol, price=price, ts=datetime.now(UTC))


def _persist_with_ids(snaps: list[PriceSnapshot]) -> list[PriceSnapshot]:
    return [s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)]


@pytest.mark.asyncio
async def test_empty_watchlist_persists_market() -> None:
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)
    storage.get_previous_state = AsyncMock()

    board = [_snap("JKH.N0000"), _snap("COMB.N0000", 90.0)]
    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=board)

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is True
    assert poller.watched_missing == []
    cse.fetch_trade_summary.assert_awaited_once()
    storage.persist_market_snapshots.assert_awaited_once_with(board)
    storage.get_previous_state.assert_not_awaited()
    storage.active_rules_for_symbols.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_watchlist_empty_board_price_ok_false() -> None:
    """HTTP-OK empty tradeSummary with no watchlist is still a failed browse persist."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is False
    assert poller.trade_summary_empty_ok is True
    assert poller.trade_summary_count == 0
    storage.persist_market_snapshots.assert_awaited_once_with([])


@pytest.mark.asyncio
async def test_empty_watchlist_persist_failure_degrades_tick() -> None:
    """DB write failure must set last_tick_ok False even with an empty watchlist."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=RuntimeError("db down"))

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.price_poll_ok is False
    assert poller.last_tick_ok is False
    assert poller.last_error == "poll_degraded"
    assert poller.watched_missing == []


@pytest.mark.asyncio
async def test_watchlist_persist_failure_price_ok_false(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Persist failure with a non-empty watchlist returns price_ok False (fail closed)."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000", "COMB.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=RuntimeError("db down"))
    storage.get_previous_state = AsyncMock()

    board = [_snap("JKH.N0000"), _snap("COMB.N0000", 90.0)]
    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=board)

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    poller.watched_missing = ["STALE.N0000"]
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is False
    # Fetch succeeded — recompute missing from the board (both watched present).
    assert poller.watched_missing == []
    storage.persist_market_snapshots.assert_awaited_once_with(board)
    storage.get_previous_state.assert_not_awaited()
    storage.active_rules_for_symbols.assert_not_awaited()
    assert "market_persist_failed" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_watchlist_persist_failure_degrades_tick() -> None:
    """run_once: persist failure with watchlist → price_poll_ok / last_tick_ok False."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=RuntimeError("db down"))

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.price_poll_ok is False
    assert poller.last_tick_ok is False
    assert poller.last_error == "poll_degraded"


@pytest.mark.asyncio
async def test_empty_board_empty_watchlist_still_attempts_persist() -> None:
    """Empty tradeSummary + empty watchlist: persist [] then price_ok False."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    poller.watched_missing = ["STALE.N0000"]
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is False
    assert poller.watched_missing == []
    assert poller.trade_summary_empty_ok is True
    assert poller.trade_summary_count == 0
    cse.fetch_trade_summary.assert_awaited_once()
    storage.persist_market_snapshots.assert_awaited_once_with([])
    storage.active_rules_for_symbols.assert_not_awaited()


@pytest.mark.asyncio
async def test_circuit_open_empty_watchlist_degrades_tick() -> None:
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    from chime.circuit import CircuitOpenError

    cse.fetch_trade_summary = AsyncMock(side_effect=CircuitOpenError("open"))
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)

    assert events == []
    assert poller.price_poll_ok is False
    assert poller.last_tick_ok is False
    assert poller.last_error == "poll_degraded"


@pytest.mark.asyncio
async def test_persist_only_evaluates_watched() -> None:
    """Two snaps in summary, one watched — persist both; evaluate only watched."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))

    board = [_snap("JKH.N0000"), _snap("COMB.N0000", 90.0)]
    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=board)

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is True
    assert poller.watched_missing == []
    storage.persist_market_snapshots.assert_awaited_once_with(board)
    storage.get_previous_state.assert_awaited_once()
    assert storage.get_previous_state.await_args.args[0] == "JKH.N0000"
    assert storage.get_previous_state.await_args.kwargs["before_id"] == 1


def test_briefs_disabled_by_default() -> None:
    assert briefs_enabled(BriefSettings()) is False
    assert BriefSettings.from_env().enabled is False


@pytest.mark.asyncio
async def test_circuit_open_clears_stale_watched_missing() -> None:
    """Fetch failure must not leave a prior tick's missing list on health."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    cse = AsyncMock()
    from chime.circuit import CircuitOpenError

    cse.fetch_trade_summary = AsyncMock(side_effect=CircuitOpenError("open"))

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    poller.watched_missing = ["STALE.N0000"]
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is False
    assert poller.watched_missing == []


@pytest.mark.asyncio
async def test_persist_failure_updates_missing_from_fetched_board() -> None:
    """DB persist fail after a successful fetch still reports CSE gaps honestly."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000", "COMB.N0000"])
    storage.persist_market_snapshots = AsyncMock(side_effect=RuntimeError("db down"))

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    poller.watched_missing = ["STALE.N0000"]
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is False
    assert poller.watched_missing == ["COMB.N0000"]
    assert poller.trade_summary_count == 1


@pytest.mark.asyncio
async def test_retention_off_skips_cleanup() -> None:
    """Default SNAPSHOT_RETENTION_DAYS=0 does not call retention delete."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)
    storage.delete_old_non_watchlist_snapshots = AsyncMock(return_value=0)

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is True
    storage.delete_old_non_watchlist_snapshots.assert_not_awaited()


@pytest.mark.asyncio
async def test_retention_runs_after_successful_persist() -> None:
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)
    storage.delete_old_non_watchlist_snapshots = AsyncMock(return_value=12)
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))

    board = [_snap("JKH.N0000"), _snap("COMB.N0000", 90.0)]
    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=board)

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        snapshot_retention_days=7,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is True
    storage.persist_market_snapshots.assert_awaited_once_with(board)
    storage.delete_old_non_watchlist_snapshots.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_retention_zero_deleted_skips_info_log(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """deleted=0 still runs cleanup but must not emit snapshot_retention_deleted."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)
    storage.delete_old_non_watchlist_snapshots = AsyncMock(return_value=0)

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        snapshot_retention_days=7,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is True
    storage.delete_old_non_watchlist_snapshots.assert_awaited_once_with(7)
    assert "snapshot_retention_deleted" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_retention_failure_is_fail_soft(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Retention errors must not degrade price_ok / skip rule eval."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)
    storage.delete_old_non_watchlist_snapshots = AsyncMock(side_effect=RuntimeError("cleanup boom"))
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))

    board = [_snap("JKH.N0000")]
    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=board)

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        snapshot_retention_days=14,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is True
    storage.get_previous_state.assert_awaited_once()
    assert "snapshot_retention_failed" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_retention_skipped_when_persist_fails() -> None:
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=RuntimeError("db down"))
    storage.delete_old_non_watchlist_snapshots = AsyncMock(return_value=0)

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap("JKH.N0000")])

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        snapshot_retention_days=7,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is False
    storage.delete_old_non_watchlist_snapshots.assert_not_awaited()
