"""Sample-weight tests for ML training levers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.sample_weights import adv20_sample_weights


def _bars(
    symbol: str,
    volumes: list[float | None],
    *,
    start: date = date(2025, 1, 1),
) -> list[DailyBar]:
    out: list[DailyBar] = []
    for index, volume in enumerate(volumes):
        day = start + timedelta(days=index)
        out.append(
            DailyBar(
                symbol=symbol,
                trade_date=day,
                price=10.0 + index,
                high=10.0 + index,
                low=10.0 + index,
                open=10.0 + index,
                volume=volume,
                source_period=5,
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
        target_date=as_of + timedelta(days=1),
    )


def test_adv20_sample_weights_ignore_future_volume() -> None:
    start = date(2025, 1, 1)
    as_of = start + timedelta(days=29)
    future_heavy_tail = [100.0] * 30 + [1_000_000.0] * 20
    steady = [100.0] * 50

    weights = adv20_sample_weights(
        [_sample("FUTURE.N0000", as_of), _sample("STEADY.N0000", as_of)],
        {
            "FUTURE.N0000": _bars("FUTURE.N0000", future_heavy_tail, start=start),
            "STEADY.N0000": _bars("STEADY.N0000", steady, start=start),
        },
    )

    assert weights == pytest.approx([1.0, 1.0])


def test_adv20_sample_weights_use_last_twenty_bars_at_as_of() -> None:
    start = date(2025, 1, 1)
    as_of = start + timedelta(days=24)

    weights = adv20_sample_weights(
        [_sample("ROLL.N0000", as_of), _sample("STEADY.N0000", as_of)],
        {
            "ROLL.N0000": _bars("ROLL.N0000", [1.0] * 5 + [9.0] * 20, start=start),
            "STEADY.N0000": _bars("STEADY.N0000", [9.0] * 25, start=start),
        },
    )

    assert weights == pytest.approx([1.0, 1.0])


def test_adv20_sample_weights_missing_history_is_neutral() -> None:
    weights = adv20_sample_weights(
        [_sample("MISSING.N0000", date(2025, 1, 10))],
        {},
    )

    assert weights == [1.0]
