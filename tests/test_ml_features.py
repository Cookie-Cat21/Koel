"""ML feature / leakage unit tests (no sklearn required)."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

import pytest

from koel.corporate_actions import CorporateAction
from koel.domain import DailyBar
from koel.ml.dataset import build_samples, feature_names
from koel.ml.features import labels_at, path_features


def _assert_feature_tuple_equal(left: tuple[float, ...], right: tuple[float, ...]) -> None:
    assert len(left) == len(right)
    for left_value, right_value in zip(left, right, strict=True):
        if math.isnan(left_value) or math.isnan(right_value):
            assert math.isnan(left_value) and math.isnan(right_value)
        else:
            assert left_value == pytest.approx(right_value)


def _bars(prices: list[float], *, start: date | None = None) -> list[DailyBar]:
    day0 = start or date(2025, 8, 1)
    out: list[DailyBar] = []
    for i, price in enumerate(prices):
        d = day0 + timedelta(days=i)
        out.append(
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
    return out


def test_path_features_uses_last_as_of() -> None:
    bars = _bars([10.0 + i * 0.1 for i in range(30)])
    feats = path_features(bars)
    assert feats is not None
    assert feats.as_of == bars[-1].trade_date
    assert len(feats.values) == 15


def test_labels_horizon() -> None:
    prices = [10.0, 11.0, 12.0, 9.0]
    lab = labels_at(prices, index=0, horizon=1)
    assert lab is not None
    ret, direction = lab
    assert abs(ret - 0.1) < 1e-9
    assert direction == 1.0
    lab5 = labels_at(prices, index=0, horizon=5)
    assert lab5 is None
    assert labels_at([10.0, 10.0], index=0, horizon=1) is None
    assert labels_at(
        [10.0, 10.0],
        index=0,
        horizon=1,
        include_flat=True,
    ) == (0.0, 0.0)


def test_build_samples_no_future_in_features() -> None:
    """Mutating future prices must not change feature vectors for past as_of."""
    prices = [10.0 + i * 0.05 for i in range(80)]
    bars = _bars(prices)
    samples = build_samples({"TEST.N0000": bars}, horizon=1, min_history=60)
    assert samples
    assert samples[0].target_date == bars[60].trade_date
    # Take a mid sample
    mid = samples[len(samples) // 2]
    # Rebuild with poisoned future prices after mid.as_of
    poisoned = []
    for b in bars:
        if b.trade_date > mid.as_of:
            poisoned.append(b.model_copy(update={"price": b.price * 10}))
        else:
            poisoned.append(b)
    samples2 = build_samples({"TEST.N0000": poisoned}, horizon=1, min_history=60)
    match = [s for s in samples2 if s.as_of == mid.as_of]
    assert match
    assert match[0].x == mid.x


def test_build_samples_bounded_window_matches_full_history_features() -> None:
    bars = _bars([10.0 + i * 0.03 for i in range(140)])
    samples = build_samples({"TEST.N0000": bars}, horizon=1, min_history=60)
    chosen = samples[-10]
    index = next(i for i, bar in enumerate(bars) if bar.trade_date == chosen.as_of)
    full = path_features(bars[: index + 1])
    assert full is not None
    assert chosen.x == full.values


def test_build_samples_quarantines_price_cliff_windows() -> None:
    prices = [10.0 + i * 0.01 for i in range(150)]
    prices[70:] = [price * 10 for price in prices[70:]]
    bars = _bars(prices)
    samples = build_samples(
        {"TEST.N0000": bars},
        horizon=1,
        min_history=60,
        max_abs_return=0.50,
    )
    sample_dates = {sample.as_of for sample in samples}
    assert bars[69].trade_date not in sample_dates  # label crosses the cliff
    assert bars[70].trade_date not in sample_dates  # features contain the cliff
    assert bars[129].trade_date not in sample_dates
    assert bars[130].trade_date in sample_dates


def test_build_samples_can_retain_flat_outcomes() -> None:
    bars = _bars([10.0] * 80)
    dropped = build_samples({"TEST.N0000": bars}, horizon=1, min_history=60)
    retained = build_samples(
        {"TEST.N0000": bars},
        horizon=1,
        min_history=60,
        include_flat=True,
    )
    assert dropped == []
    assert retained
    assert all(sample.y_dir == 0 for sample in retained)
    assert all(sample.target_date > sample.as_of for sample in retained)


def test_split_after_as_of_does_not_adjust_label() -> None:
    bars = _bars([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 5.0, 5.5])
    action = CorporateAction(
        symbol="TEST.N0000",
        effective_date=bars[6].trade_date,
        kind="split",
        ratio_from=1,
        ratio_to=2,
    )
    samples = build_samples(
        {"TEST.N0000": bars},
        horizon=1,
        min_history=6,
        include_flat=True,
        price_adjustment="split",
        corporate_actions={"TEST.N0000": [action]},
    )
    before_split = next(sample for sample in samples if sample.as_of == bars[5].trade_date)
    assert before_split.y_ret == pytest.approx(-0.5)


def test_split_before_as_of_adjusts_feature_window() -> None:
    bars = _bars([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 5.0, 5.5])
    action = CorporateAction(
        symbol="TEST.N0000",
        effective_date=bars[6].trade_date,
        kind="split",
        ratio_from=1,
        ratio_to=2,
    )
    samples = build_samples(
        {"TEST.N0000": bars},
        horizon=1,
        min_history=6,
        include_flat=True,
        price_adjustment="split",
        corporate_actions={"TEST.N0000": [action]},
    )
    ret_5d = feature_names().index("ret_5d")
    after_split = next(sample for sample in samples if sample.as_of == bars[6].trade_date)
    assert after_split.x[ret_5d] == pytest.approx(0.0)

    bounded = build_samples(
        {"TEST.N0000": bars},
        horizon=1,
        min_history=6,
        max_abs_return=0.35,
        include_flat=True,
        price_adjustment="split",
        corporate_actions={"TEST.N0000": [action]},
    )
    bounded_dates = {sample.as_of for sample in bounded}
    assert bars[5].trade_date not in bounded_dates
    assert bars[6].trade_date in bounded_dates


def test_no_lookahead_across_as_of_for_future_split_features() -> None:
    bars = _bars([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 7.5, 8.0])
    action = CorporateAction(
        symbol="TEST.N0000",
        effective_date=bars[6].trade_date,
        kind="split",
        ratio_from=1,
        ratio_to=2,
    )
    adjusted = build_samples(
        {"TEST.N0000": bars},
        horizon=1,
        min_history=6,
        include_flat=True,
        price_adjustment="split",
        corporate_actions={"TEST.N0000": [action]},
    )
    raw = build_samples(
        {"TEST.N0000": bars},
        horizon=1,
        min_history=6,
        include_flat=True,
    )
    as_of = bars[5].trade_date
    adjusted_before_split = next(sample for sample in adjusted if sample.as_of == as_of)
    raw_before_split = next(sample for sample in raw if sample.as_of == as_of)
    _assert_feature_tuple_equal(adjusted_before_split.x, raw_before_split.x)


def test_unadjusted_mode_keeps_raw_split_cliff() -> None:
    bars = _bars([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 5.0, 5.5])
    action = CorporateAction(
        symbol="TEST.N0000",
        effective_date=bars[6].trade_date,
        kind="split",
        ratio_from=1,
        ratio_to=2,
    )
    samples = build_samples(
        {"TEST.N0000": bars},
        horizon=1,
        min_history=6,
        include_flat=True,
        price_adjustment="none",
        corporate_actions={"TEST.N0000": [action]},
    )
    ret_5d = feature_names().index("ret_5d")
    after_split = next(sample for sample in samples if sample.as_of == bars[6].trade_date)
    assert after_split.x[ret_5d] == pytest.approx(-0.5)


def test_sklearn_available_helper() -> None:
    from koel.ml import sklearn_available

    # Just ensure callable; may be True/False depending on env.
    assert isinstance(sklearn_available(), bool)
