"""Skip-day / execution-lag labels stay PIT-safe and leave features unchanged."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

from koel.domain import DailyBar
from koel.ml.dataset import build_samples
from koel.ml.features import labels_at


def _bars(prices: list[float]) -> list[DailyBar]:
    start = date(2024, 1, 1)
    return [
        DailyBar(
            symbol="T.N0000",
            trade_date=start + timedelta(days=i),
            price=price,
            high=price,
            low=price,
            open=price,
            volume=1000.0,
            source_period=5,
            bar_ts=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
        )
        for i, price in enumerate(prices)
    ]


def _same_features(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    if len(a) != len(b):
        return False
    for left, right in zip(a, b, strict=True):
        if math.isnan(left) and math.isnan(right):
            continue
        if left != right:
            return False
    return True


def test_labels_at_skip_shifts_return_window() -> None:
    prices = [10.0 + i * 0.1 for i in range(80)]
    skip0 = labels_at(prices, index=60, horizon=1, skip=0)
    skip1 = labels_at(prices, index=60, horizon=1, skip=1)
    assert skip0 is not None and skip1 is not None
    assert skip0[0] == (prices[61] / prices[60]) - 1.0
    assert skip1[0] == (prices[62] / prices[61]) - 1.0


def test_build_samples_label_skip_keeps_features_changes_labels() -> None:
    prices = [10.0 + i * 0.1 for i in range(100)]
    bars = _bars(prices)
    base = build_samples({"T.N0000": bars}, horizon=1, min_history=60, label_skip=0)
    skipped = build_samples(
        {"T.N0000": bars},
        horizon=1,
        min_history=60,
        label_skip=1,
    )
    assert len(skipped) == len(base) - 1
    by0 = {sample.as_of: sample for sample in base}
    by1 = {sample.as_of: sample for sample in skipped}
    common = sorted(set(by0) & set(by1))
    assert common
    for as_of in common:
        assert _same_features(by0[as_of].x, by1[as_of].x)
        assert by0[as_of].y_ret != by1[as_of].y_ret
        assert by1[as_of].target_date == by0[as_of].target_date + timedelta(days=1)
