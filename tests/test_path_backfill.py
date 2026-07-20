"""Daily path normalize + backfill gate — no live CSE."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from koel.adapters.cse import (
    CHART_PERIOD_1Y,
    CHART_PERIOD_INTRADAY,
    ChartPointRow,
    TradeSummaryRow,
    chart_point_to_daily_bar,
    chart_point_to_intraday_snapshot,
    chart_trade_date,
    trade_row_to_snapshot,
)
from koel.config import Settings
from koel.domain import DailyBar, PriceSnapshot
from koel.path_backfill import (
    PathBackfillResult,
    run_path_backfill,
    seed_cse_stock_ids_from_company_info,
)


def test_trade_row_maps_cse_stock_id() -> None:
    row = TradeSummaryRow(id=297, symbol="jkh.n0000", price=20.0, name="JKH")
    snap = trade_row_to_snapshot(row)
    assert snap is not None
    assert snap.cse_stock_id == 297
    assert snap.symbol == "JKH.N0000"


def test_trade_row_rejects_bool_cse_stock_id() -> None:
    with pytest.raises(ValidationError):
        TradeSummaryRow(id=True, symbol="JKH.N0000", price=20.0)  # type: ignore[arg-type]


def test_chart_trade_date_colombo() -> None:
    # 18:30 UTC = midnight Colombo next calendar day
    ts = datetime(2026, 7, 15, 18, 30, tzinfo=UTC)
    assert chart_trade_date(ts).isoformat() == "2026-07-16"


def test_chart_point_to_daily_bar_period5() -> None:
    row = ChartPointRow.model_validate(
        {"p": 25.3, "h": 25.7, "l": 24.9, "o": None, "q": 1_000.0, "t": 1_752_703_800_000}
    )
    bar = chart_point_to_daily_bar(row, symbol="jkh.n0000", period=CHART_PERIOD_1Y)
    assert bar is not None
    assert bar.symbol == "JKH.N0000"
    assert bar.price == 25.3
    assert bar.high == 25.7
    assert bar.low == 24.9
    assert bar.open is None
    assert bar.volume == 1_000.0
    assert bar.source_period == 5


def test_chart_point_skips_intraday_period() -> None:
    row = ChartPointRow(p=20.0, t=1_752_703_800_000)
    assert chart_point_to_daily_bar(row, symbol="JKH.N0000", period=CHART_PERIOD_INTRADAY) is None


def test_chart_point_to_intraday_snapshot() -> None:
    row = ChartPointRow.model_validate(
        {
            "p": 27.6,
            "h": 27.8,
            "l": 26.2,
            "o": None,
            "q": 15.0,
            "c": 1.4,
            "pc": 5.34,
            "t": 1_784_278_690_833,
        }
    )
    snap = chart_point_to_intraday_snapshot(
        row, symbol="pins.n0000", cse_stock_id=3461
    )
    assert snap is not None
    assert snap.symbol == "PINS.N0000"
    assert snap.price == 27.6
    assert snap.high == 27.8
    assert snap.low == 26.2
    assert snap.volume == 15.0
    assert snap.cse_stock_id == 3461
    assert snap.ts.tzinfo is not None


def test_chart_point_intraday_skips_bad_price() -> None:
    row = ChartPointRow(p=float("nan"), t=1_752_703_800_000)
    assert chart_point_to_intraday_snapshot(row, symbol="JKH.N0000") is None


def test_chart_point_skips_non_finite_price() -> None:
    row = ChartPointRow(p=float("nan"), t=1_752_703_800_000)
    assert chart_point_to_daily_bar(row, symbol="JKH.N0000", period=CHART_PERIOD_1Y) is None


def test_daily_bar_rejects_bool_price() -> None:
    with pytest.raises(ValidationError):
        DailyBar(
            symbol="JKH.N0000",
            trade_date=chart_trade_date(datetime(2026, 7, 15, 18, 30, tzinfo=UTC)),
            price=True,  # type: ignore[arg-type]
            source_period=5,
            bar_ts=datetime(2026, 7, 15, 18, 30, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_path_backfill_disabled_without_force() -> None:
    settings = MagicMock(spec=Settings)
    settings.path_backfill_enabled = False
    storage = AsyncMock()
    cse = AsyncMock()
    result = await run_path_backfill(
        settings=settings, storage=storage, cse=cse, force=False
    )
    assert result == PathBackfillResult(0, 0, 0, 0, 0)
    cse.fetch_trade_summary.assert_not_called()
    cse.fetch_company_chart.assert_not_called()


@pytest.mark.asyncio
async def test_path_backfill_force_runs_and_persists() -> None:
    settings = MagicMock(spec=Settings)
    settings.path_backfill_enabled = False
    settings.path_backfill_period = 5
    settings.path_backfill_sleep_seconds = 0.0

    bar = DailyBar(
        symbol="JKH.N0000",
        trade_date=chart_trade_date(datetime(2026, 7, 15, 18, 30, tzinfo=UTC)),
        price=20.0,
        high=20.2,
        low=19.9,
        open=None,
        volume=100.0,
        source_period=5,
        bar_ts=datetime(2026, 7, 15, 18, 30, tzinfo=UTC),
    )
    storage = AsyncMock()
    storage.persist_market_snapshots = AsyncMock(
        return_value=[
            PriceSnapshot(
                symbol="JKH.N0000",
                price=20.0,
                ts=datetime.now(UTC),
                cse_stock_id=297,
            )
        ]
    )
    storage.list_stocks_with_cse_ids = AsyncMock(return_value=[("JKH.N0000", 297)])
    storage.list_symbols_missing_cse_stock_id = AsyncMock(return_value=[])
    storage.persist_daily_bars = AsyncMock(return_value=1)
    storage.upsert_stock = AsyncMock()

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(
                symbol="JKH.N0000",
                price=20.0,
                ts=datetime.now(UTC),
                cse_stock_id=297,
            )
        ]
    )
    cse.fetch_company_info = AsyncMock(return_value=None)
    cse.fetch_company_chart = AsyncMock(return_value=[bar])

    result = await run_path_backfill(
        settings=settings,
        storage=storage,
        cse=cse,
        force=True,
        sleep_seconds=0.0,
        limit=10,
    )
    assert result.symbols_targeted == 1
    assert result.symbols_ok == 1
    assert result.bars_upserted == 1
    cse.fetch_company_chart.assert_awaited_once()
    storage.persist_daily_bars.assert_awaited_once()


@pytest.mark.asyncio
async def test_company_info_seed_fills_missing_ids() -> None:
    storage = AsyncMock()
    storage.list_symbols_missing_cse_stock_id = AsyncMock(
        return_value=["TAP.N0000"]
    )
    storage.upsert_stock = AsyncMock()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(
        return_value=PriceSnapshot(
            symbol="TAP.N0000",
            price=30.1,
            ts=datetime.now(UTC),
            name="AMBEON CAPITAL PLC",
            cse_stock_id=2145,
        )
    )
    n = await seed_cse_stock_ids_from_company_info(
        storage=storage, cse=cse, limit=10, sleep_seconds=0.0
    )
    assert n == 1
    storage.upsert_stock.assert_awaited_once_with(
        "TAP.N0000", "AMBEON CAPITAL PLC", cse_stock_id=2145
    )
