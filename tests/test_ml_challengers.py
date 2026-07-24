"""CPU challenger backend smoke tests."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from koel.ml.challengers import (
    predict_native_double_ensemble,
    predict_qlib_lightgbm,
)
from koel.ml.dataset import Sample


@pytest.fixture(autouse=True)
def _require_lightgbm() -> None:
    # Run-time (not collection-time) skip: a module-level importorskip would
    # surface as a collection skip even under `-m integration`, tripping the
    # migrate job's no-skips gate for a suite these tests aren't part of.
    pytest.importorskip("lightgbm")


def _samples(days: int) -> list[Sample]:
    out = []
    start = date(2020, 1, 1)
    for day in range(days):
        for symbol_index in range(4):
            feature = (day % 10 - 5) / 10 + symbol_index / 20
            realized = 0.01 if feature > 0 else -0.01
            out.append(
                Sample(
                    symbol=f"S{symbol_index}",
                    as_of=start + timedelta(days=day),
                    x=(feature, feature**2, float(symbol_index), float(day % 5)),
                    y_ret=realized,
                    y_dir=1.0 if realized > 0 else -1.0,
                    horizon=1,
                    target_date=start + timedelta(days=day + 1),
                )
            )
    return out


def test_qlib_lightgbm_challenger_is_deterministic() -> None:
    train, test = _samples(40), _samples(5)
    first = predict_qlib_lightgbm(train, test, seed=7)
    second = predict_qlib_lightgbm(train, test, seed=7)
    assert first == second
    assert len(first) == len(test)
    assert all(math.isfinite(value) for value in first)


def test_native_double_ensemble_outputs_finite_scores() -> None:
    train, test = _samples(40), _samples(5)
    prediction = predict_native_double_ensemble(train, test, seed=11)
    assert len(prediction) == len(test)
    assert all(math.isfinite(value) for value in prediction)
