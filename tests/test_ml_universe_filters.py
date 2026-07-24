"""Universe/liquidity filter tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.research_features import ResearchBarMetadata
from koel.ml.universe_filters import (
    LIQ_FILTER_V1,
    LIQ_FILTER_V2,
    LIQ_FILTER_V3,
    LIQ_FILTER_V4,
    filter_samples,
    passes_liq_filter_v1,
    passes_liq_filter_v2,
    passes_liq_filter_v3,
    passes_liq_filter_v4,
)


def _bars(
    *,
    symbol: str = "TEST.N0000",
    count: int = 80,
    start: date | None = None,
    volumes: list[float] | None = None,
    prices: list[float] | None = None,
    source_periods: list[int] | None = None,
) -> list[DailyBar]:
    day0 = start or date(2025, 1, 1)
    out: list[DailyBar] = []
    for index in range(count):
        day = day0 + timedelta(days=index)
        price = prices[index] if prices and index < len(prices) else 10.0 + index * 0.1
        volume = (
            volumes[index]
            if volumes and index < len(volumes)
            else 2_000.0 + index
        )
        source_period = (
            source_periods[index]
            if source_periods and index < len(source_periods)
            else 5
        )
        out.append(
            DailyBar(
                symbol=symbol,
                trade_date=day,
                price=price,
                high=price * 1.01,
                low=price * 0.99,
                open=price,
                volume=volume,
                source_period=source_period,
                bar_ts=datetime(day.year, day.month, day.day, tzinfo=UTC),
            )
        )
    return out


def _sample(symbol: str, as_of: date) -> Sample:
    return Sample(
        symbol=symbol,
        as_of=as_of,
        x=(1.0,),
        y_ret=0.01,
        y_dir=1.0,
        horizon=1,
    )


def test_liq_filter_v1_manifest_thresholds_are_frozen() -> None:
    assert LIQ_FILTER_V1.name == "liq_v1"
    assert LIQ_FILTER_V1.version == "v1"
    assert LIQ_FILTER_V1.min_adv20 == pytest.approx(1000.0)
    assert LIQ_FILTER_V1.max_flat_fraction_60 == pytest.approx(0.40)
    assert LIQ_FILTER_V1.min_cse_sessions_60 == 20


def test_passes_liq_filter_v1_accepts_liquid_nonflat_cse_history() -> None:
    bars = _bars(count=60, volumes=[1_000.0] * 60)

    assert passes_liq_filter_v1("TEST.N0000", bars)


def test_passes_liq_filter_v1_rejects_low_adv20() -> None:
    bars = _bars(count=60, volumes=[999.0] * 60)

    assert not passes_liq_filter_v1("TEST.N0000", bars)


def test_passes_liq_filter_v1_rejects_flat_history() -> None:
    bars = _bars(count=60, prices=[10.0] * 60)

    assert not passes_liq_filter_v1("TEST.N0000", bars)


def test_passes_liq_filter_v1_rejects_insufficient_cse_sessions() -> None:
    source_periods = [4] * 41 + [5] * 19
    bars = _bars(count=60, source_periods=source_periods)

    assert not passes_liq_filter_v1("TEST.N0000", bars)


def test_filter_samples_does_not_count_future_volume() -> None:
    volumes = [100.0] * 60 + [10_000.0] * 20
    bars = _bars(count=80, volumes=volumes)
    before_future_volume = _sample("TEST.N0000", bars[59].trade_date)
    after_future_volume = _sample("TEST.N0000", bars[79].trade_date)

    filtered = filter_samples(
        [before_future_volume, after_future_volume],
        {"TEST.N0000": bars},
        {},
        LIQ_FILTER_V1,
    )

    assert filtered == [after_future_volume]


def test_liq_filter_v2_manifest_thresholds_are_frozen() -> None:
    assert LIQ_FILTER_V2.name == "liq_v2"
    assert LIQ_FILTER_V2.version == "v2"
    assert LIQ_FILTER_V2.min_adv20 == pytest.approx(100.0)
    assert LIQ_FILTER_V2.max_flat_fraction_60 == pytest.approx(0.50)
    assert LIQ_FILTER_V2.min_cse_sessions_60 == 10


def test_passes_liq_filter_v2_accepts_milder_adv20_than_v1() -> None:
    bars = _bars(count=60, volumes=[500.0] * 60)

    assert passes_liq_filter_v2("TEST.N0000", bars)
    assert not passes_liq_filter_v1("TEST.N0000", bars)


def test_liq_filter_v3_manifest_thresholds_are_frozen() -> None:
    assert LIQ_FILTER_V3.name == "liq_v3"
    assert LIQ_FILTER_V3.version == "v3"
    assert LIQ_FILTER_V3.min_adv20 == pytest.approx(0.0)
    assert LIQ_FILTER_V3.max_flat_fraction_60 == pytest.approx(0.40)
    assert LIQ_FILTER_V3.min_cse_sessions_60 == 5


def test_passes_liq_filter_v3_skips_adv_floor() -> None:
    bars = _bars(count=60, volumes=[0.0] * 60)

    assert passes_liq_filter_v3("TEST.N0000", bars)
    assert not passes_liq_filter_v2("TEST.N0000", bars)


def test_passes_liq_filter_v1_uses_optional_metadata_flat_fraction() -> None:
    bars = _bars(count=60)
    metadata_row = ResearchBarMetadata(
        source="cse",
        features=(),
        flat_fraction_60=0.50,
    )

    assert not passes_liq_filter_v1(
        "TEST.N0000",
        bars,
        metadata_row=metadata_row,
    )


def test_liq_filter_v4_manifest_is_adv_only() -> None:
    assert LIQ_FILTER_V4.name == "liq_v4"
    assert LIQ_FILTER_V4.version == "v4"
    assert LIQ_FILTER_V4.min_adv20 == pytest.approx(500.0)
    assert LIQ_FILTER_V4.max_flat_fraction_60 == pytest.approx(1.0)
    assert LIQ_FILTER_V4.min_cse_sessions_60 == 0


def test_passes_liq_filter_v4_accepts_yahoo_heavy_history_with_adv() -> None:
    # All Yahoo source_period=4 would fail v1 CSE floor; v4 ignores CSE floor.
    bars = _bars(count=60, volumes=[600.0] * 60, source_periods=[4] * 60)
    assert passes_liq_filter_v4("TEST.N0000", bars)
    assert not passes_liq_filter_v1("TEST.N0000", bars)


def test_passes_liq_filter_v4_rejects_below_adv_floor() -> None:
    bars = _bars(count=60, volumes=[499.0] * 60, source_periods=[4] * 60)
    assert not passes_liq_filter_v4("TEST.N0000", bars)
