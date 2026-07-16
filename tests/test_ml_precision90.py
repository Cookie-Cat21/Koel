"""Unit tests for precision-90 gate evaluation."""

from __future__ import annotations

from datetime import date, timedelta

from chime.ml.diagnose import PredRow
from chime.ml.features import FEATURE_NAMES
from chime.ml.precision90 import (
    PRECISION_TARGET,
    _eval_mask,
    pick_best,
    sweep_score_thresholds,
)


def _row(
    *,
    score: float,
    hit: bool,
    fold: int = 0,
    symbol: str = "A.N0000",
    day: int = 0,
) -> PredRow:
    return PredRow(
        symbol=symbol,
        as_of=date(2025, 1, 1) + timedelta(days=day),
        fold=fold,
        score=score,
        y_dir=1.0 if hit else -1.0,
        y_ret=0.01 if hit else -0.01,
        hit=hit,
        features=(0.0,) * len(FEATURE_NAMES),
        sector="Test",
    )


def test_eval_mask_precision() -> None:
    rows = [
        _row(score=0.4, hit=True, fold=0, symbol="A", day=0),
        _row(score=0.4, hit=True, fold=0, symbol="B", day=1),
        _row(score=0.4, hit=False, fold=1, symbol="C", day=2),
        _row(score=0.05, hit=False, fold=1, symbol="D", day=3),
    ]
    mask = [abs(r.score) >= 0.3 for r in rows]
    cand = _eval_mask(rows, mask, name="t", details={"kind": "abs_score", "thr": 0.3})
    assert cand.n_emits == 3
    assert abs(cand.precision - 2 / 3) < 1e-9


def test_sweep_finds_high_thr() -> None:
    rows = []
    # Many high-score hits across folds/symbols
    for i in range(250):
        rows.append(
            _row(
                score=0.4,
                hit=True,
                fold=i % 5,
                symbol=f"S{i % 90}",
                day=i,
            )
        )
    for i in range(50):
        rows.append(
            _row(
                score=0.05,
                hit=False,
                fold=i % 5,
                symbol=f"L{i}",
                day=1000 + i,
            )
        )
    cands = sweep_score_thresholds(rows, prefix="clf")
    best = pick_best(cands)
    assert best is not None
    assert best.precision >= PRECISION_TARGET
    assert best.passes_target
