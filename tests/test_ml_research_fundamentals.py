"""Publication-time-safe fundamental research feature tests."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime

from koel.ml.dataset import Sample
from koel.ml.research_fundamentals import (
    FUNDAMENTAL_FEATURE_NAMES,
    enrich_fundamentals,
)
from koel.ml.snapshot import FundamentalEvent


def _sample(day: date) -> Sample:
    return Sample(
        symbol="A.N0000",
        as_of=day,
        x=(1.0,),
        y_ret=0.01,
        y_dir=1.0,
        horizon=1,
        target_date=date(day.year, day.month, min(28, day.day + 1)),
    )


def test_fundamental_features_apply_only_after_publication_date() -> None:
    event = FundamentalEvent(
        symbol="A.N0000",
        published_at=datetime(2025, 2, 10, 12, tzinfo=UTC),
        fiscal_period_end=date(2024, 12, 31),
        kind="quarterly",
        revenue=1000.0,
        profit=100.0,
        eps_basic=1.25,
        eps_delta_pct=25.0,
        revenue_delta_pct=10.0,
        profit_delta_pct=12.0,
        match_quality="exact_yoy",
    )
    same_day = _sample(date(2025, 2, 10))
    next_day = _sample(date(2025, 2, 11))
    enriched = enrich_fundamentals(
        [same_day, next_day],
        {"A.N0000": [event]},
    )
    by_day = {sample.as_of: sample for sample in enriched}
    same_features = by_day[same_day.as_of].x[-len(FUNDAMENTAL_FEATURE_NAMES) :]
    next_features = by_day[next_day.as_of].x[-len(FUNDAMENTAL_FEATURE_NAMES) :]
    assert same_features[0] == 0.0
    assert next_features[0] == 1.0
    assert next_features[1] == 1.0
    assert next_features[2] == 1.0
    assert next_features[-1] == 1.0


def test_future_filing_does_not_change_past_feature_vector() -> None:
    sample = _sample(date(2025, 2, 11))
    future = FundamentalEvent(
        symbol="A.N0000",
        published_at=datetime(2025, 3, 1, tzinfo=UTC),
        fiscal_period_end=date(2024, 12, 31),
        kind="annual",
        revenue=9999.0,
        profit=999.0,
        eps_basic=9.0,
        eps_delta_pct=900.0,
        revenue_delta_pct=900.0,
        profit_delta_pct=900.0,
        match_quality="exact_yoy",
    )
    without = enrich_fundamentals([sample], {})
    with_future = enrich_fundamentals(
        [sample],
        {"A.N0000": [future]},
    )
    for left, right in zip(without[0].x, with_future[0].x, strict=True):
        assert left == right or (math.isnan(left) and math.isnan(right))
