"""Sector backfill normalize / gate — no live CSE."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.config import Settings
from chime.sector_backfill import SectorBackfillResult, run_sector_backfill


@pytest.mark.asyncio
async def test_sector_backfill_disabled_without_force() -> None:
    settings = MagicMock(spec=Settings)
    settings.sector_backfill_enabled = False
    storage = AsyncMock()
    cse = AsyncMock()
    result = await run_sector_backfill(
        settings=settings, storage=storage, cse=cse, force=False
    )
    assert result == SectorBackfillResult(0, 0, 0, 0)
    cse.fetch_company_sector.assert_not_called()


@pytest.mark.asyncio
async def test_sector_backfill_force_updates() -> None:
    settings = MagicMock(spec=Settings)
    settings.sector_backfill_enabled = False
    settings.sector_backfill_sleep_seconds = 0.0
    storage = AsyncMock()
    storage.list_symbols_missing_sector = AsyncMock(
        return_value=["JKH.N0000", "COMB.N0000"]
    )
    storage.upsert_stock = AsyncMock()
    cse = AsyncMock()
    cse.fetch_company_sector = AsyncMock(side_effect=["Capital Goods", None])

    result = await run_sector_backfill(
        settings=settings,
        storage=storage,
        cse=cse,
        force=True,
        sleep_seconds=0.0,
    )
    assert result.symbols_targeted == 2
    assert result.symbols_updated == 1
    assert result.symbols_skipped == 1
    storage.upsert_stock.assert_awaited_once_with(
        "JKH.N0000", sector="Capital Goods"
    )
