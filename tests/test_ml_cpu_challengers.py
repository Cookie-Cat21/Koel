"""CPU exhaust challenger smoke tests (runtime-skip when deps missing)."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from koel.ml.cpu_challengers import (
    CPU_EXHAUST_MODELS,
    lgb_hyperparam_grid,
    predict_hgb_bagged,
    predict_hgb_deep,
    predict_hgb_regressor,
    predict_hgb_weighted,
    predict_ridge_return,
)
from koel.ml.dataset import Sample
from koel.ml.distributed import ALLOWED_MODELS


@pytest.fixture(autouse=True)
def _require_sklearn() -> None:
    pytest.importorskip("sklearn")


def _samples(days: int, symbols: int = 6, start: date = date(2020, 1, 1)) -> list[Sample]:
    out = []
    for day in range(days):
        for symbol_index in range(symbols):
            feature = (day % 10 - 5) / 10 + symbol_index / 20
            realized = 0.01 if feature > 0 else -0.01
            out.append(
                Sample(
                    symbol=f"S{symbol_index}",
                    as_of=start + timedelta(days=day),
                    x=tuple(feature + offset * 0.01 for offset in range(12)),
                    y_ret=realized,
                    y_dir=1.0 if realized > 0 else -1.0,
                    horizon=1,
                    target_date=start + timedelta(days=day + 1),
                )
            )
    return out


def test_cpu_exhaust_models_are_registered() -> None:
    missing = sorted(set(CPU_EXHAUST_MODELS) - set(ALLOWED_MODELS))
    assert missing == []


def test_lgb_hyperparam_grid_hits_10000() -> None:
    grid = lgb_hyperparam_grid(limit=10_000)
    assert len(grid) == 10_000
    assert len({tuple(sorted(item.items())) for item in grid}) == 10_000


def test_ridge_and_hgb_variants_are_deterministic() -> None:
    train = _samples(80)
    test = _samples(20, start=date(2020, 1, 1) + timedelta(days=80))
    for fn in (
        predict_ridge_return,
        predict_hgb_regressor,
        predict_hgb_bagged,
        predict_hgb_deep,
        predict_hgb_weighted,
    ):
        first = fn(train, test, seed=3)
        second = fn(train, test, seed=3)
        assert first == second
        assert len(first) == len(test)
        assert all(math.isfinite(value) for value in first)
