"""Notices backfill gate — no live CSE."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.config import Settings
from koel.domain import MarketNotice
from koel.notices_backfill import NoticesBackfillResult, run_notices_backfill


@pytest.mark.asyncio
async def test_notices_backfill_disabled_without_force() -> None:
    settings = MagicMock(spec=Settings)
    settings.notices_backfill_enabled = False
    storage = AsyncMock()
    cse = AsyncMock()
    result = await run_notices_backfill(
        settings=settings, storage=storage, cse=cse, force=False
    )
    assert result == NoticesBackfillResult(0, 0, 0, 0)
    cse.fetch_buy_in_announcements.assert_not_called()


@pytest.mark.asyncio
async def test_notices_backfill_force_persists() -> None:
    settings = MagicMock(spec=Settings)
    settings.notices_backfill_enabled = False
    notice = MarketNotice(
        external_id="n1",
        notice_type="non_compliance",
        symbol=None,
        title="SOME CO PLC",
        body="SOME CO PLC — late filing",
        url="https://www.cse.lk/announcements#n1",
        published_at=datetime(2026, 7, 1, tzinfo=UTC),
        seen_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    storage = AsyncMock()
    storage.resolve_symbol_by_company_name = AsyncMock(return_value="SOME.N0000")
    storage.upsert_market_notice = AsyncMock(return_value=notice)
    cse = AsyncMock()
    cse.fetch_buy_in_announcements = AsyncMock(return_value=[])
    cse.fetch_non_compliance_announcements = AsyncMock(return_value=[notice])
    cse.fetch_market_notifications = AsyncMock(return_value=[])

    result = await run_notices_backfill(
        settings=settings, storage=storage, cse=cse, force=True
    )
    assert result.fetched == 1
    assert result.persisted == 1
    assert result.resolved_symbols == 1
    storage.upsert_market_notice.assert_awaited()
