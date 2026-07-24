"""Feature Pack v3 append enricher tests."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.feature_pack_v1 import FEATURE_PACK_V1_NAMES
from koel.ml.feature_pack_v3 import FEATURE_PACK_V3_NAMES, enrich_feature_pack_v3


def _bars(
    *,
    symbol: str = "TEST.N0000",
    prices: list[float] | None = None,
    start: date | None = None,
    count: int = 70,
    volume_base: float = 1000.0,
) -> list[DailyBar]:
    day0 = start or date(2025, 1, 1)
    out: list[DailyBar] = []
    for index in range(count):
        day = day0 + timedelta(days=index)
        price = prices[index] if prices and index < len(prices) else 10.0 + index * 0.1
        out.append(
            DailyBar(
                symbol=symbol,
                trade_date=day,
                price=price,
                high=price * 1.02,
                low=price * 0.98,
                open=price,
                volume=volume_base + index * 10.0,
                source_period=5,
                bar_ts=datetime(day.year, day.month, day.day, tzinfo=UTC),
            )
        )
    return out


def _sample(symbol: str, as_of: date) -> Sample:
    return Sample(
        symbol=symbol,
        as_of=as_of,
        x=(),
        y_ret=0.01,
        y_dir=1.0,
        horizon=1,
        target_date=as_of + timedelta(days=1),
    )


def test_v3_appends_ten_columns_after_v2_pack() -> None:
    prices_a = [10.0 + index * 0.5 for index in range(70)]
    prices_b = [20.0 + index * 0.1 for index in range(70)]
    bars_a = _bars(symbol="A.N0000", prices=prices_a, volume_base=5000.0)
    bars_b = _bars(symbol="B.N0000", prices=prices_b, volume_base=500.0)
    as_of = bars_a[60].trade_date
    sector_map = {"A.N0000": "Tech", "B.N0000": "Tech"}
    samples = [_sample("A.N0000", as_of), _sample("B.N0000", as_of)]
    series = {"A.N0000": bars_a, "B.N0000": bars_b}

    enriched = enrich_feature_pack_v3(samples, series, sector_map=sector_map)
    assert len(enriched) == 2
    for row in enriched:
        assert len(row.x) == len(FEATURE_PACK_V1_NAMES) + len(FEATURE_PACK_V3_NAMES)

    by_symbol = {row.symbol: row for row in enriched}
    # Sector rank: A has steeper path → higher 1d rank than B on typical days.
    rank_a = by_symbol["A.N0000"].x[-len(FEATURE_PACK_V3_NAMES)]
    rank_b = by_symbol["B.N0000"].x[-len(FEATURE_PACK_V3_NAMES)]
    assert math.isfinite(rank_a) and math.isfinite(rank_b)
    assert {rank_a, rank_b} == {0.0, 1.0}

    # ADV z-scores should be opposite signs (high vs low volume).
    adv_z_a = by_symbol["A.N0000"].x[-len(FEATURE_PACK_V3_NAMES) + 2]
    adv_z_b = by_symbol["B.N0000"].x[-len(FEATURE_PACK_V3_NAMES) + 2]
    assert adv_z_a > 0 > adv_z_b


def test_v3_future_bars_do_not_change_as_of_features() -> None:
    bars = _bars(symbol="A.N0000", count=70)
    as_of = bars[50].trade_date
    sector_map = {"A.N0000": "Tech"}
    samples = [_sample("A.N0000", as_of)]
    base = enrich_feature_pack_v3(samples, {"A.N0000": bars[:51]}, sector_map=sector_map)
    poisoned_bars = bars[:51] + _bars(
        symbol="A.N0000",
        start=as_of + timedelta(days=1),
        count=10,
        prices=[999.0] * 10,
        volume_base=1e9,
    )
    poisoned = enrich_feature_pack_v3(
        samples, {"A.N0000": poisoned_bars}, sector_map=sector_map
    )
    assert len(base[0].x) == len(poisoned[0].x)
    for left, right in zip(base[0].x, poisoned[0].x, strict=True):
        if math.isnan(left) and math.isnan(right):
            continue
        assert left == right
