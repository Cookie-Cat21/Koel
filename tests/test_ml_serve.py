"""ML forecast serve — smoke with synthetic bars (needs sklearn)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from koel.domain import DailyBar
from koel.ml import sklearn_available


def _series(n: int = 200) -> dict[str, list[DailyBar]]:
    day0 = date(2025, 8, 1)
    bars: list[DailyBar] = []
    for i in range(n):
        d = day0 + timedelta(days=i)
        price = 10.0 + i * 0.05
        bars.append(
            DailyBar(
                symbol="TEST.N0000",
                trade_date=d,
                price=price,
                high=price * 1.01,
                low=price * 0.99,
                open=None,
                volume=1000.0 + i,
                source_period=5,
                bar_ts=datetime(d.year, d.month, d.day, 18, 30, tzinfo=UTC),
            )
        )
    return {"TEST.N0000": bars}


@pytest.mark.skipif(not sklearn_available(), reason="sklearn not installed")
def test_train_and_predict_path() -> None:
    from koel.ml.serve import _predict_price_path, _train_horizon_models

    series = _series()
    models = _train_horizon_models(series, horizons=(1, 5), min_history=60)
    assert 1 in models and 5 in models
    points = _predict_price_path(series["TEST.N0000"], models, horizons=(1, 5))
    assert len(points) == 2
    assert points[0].horizon_i == 1
    assert points[0].model_version.startswith("ml_hgb")
    assert points[0].yhat > 0


@pytest.mark.asyncio
@pytest.mark.skipif(not sklearn_available(), reason="sklearn not installed")
async def test_write_ml_forecasts_calls_storage() -> None:
    from koel.ml.serve import write_ml_forecasts

    series = _series()
    storage = AsyncMock()
    storage.list_symbols_with_daily_bars = AsyncMock(
        return_value=list(series.keys())
    )
    storage.list_daily_bars = AsyncMock(return_value=series["TEST.N0000"])
    storage.replace_forecast_points = AsyncMock(return_value=5)

    result = await write_ml_forecasts(storage=storage, horizons=(1, 2, 3, 4, 5))
    assert result.symbols_ok == 1
    assert result.points_written == 5
    storage.replace_forecast_points.assert_awaited()
