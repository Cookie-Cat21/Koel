"""Market Appetite meter — pure scoring helpers + mocked async paths."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.appetite import (
    backfill_appetite,
    band_for_score,
    build_day_result,
    component_scores,
    composite_score,
    compute_day,
    compute_from_snapshots,
    map_breadth_score,
    map_index_score,
    map_intensity_score,
    map_participation_volume_share,
    map_participation_volume_total,
    map_participation_z_score,
    turnover_zscore,
)
from chime.domain import PriceSnapshot


def test_band_for_score_boundaries() -> None:
    assert band_for_score(0) == "extreme_caution"
    assert band_for_score(19.99) == "extreme_caution"
    assert band_for_score(20) == "caution"
    assert band_for_score(39.99) == "caution"
    assert band_for_score(40) == "neutral"
    assert band_for_score(59.99) == "neutral"
    assert band_for_score(60) == "appetite"
    assert band_for_score(79.99) == "appetite"
    assert band_for_score(80) == "strong_appetite"
    assert band_for_score(100) == "strong_appetite"


def test_band_for_score_clamps_out_of_range() -> None:
    assert band_for_score(-10) == "extreme_caution"
    assert band_for_score(150) == "strong_appetite"
    assert band_for_score(float("nan")) == "neutral"


def test_map_breadth_identity() -> None:
    assert map_breadth_score(0) == 0.0
    assert map_breadth_score(50) == 50.0
    assert map_breadth_score(100) == 100.0
    assert map_breadth_score(-5) == 0.0
    assert map_breadth_score(120) == 100.0
    assert map_breadth_score(float("nan")) == 50.0


def test_map_index_linear_through_zero() -> None:
    assert map_index_score(-3.0) == 0.0
    assert map_index_score(0.0) == 50.0
    assert map_index_score(3.0) == 100.0
    assert map_index_score(-6.0) == 0.0
    assert map_index_score(6.0) == 100.0
    assert map_index_score(None) == 50.0
    assert abs(map_index_score(1.5) - 75.0) < 1e-9


def test_map_intensity_none_is_neutral() -> None:
    assert map_intensity_score(None) == 50.0
    assert map_intensity_score(0) == 0.0
    assert map_intensity_score(100) == 100.0
    assert map_intensity_score(float("nan")) == 50.0


def test_map_participation_z() -> None:
    assert map_participation_z_score(-2.0) == 0.0
    assert map_participation_z_score(0.0) == 50.0
    assert map_participation_z_score(2.0) == 100.0
    assert map_participation_z_score(None) == 50.0
    assert map_participation_z_score(-4.0) == 0.0


def test_map_participation_volume_share() -> None:
    assert map_participation_volume_share(0) == 0.0
    assert map_participation_volume_share(100) == 100.0
    assert map_participation_volume_share(37.5) == 37.5
    assert map_participation_volume_share(float("nan")) == 50.0


def test_map_participation_volume_total() -> None:
    hist = [100.0, 100.0, 100.0, 100.0, 100.0, 200.0]
    assert map_participation_volume_total(None, hist) is None
    assert map_participation_volume_total(100.0, [100.0]) is None  # thin hist
    scored = map_participation_volume_total(200.0, hist)
    assert scored is not None
    assert scored > 50.0


def test_turnover_zscore_basic() -> None:
    hist = [10.0, 10.0, 10.0, 10.0, 20.0]
    z = turnover_zscore(20.0, hist)
    assert z is not None
    assert z > 0
    assert turnover_zscore(10.0, [10.0]) is None
    assert turnover_zscore(10.0, [10.0, 10.0]) == 0.0
    assert turnover_zscore(10.0, [float("nan"), 10.0]) is None


def test_component_scores_all_advancers() -> None:
    comps = component_scores(
        change_pcts=[1.0, 2.0, 3.0, 0.5],
        volumes=[100.0, 200.0, 0.0, 50.0],
        aspi_change_pct=0.0,
    )
    assert comps["breadth"] == 100.0
    assert comps["intensity"] == 100.0
    assert comps["index"] == 50.0
    assert comps["participation"] == 75.0


def test_component_scores_all_decliners_no_movers() -> None:
    comps = component_scores(
        change_pcts=[-0.5, -0.2, -1.0],
        aspi_change_pct=-3.0,
    )
    assert comps["breadth"] == 0.0
    assert comps["intensity"] == 50.0
    assert comps["index"] == 0.0


def test_component_scores_intensity_mixed_movers() -> None:
    comps = component_scores(change_pcts=[2.0, 3.0, -2.5, 0.1])
    assert abs(comps["intensity"] - (2 / 3) * 100.0) < 1e-9
    assert abs(comps["breadth"] - 75.0) < 1e-9


def test_component_scores_uses_turnover_z_when_history() -> None:
    hist = [100.0, 100.0, 100.0, 100.0, 100.0, 200.0]
    comps = component_scores(
        change_pcts=[1.0, -1.0],
        volumes=[0.0, 0.0],
        turnover=200.0,
        turnover_history=hist,
    )
    assert comps["participation"] > 50.0


def test_component_scores_uses_volume_total_z() -> None:
    hist = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 2000.0]
    comps = component_scores(
        change_pcts=[1.0, -1.0],
        volumes=[0.0, 0.0],  # would be 0% if used
        volume_total=2000.0,
        volume_total_history=hist,
    )
    assert comps["participation"] > 50.0


def test_component_scores_empty_changes_neutral_breadth() -> None:
    comps = component_scores(change_pcts=[])
    assert comps["breadth"] == 50.0
    assert comps["intensity"] == 50.0
    assert comps["participation"] == 50.0


def test_composite_score_weights() -> None:
    comps = {
        "breadth": 100.0,
        "intensity": 0.0,
        "index": 50.0,
        "participation": 0.0,
    }
    assert abs(composite_score(comps) - 50.0) < 1e-9


def test_build_day_result_empty_returns_none() -> None:
    assert build_day_result(trade_date=date(2026, 7, 1), change_pcts=[]) is None


def test_build_day_result_happy_path() -> None:
    result = build_day_result(
        trade_date=date(2026, 7, 16),
        change_pcts=[1.0, 2.0, -1.0, 0.0],
        volumes=[10.0, 20.0, 30.0, 0.0],
        aspi_change_pct=1.5,
        volume_total=60.0,
        volume_total_history=[50.0, 55.0, 60.0, 45.0, 70.0, 60.0],
        source="cse",
    )
    assert result is not None
    assert result.universe_n == 4
    assert result.advancers == 2
    assert result.decliners == 1
    assert result.unchanged == 1
    assert 0.0 <= result.score <= 100.0
    assert result.band == band_for_score(result.score)
    assert set(result.components) == {"breadth", "intensity", "index", "participation"}
    assert math.isfinite(result.score)


def test_build_day_result_invalid_source_normalized() -> None:
    result = build_day_result(
        trade_date=date(2026, 7, 1),
        change_pcts=[1.0],
        source="nope",
    )
    assert result is not None
    assert result.source == "cse"


@pytest.mark.asyncio
async def test_compute_day_happy() -> None:
    storage = MagicMock()
    storage.list_daily_bar_changes_for_date = AsyncMock(
        return_value=[
            {"change_pct": 1.0, "volume": 10.0},
            {"change_pct": -2.0, "volume": 20.0},
            {"change_pct": 3.0, "volume": 0.0},
        ]
    )
    storage.aspi_change_pct_for_date = AsyncMock(return_value=0.5)
    storage.list_market_daily_summary = AsyncMock(
        return_value=[
            {"trade_date": date(2026, 7, 1), "market_turnover": 100.0},
            {"trade_date": date(2026, 7, 2), "market_turnover": 120.0},
            {"trade_date": date(2026, 7, 3), "market_turnover": 140.0},
        ]
    )
    storage.upsert_market_appetite_daily = AsyncMock()
    out = await compute_day(storage, date(2026, 7, 3), source="cse")
    assert out is not None
    assert out.universe_n == 3
    storage.upsert_market_appetite_daily.assert_awaited_once()


@pytest.mark.asyncio
async def test_compute_day_empty_returns_none() -> None:
    storage = MagicMock()
    storage.list_daily_bar_changes_for_date = AsyncMock(return_value=[])
    out = await compute_day(storage, date(2026, 7, 3))
    assert out is None


@pytest.mark.asyncio
async def test_compute_from_snapshots() -> None:
    storage = MagicMock()
    ts = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)
    storage.list_latest_price_snapshots = AsyncMock(
        return_value=[
            PriceSnapshot(
                id=1,
                symbol="JKH.N0000",
                price=100.0,
                change=1.0,
                change_pct=1.0,
                volume=1000.0,
                ts=ts,
                previous_close=99.0,
            ),
            PriceSnapshot(
                id=2,
                symbol="COMB.N0000",
                price=50.0,
                change=-1.0,
                change_pct=-2.0,
                volume=500.0,
                ts=ts,
                previous_close=51.0,
            ),
        ]
    )
    storage.latest_index_change_pct = AsyncMock(return_value=0.2)
    storage.list_market_daily_summary = AsyncMock(return_value=[])
    storage.upsert_market_appetite_daily = AsyncMock()
    out = await compute_from_snapshots(storage, trade_date=date(2026, 7, 16))
    assert out is not None
    assert out.universe_n == 2
    storage.upsert_market_appetite_daily.assert_awaited_once()


@pytest.mark.asyncio
async def test_backfill_appetite_force() -> None:
    d1, d2 = date(2026, 7, 15), date(2026, 7, 16)
    storage = MagicMock()
    storage.list_daily_bar_trade_dates = AsyncMock(return_value=[d1, d2])
    storage.list_market_appetite_daily = AsyncMock(return_value=[])
    storage.list_market_daily_summary = AsyncMock(return_value=[])
    storage.list_all_daily_bar_changes = AsyncMock(
        return_value=[
            {"trade_date": d1, "change_pct": 1.0, "volume": 10.0},
            {"trade_date": d1, "change_pct": -1.0, "volume": 20.0},
            {"trade_date": d2, "change_pct": 2.0, "volume": 30.0},
            {"trade_date": d2, "change_pct": 3.0, "volume": 40.0},
        ]
    )
    storage.list_aspi_change_pcts = AsyncMock(
        return_value={d1: 0.1, d2: -0.2}
    )
    storage.upsert_market_appetite_daily = AsyncMock()
    result = await backfill_appetite(storage, source="cse", force=True)
    assert result.dates_targeted == 2
    assert result.dates_upserted == 2
    assert storage.upsert_market_appetite_daily.await_count == 2


@pytest.mark.asyncio
async def test_backfill_skips_existing_without_force() -> None:
    d1 = date(2026, 7, 15)
    storage = MagicMock()
    storage.list_daily_bar_trade_dates = AsyncMock(return_value=[d1])
    storage.list_market_appetite_daily = AsyncMock(
        return_value=[{"trade_date": d1}]
    )
    storage.list_market_daily_summary = AsyncMock(return_value=[])
    storage.list_all_daily_bar_changes = AsyncMock(return_value=[])
    storage.list_aspi_change_pcts = AsyncMock(return_value={})
    storage.upsert_market_appetite_daily = AsyncMock()
    result = await backfill_appetite(storage, force=False)
    assert result.dates_skipped == 1
    assert result.dates_upserted == 0
    storage.upsert_market_appetite_daily.assert_not_awaited()
