"""Point-in-time distributed research feature tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.research_features import (
    RESEARCH_FEATURE_NAMES,
    build_research_bar_metadata,
    enrich_market_context,
    enrich_research_quality,
    sample_domain,
)


def _bars() -> list[DailyBar]:
    start = date(2025, 1, 1)
    out: list[DailyBar] = []
    for index in range(70):
        day = start + timedelta(days=index)
        cse = index >= 50
        out.append(
            DailyBar(
                symbol="A.N0000",
                trade_date=day,
                price=10.0 + index * 0.01,
                high=None if cse else 10.2 + index * 0.01,
                low=None if cse else 9.8 + index * 0.01,
                open=None if cse else 10.0 + index * 0.01,
                volume=1000.0,
                source_period=5 if cse else 0,
                bar_ts=datetime(day.year, day.month, day.day, tzinfo=UTC),
            )
        )
    return out


def test_research_metadata_tracks_source_without_future_leakage() -> None:
    bars = _bars()
    metadata = build_research_bar_metadata(
        {"A.N0000": bars},
        dataset="hybrid",
    )
    before = metadata[("A.N0000", bars[49].trade_date)]
    first_cse = metadata[("A.N0000", bars[50].trade_date)]
    latest = metadata[("A.N0000", bars[69].trade_date)]

    assert before.source == "yahoo"
    assert before.features[0] == 0.0
    assert before.features[3] == -1.0
    assert first_cse.source == "cse"
    assert first_cse.features[0] == 1.0
    assert first_cse.features[1] == 1 / 20
    assert first_cse.features[4] == 1.0
    assert latest.features[1] == 1.0
    assert latest.features[5] == 1.0
    assert len(latest.features) == len(RESEARCH_FEATURE_NAMES)
    lag_index = RESEARCH_FEATURE_NAMES.index("return_lag_1")
    assert latest.features[lag_index] > 0

    poisoned = list(bars)
    poisoned[-1] = poisoned[-1].model_copy(update={"source_period": 0, "open": 99.0})
    changed = build_research_bar_metadata(
        {"A.N0000": poisoned},
        dataset="hybrid",
    )
    assert changed[("A.N0000", bars[49].trade_date)] == before


def test_research_enrichment_preserves_target_and_domain() -> None:
    bars = _bars()
    metadata = build_research_bar_metadata(
        {"A.N0000": bars},
        dataset="hybrid",
    )
    sample = Sample(
        symbol="A.N0000",
        as_of=bars[68].trade_date,
        x=(1.0, 2.0),
        y_ret=0.01,
        y_dir=1.0,
        horizon=1,
        target_date=bars[69].trade_date,
    )
    enriched = enrich_research_quality([sample], metadata)
    assert len(enriched) == 1
    assert len(enriched[0].x) == 2 + len(RESEARCH_FEATURE_NAMES)
    assert enriched[0].target_date == sample.target_date
    assert sample_domain(enriched[0], metadata) == "cse"

    crossing = Sample(
        symbol="A.N0000",
        as_of=bars[49].trade_date,
        x=(1.0,),
        y_ret=0.01,
        y_dir=1.0,
        horizon=1,
        target_date=bars[50].trade_date,
    )
    assert sample_domain(crossing, metadata) is None


def test_market_context_uses_current_session_features() -> None:
    day = date(2025, 2, 1)
    samples = [
        Sample("A", day, (0.10, 0.20), 0.01, 1.0, 1, day + timedelta(days=1)),
        Sample("B", day, (-0.05, -0.10), -0.01, -1.0, 1, day + timedelta(days=1)),
    ]
    enriched = enrich_market_context(samples)
    for sample in enriched:
        context = sample.x[-5:]
        assert context[0] == pytest.approx(0.025)
        assert context[1] == pytest.approx(0.025)
        assert context[2] == 0.5
        assert context[3] == pytest.approx(0.075)
        assert context[4] == pytest.approx(0.05)
