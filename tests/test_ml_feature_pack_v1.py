"""Feature Pack v1 pure helper tests (research-only stub)."""

from __future__ import annotations

import math
import statistics
from datetime import UTC, date, datetime, timedelta

import pytest

from koel.domain import DailyBar
from koel.ml.feature_pack_v1 import adv20, vol20


def _bars(
    *,
    prices: list[float] | None = None,
    volumes: list[float] | None = None,
    start: date | None = None,
    count: int | None = None,
) -> list[DailyBar]:
    n = count if count is not None else max(len(prices or []), len(volumes or []), 25)
    day0 = start or date(2025, 1, 1)
    out: list[DailyBar] = []
    for index in range(n):
        day = day0 + timedelta(days=index)
        price = (prices[index] if prices and index < len(prices) else 10.0 + index * 0.1)
        volume = (
            volumes[index]
            if volumes and index < len(volumes)
            else 1000.0 + index * 10.0
        )
        out.append(
            DailyBar(
                symbol="TEST.N0000",
                trade_date=day,
                price=price,
                high=price * 1.01,
                low=price * 0.99,
                open=price,
                volume=volume,
                source_period=5,
                bar_ts=datetime(day.year, day.month, day.day, tzinfo=UTC),
            )
        )
    return out


def test_adv20_mean_of_last_twenty_volumes() -> None:
    volumes = [float(index) for index in range(1, 31)]
    bars = _bars(volumes=volumes)
    expected = statistics.fmean(volumes[-20:])
    assert adv20(bars) == pytest.approx(expected)


def test_adv20_respects_as_of_cutoff() -> None:
    volumes = [100.0] * 15 + [200.0] * 15
    bars = _bars(volumes=volumes, count=30)
    as_of = bars[9].trade_date
    assert adv20(bars, as_of=as_of) == pytest.approx(100.0)


def test_vol20_positive_for_trending_prices() -> None:
    bars = _bars(prices=[10.0 + index * 0.5 for index in range(30)])
    value = vol20(bars)
    assert math.isfinite(value)
    assert value > 0.0


def test_vol20_nan_with_insufficient_history() -> None:
    bars = _bars(prices=[10.0, 10.1, 10.2], count=3)
    assert math.isnan(vol20(bars))


def test_future_bars_do_not_change_point_in_time_features() -> None:
    bars = _bars()
    as_of = bars[19].trade_date
    before_adv = adv20(bars, as_of=as_of)
    before_vol = vol20(bars, as_of=as_of)

    poisoned = list(bars)
    poisoned[-1] = poisoned[-1].model_copy(update={"price": 999.0, "volume": 999_999.0})

    assert adv20(poisoned, as_of=as_of) == pytest.approx(before_adv)
    assert vol20(poisoned, as_of=as_of) == pytest.approx(before_vol)
