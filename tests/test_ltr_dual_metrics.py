"""Unit tests for LTR / dual-target metric helpers (no DB)."""

from __future__ import annotations

from datetime import date

from chime.ml.dataset import Sample
from chime.ml.ltr_dual import (
    _big_move_precision,
    _relevance_from_returns,
    _top_bottom_spread,
)


def _s(sym: str, d: date, ret: float) -> Sample:
    return Sample(
        symbol=sym,
        as_of=d,
        x=(0.0,) * 15,
        y_ret=ret,
        y_dir=1.0 if ret > 0 else -1.0,
        horizon=1,
    )


def test_relevance_higher_return_higher_rel() -> None:
    d = date(2026, 1, 2)
    day = [_s("A", d, -0.02), _s("B", d, 0.0), _s("C", d, 0.03), _s("D", d, 0.01)]
    rel = _relevance_from_returns(day, buckets=4)
    assert rel[2] > rel[0]  # C > A
    assert max(rel) == 3.0


def test_top_bottom_spread_positive_when_ranked() -> None:
    d = date(2026, 1, 2)
    # 10 names; preds equal actuals → positive spread
    as_of = [d] * 10
    preds = [float(i) for i in range(10)]
    actuals = [float(i) * 0.01 for i in range(10)]
    spread = _top_bottom_spread(as_of, preds, actuals, frac=0.2, min_names=10)
    assert spread is not None
    assert spread > 0


def test_big_move_precision_perfect() -> None:
    d = date(2026, 1, 2)
    as_of = [d] * 12
    preds = [float(i) for i in range(12)]
    actuals = [float(i) for i in range(12)]
    p = _big_move_precision(as_of, preds, actuals, frac=0.25, min_names=8)
    assert p == 1.0
