"""Wave92: medium+ poller bugs."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from koel.config import Settings
from koel.domain import PriceSnapshot
from koel.poller import Poller


def _settings(**kwargs: object) -> Settings:
    base: dict[str, object] = {
        "telegram_bot_token": "x",
        "database_url": "postgresql://x",
        "poll_jitter_seconds": 0,
    }
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def _snap(symbol: str = "JKH.N0000") -> PriceSnapshot:
    return PriceSnapshot(symbol=symbol, price=100.0, ts=datetime.now(UTC))


async def _persist_with_ids(snaps: list[PriceSnapshot]) -> list[PriceSnapshot]:
    return [snap.model_copy(update={"id": i}) for i, snap in enumerate(snaps, start=1)]


@pytest.mark.asyncio
async def test_bool_snapshot_retention_days_does_not_delete_snapshots() -> None:
    """``True`` must not be treated as a one-day retention delete window."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(side_effect=_persist_with_ids)
    storage.delete_old_non_watchlist_snapshots = AsyncMock(return_value=3)

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[_snap()])

    settings = _settings()
    object.__setattr__(settings, "snapshot_retention_days", True)
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))

    events, price_ok = await poller._poll_prices()

    assert events == []
    assert price_ok is True
    storage.persist_market_snapshots.assert_awaited_once()
    storage.delete_old_non_watchlist_snapshots.assert_not_awaited()
