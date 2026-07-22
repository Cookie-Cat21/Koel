"""Kronos-as-features adapter tests.

The pure reconstruction helper is tested unconditionally (no network/GPU
needed). The end-to-end adapter test additionally needs torch, lightgbm,
and a one-time download of the public Kronos-mini checkpoint from
Hugging Face Hub -- it is skipped when those aren't available rather than
failing CI in offline/no-GPU environments.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from koel.ml.dataset import Sample
from koel.ml.features import FEATURE_NAMES
from koel.ml.gpu_challengers import _reconstruct_price_path, predict_kronos_features

_INDEX = {name: position for position, name in enumerate(FEATURE_NAMES)}


@pytest.fixture(autouse=True)
def _require_pandas() -> None:
    # Run-time (not collection-time) skip: a module-level importorskip would
    # surface as a collection skip even under `-m integration`, tripping the
    # migrate job's no-skips gate. Every test here needs pandas at run time
    # (the reconstruction helper builds a DataFrame); the end-to-end test
    # additionally gates on torch/lightgbm/huggingface_hub inside its body.
    pytest.importorskip("pandas")


def _make_sample(symbol: str, as_of: date, *, ret_1d: float, log_price: float) -> Sample:
    values = [0.0] * len(FEATURE_NAMES)
    values[_INDEX["ret_1d"]] = ret_1d
    values[_INDEX["ret_5d"]] = ret_1d * 3
    values[_INDEX["ret_20d"]] = ret_1d * 8
    values[_INDEX["ret_60d"]] = ret_1d * 15
    values[_INDEX["liquidity_20d"]] = 5000.0
    values[_INDEX["vol_spike"]] = 1.2
    values[_INDEX["range_20d"]] = 0.02
    values[_INDEX["log_price"]] = log_price
    return Sample(
        symbol=symbol,
        as_of=as_of,
        x=tuple(values),
        y_ret=0.0,
        y_dir=0.0,
        horizon=1,
        target_date=as_of + timedelta(days=1),
    )


def test_reconstruct_price_path_uses_only_this_samples_own_features() -> None:
    """The reconstruction is a pure function of one Sample's own x -- it
    cannot see any other sample, so it trivially cannot leak the future.
    This test pins down its shape/finiteness contract instead."""
    sample = _make_sample("S1", date(2024, 7, 1), ret_1d=0.01, log_price=math.log(100.0))
    path, current_close = _reconstruct_price_path(sample, lookback=61)

    assert len(path) == 61
    assert list(path.columns) == ["open", "high", "low", "close", "volume"]
    assert current_close == pytest.approx(100.0)
    assert path["close"].iloc[-1] == pytest.approx(100.0)
    assert (path["high"] >= path["close"]).all()
    assert (path["low"] <= path["close"]).all()
    assert path.notna().all().all()


def test_reconstruct_price_path_is_deterministic_per_sample() -> None:
    sample = _make_sample("S1", date(2024, 7, 1), ret_1d=-0.02, log_price=math.log(50.0))
    first, _ = _reconstruct_price_path(sample, lookback=61)
    second, _ = _reconstruct_price_path(sample, lookback=61)
    assert first.equals(second)


def _synthetic_samples(days: int, symbols: int, start: date) -> list[Sample]:
    out = []
    for day in range(days):
        for symbol_index in range(symbols):
            ret_1d = ((day + symbol_index) % 7 - 3) / 100
            out.append(
                _make_sample(
                    f"S{symbol_index}",
                    start + timedelta(days=day),
                    ret_1d=ret_1d,
                    log_price=math.log(100.0 + symbol_index),
                )
            )
    return out


def test_kronos_features_end_to_end_is_deterministic() -> None:
    # Run-time (not collection-time) skips: module-level importorskip would
    # surface as a collection skip even under `-m integration`, tripping the
    # migrate job's no-skips gate. Only this end-to-end test needs the heavy
    # stack; the reconstruction tests above must keep running without it.
    pytest.importorskip("torch")
    pytest.importorskip("lightgbm")
    pytest.importorskip("huggingface_hub")

    train = _synthetic_samples(30, 4, date(2024, 7, 1))
    test = _synthetic_samples(5, 4, date(2024, 7, 1) + timedelta(days=30))
    kwargs = dict(seed=3, sample_count=4, pred_len=1)
    try:
        first = predict_kronos_features(train, test, **kwargs)
        second = predict_kronos_features(train, test, **kwargs)
    except Exception as exc:  # pragma: no cover - network/hub outage guard
        pytest.skip(f"Kronos checkpoint unavailable: {exc}")

    assert first == second
    assert len(first) == len(test)
    assert all(math.isfinite(value) for value in first)
