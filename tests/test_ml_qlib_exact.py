"""Exact Qlib adapter tests that do not require optional pyqlib."""

from __future__ import annotations

from datetime import date, timedelta

from koel.ml.dataset import Sample
from koel.ml.qlib_exact import _split_train_valid


def test_exact_qlib_split_is_chronological() -> None:
    start = date(2020, 1, 1)
    samples = [
        Sample(
            symbol="A",
            as_of=start + timedelta(days=index),
            x=(float(index),),
            y_ret=0.01,
            y_dir=1.0,
            horizon=1,
            target_date=start + timedelta(days=index + 1),
        )
        for index in range(30)
    ]
    train, valid = _split_train_valid(samples)
    assert train
    assert valid
    assert max(sample.as_of for sample in train) < min(
        sample.as_of for sample in valid
    )
    assert len(valid) == 10
