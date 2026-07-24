"""GPU challenger adapter tests (skipped when torch/qlib are unavailable)."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from koel.ml.dataset import Sample
from koel.ml.gpu_challengers import predict_master, predict_qlib_tra


@pytest.fixture(autouse=True)
def _require_gpu_stack() -> None:
    # Run-time (not collection-time) skip: a module-level importorskip would
    # surface as a collection skip even under `-m integration`, tripping the
    # migrate job's no-skips gate for a suite these tests aren't part of.
    # Importing koel.ml.gpu_challengers itself is safe without torch/qlib --
    # it lazy-imports every heavy dependency inside the function bodies.
    pytest.importorskip("torch")
    pytest.importorskip("qlib")


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
                    x=tuple(
                        feature + offset * 0.01 for offset in range(15)
                    ),
                    y_ret=realized,
                    y_dir=1.0 if realized > 0 else -1.0,
                    horizon=1,
                    target_date=start + timedelta(days=day + 1),
                )
            )
    return out


_TRA_KWARGS = dict(n_epochs=2, seq_len=5, batch_size=16)


def test_qlib_tra_is_deterministic() -> None:
    train, test = _samples(60), _samples(20, start=date(2020, 1, 1) + timedelta(days=60))
    first = predict_qlib_tra(train, test, seed=3, **_TRA_KWARGS)
    second = predict_qlib_tra(train, test, seed=3, **_TRA_KWARGS)
    assert first == second
    assert len(first) == len(test)
    assert all(math.isfinite(value) for value in first)


def test_qlib_tra_predictions_unaffected_by_future_test_labels() -> None:
    """Poisoning later test-date labels must not change earlier test-date
    predictions. The daily eval loop processes days in chronological order
    and each day's window looks strictly backward, so a later day's label
    (only used to compute *that* day's own loss/memory write) cannot reach
    an earlier day's already-computed prediction. Keeping the test set's
    size/date range fixed (only mutating later labels) avoids conflating
    this with the adapter's flat-array position bookkeeping."""
    train = _samples(60)
    base_start = date(2020, 1, 1) + timedelta(days=60)
    test_rows = _samples(15, start=base_start)
    midpoint = base_start + timedelta(days=7)

    poisoned = [
        Sample(
            symbol=sample.symbol,
            as_of=sample.as_of,
            x=sample.x,
            y_ret=sample.y_ret * 10,
            y_dir=sample.y_dir,
            horizon=sample.horizon,
            target_date=sample.target_date,
        )
        if sample.as_of > midpoint
        else sample
        for sample in test_rows
    ]

    clean_pred = predict_qlib_tra(train, test_rows, seed=5, **_TRA_KWARGS)
    poisoned_pred = predict_qlib_tra(train, poisoned, seed=5, **_TRA_KWARGS)

    early = [
        index for index, sample in enumerate(test_rows) if sample.as_of <= midpoint
    ]
    assert early, "expected at least one pre-midpoint test row"
    assert [clean_pred[index] for index in early] == [
        poisoned_pred[index] for index in early
    ]


_MASTER_KWARGS = dict(n_epochs=3, seq_len=5, market_context_width=5)


def test_master_is_deterministic() -> None:
    train, test = _samples(60), _samples(20, start=date(2020, 1, 1) + timedelta(days=60))
    first = predict_master(train, test, seed=3, **_MASTER_KWARGS)
    second = predict_master(train, test, seed=3, **_MASTER_KWARGS)
    assert first == second
    assert len(first) == len(test)
    assert all(math.isfinite(value) for value in first)


def test_master_window_has_no_future_leakage() -> None:
    """A window built for an earlier date must be unaffected by poisoning
    (multiplying) feature values on later dates for the same symbol --
    ``_windowed_by_symbol`` only ever looks strictly backward."""
    from koel.ml.gpu_challengers import _windowed_by_symbol

    samples = _samples(30)
    mid = date(2020, 1, 1) + timedelta(days=15)

    poisoned = [
        Sample(
            symbol=sample.symbol,
            as_of=sample.as_of,
            x=tuple(value * 100 for value in sample.x),
            y_ret=sample.y_ret,
            y_dir=sample.y_dir,
            horizon=sample.horizon,
            target_date=sample.target_date,
        )
        if sample.as_of > mid
        else sample
        for sample in samples
    ]

    clean_windows = _windowed_by_symbol(samples, seq_len=5)
    poisoned_windows = _windowed_by_symbol(poisoned, seq_len=5)

    early_keys = [key for key in clean_windows if key[1] <= mid]
    assert early_keys
    for key in early_keys:
        assert (clean_windows[key] == poisoned_windows[key]).all()


def test_master_requires_gate_columns_smaller_than_feature_count() -> None:
    train, test = _samples(30), _samples(5, start=date(2020, 1, 1) + timedelta(days=30))
    with pytest.raises(ValueError):
        predict_master(train, test, seed=1, n_epochs=1, seq_len=5, market_context_width=99)
