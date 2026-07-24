"""Feature Pack v1 helper and enricher tests."""

from __future__ import annotations

import math
import statistics
from datetime import UTC, date, datetime, timedelta

import pytest

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.feature_pack_v1 import FEATURE_PACK_V1_NAMES, adv20, enrich_feature_pack_v1, vol20


def _bars(
    *,
    symbol: str = "TEST.N0000",
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
                symbol=symbol,
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


def test_feature_pack_v1_names_are_stable() -> None:
    assert FEATURE_PACK_V1_NAMES == (
        "fp_adv20",
        "fp_adv20_log",
        "fp_zero_volume_streak",
        "fp_no_trade_flag",
        "fp_volume_spike",
        "fp_vol20",
        "fp_vol60",
        "fp_vol_regime",
        "fp_vol_regime_z",
        "fp_ret_1d",
        "fp_rel_ret_1d",
        "fp_rel_ret_5d",
        "fp_rel_ret_1d_market",
        "fp_rel_ret_5d_market",
        "fp_use_sector",
        "fp_days_since_filing",
        "fp_disclosure_proximity",
        "fp_pre_filing_window",
        "fp_post_filing_window",
        "fp_cliff_quarantine",
    )
    assert len(FEATURE_PACK_V1_NAMES) == 20


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


def test_enrich_appends_feature_pack_width() -> None:
    bars = _bars(count=30)
    as_of = bars[24].trade_date
    sample = Sample(
        symbol="TEST.N0000",
        as_of=as_of,
        x=(1.0, 2.0),
        y_ret=0.01,
        y_dir=1.0,
        horizon=1,
        target_date=bars[25].trade_date,
    )

    enriched = enrich_feature_pack_v1([sample], {"TEST.N0000": bars})

    assert len(enriched) == 1
    assert len(enriched[0].x) == len(sample.x) + len(FEATURE_PACK_V1_NAMES)
    assert enriched[0].x[-len(FEATURE_PACK_V1_NAMES)] == pytest.approx(
        adv20(bars, as_of=as_of)
    )


def test_enrich_adv20_ignores_future_volume() -> None:
    bars = _bars(volumes=[100.0] * 25 + [1_000_000.0] * 5, count=30)
    as_of = bars[19].trade_date
    sample = Sample(
        symbol="TEST.N0000",
        as_of=as_of,
        x=(0.0,),
        y_ret=0.01,
        y_dir=1.0,
        horizon=1,
        target_date=bars[20].trade_date,
    )
    before = enrich_feature_pack_v1([sample], {"TEST.N0000": bars})[0].x[
        -len(FEATURE_PACK_V1_NAMES)
    ]

    poisoned = list(bars)
    poisoned[-1] = poisoned[-1].model_copy(update={"volume": 99_999_999.0})
    after = enrich_feature_pack_v1([sample], {"TEST.N0000": poisoned})[0].x[
        -len(FEATURE_PACK_V1_NAMES)
    ]

    assert before == pytest.approx(100.0)
    assert after == pytest.approx(before)
