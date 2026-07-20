"""Unit tests for purged walk-forward helpers and confidence gates."""

from __future__ import annotations

from datetime import date, timedelta

from koel.ml.dataset import Sample
from koel.ml.harden import _demean_by_day, _purge_train
from koel.ml.metrics import mean_daily_rank_ic, spearman, sweep_confidence_gates


def _sample(d: date, y_ret: float = 0.01) -> Sample:
    return Sample(
        symbol="A.N0000",
        as_of=d,
        x=(0.0,) * 15,
        y_ret=y_ret,
        y_dir=1.0 if y_ret > 0 else -1.0,
        horizon=5,
    )


def test_purge_train_drops_horizon_buffer() -> None:
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
    samples = [_sample(d) for d in dates]
    # cut=20, horizon=5, embargo=2 → end_exclusive = 20 - max(5,2) = 15
    train = _purge_train(
        samples, dates=dates, cut=20, horizon=5, embargo=2
    )
    train_dates = {s.as_of for s in train}
    assert max(train_dates) == dates[14]
    assert dates[15] not in train_dates
    assert dates[19] not in train_dates


def test_demean_by_day_zero_mean() -> None:
    d = date(2025, 6, 1)
    samples = [
        Sample(
            symbol=f"S{i}",
            as_of=d,
            x=(0.0,) * 15,
            y_ret=float(i),
            y_dir=1.0,
            horizon=1,
        )
        for i in range(4)
    ]
    out = _demean_by_day(samples)
    # mean of 0,1,2,3 = 1.5 → demeaned -1.5,-0.5,0.5,1.5; zero dropped
    assert len(out) == 4
    assert abs(sum(s.y_ret for s in out)) < 1e-9


def test_spearman_perfect() -> None:
    ic = spearman([1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
    assert ic is not None and abs(ic - 1.0) < 1e-9


def test_mean_daily_rank_ic() -> None:
    d1 = date(2025, 1, 1)
    d2 = date(2025, 1, 2)
    as_of = [d1, d1, d1, d1, d1, d2, d2, d2, d2, d2]
    preds = [1, 2, 3, 4, 5, 5, 4, 3, 2, 1]
    acts = [1, 2, 3, 4, 5, 5, 4, 3, 2, 1]
    mean_ic, n = mean_daily_rank_ic(as_of, preds, acts, min_names=5)
    assert n == 2
    assert mean_ic is not None
    assert abs(mean_ic - 1.0) < 1e-9


def test_confidence_gate_improves_when_confident() -> None:
    # Correct when |score| high; wrong when low
    y_dir = [1.0, 1.0, -1.0, -1.0, 1.0, -1.0]
    scores = [0.4, 0.3, -0.35, -0.01, 0.02, 0.01]
    rows = sweep_confidence_gates(y_dir, scores, thresholds=(0.0, 0.2))
    ungated = rows[0]["hit_rate"]
    gated = rows[1]["hit_rate"]
    assert ungated is not None and gated is not None
    assert gated >= ungated
