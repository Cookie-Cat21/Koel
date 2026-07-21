"""One fold/model worker for the distributed nested ML evaluation."""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from koel.ml.dataset import Sample, build_samples
from koel.ml.distributed import (
    ALLOWED_MODELS,
    Prediction,
    ShardSpec,
    _parse_csv_ints,
    write_prediction_artifact,
)
from koel.ml.harden import _demean_by_day
from koel.ml.iterate import _enrich_cross_section
from koel.ml.snapshot import load_bar_snapshot


@dataclass(frozen=True, slots=True)
class OuterSplit:
    calibration_train_dates: frozenset[date]
    calibration_dates: frozenset[date]
    test_train_dates: frozenset[date]
    test_dates: frozenset[date]
    lockbox_dates: frozenset[date]


def build_outer_split(
    dates: list[date],
    *,
    outer_fold: int,
    outer_folds: int,
    calibration_days: int,
    test_days: int,
    lockbox_days: int,
    embargo_days: int,
    min_train_days: int,
) -> OuterSplit:
    """Create one nested chronological split while preserving a final lockbox."""
    unique_dates = sorted(set(dates))
    if outer_folds < 2:
        raise ValueError("outer_folds must be at least 2")
    if not 0 <= outer_fold < outer_folds:
        raise ValueError("outer_fold is outside configured fold range")
    if min(calibration_days, test_days, lockbox_days, embargo_days) < 1:
        raise ValueError("split durations and embargo must be positive")

    development_end = len(unique_dates) - lockbox_days
    first_test_start = development_end - outer_folds * test_days
    test_start = first_test_start + outer_fold * test_days
    test_end = test_start + test_days
    calibration_end = test_start - embargo_days
    calibration_start = calibration_end - calibration_days
    calibration_train_end = calibration_start - embargo_days
    test_train_end = test_start - embargo_days
    if calibration_train_end < min_train_days:
        raise ValueError("not enough history for requested nested split")

    return OuterSplit(
        calibration_train_dates=frozenset(unique_dates[:calibration_train_end]),
        calibration_dates=frozenset(
            unique_dates[calibration_start:calibration_end]
        ),
        test_train_dates=frozenset(unique_dates[:test_train_end]),
        test_dates=frozenset(unique_dates[test_start:test_end]),
        lockbox_dates=frozenset(unique_dates[development_end:]),
    )


def _rows_for_dates(samples: list[Sample], dates: frozenset[date]) -> list[Sample]:
    return [sample for sample in samples if sample.as_of in dates]


def _fit_predict_one(
    *,
    model: str,
    train: list[Sample],
    test: list[Sample],
    seed: int,
) -> list[float]:
    import numpy as np

    if model not in ALLOWED_MODELS:
        raise ValueError(f"unsupported model {model}")
    selected = train
    if model.endswith("_lmt"):
        magnitudes = np.asarray([abs(sample.y_ret) for sample in train], dtype=float)
        threshold = float(np.median(magnitudes))
        selected = [
            sample for sample in train if abs(sample.y_ret) >= threshold
        ]
    if len(selected) < 100 or len(test) < 10:
        raise ValueError("insufficient train/test samples")

    x_train = np.asarray([sample.x for sample in selected], dtype=float)
    x_test = np.asarray([sample.x for sample in test], dtype=float)
    y_train = np.asarray(
        [1 if sample.y_dir > 0 else 0 for sample in selected], dtype=int
    )
    if len(set(y_train.tolist())) < 2:
        raise ValueError("training split contains one class")

    x_train[~np.isfinite(x_train)] = np.nan
    x_test[~np.isfinite(x_test)] = np.nan
    medians = np.nanmedian(x_train, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    for matrix in (x_train, x_test):
        missing = np.where(np.isnan(matrix))
        matrix[missing] = np.take(medians, missing[1])
    varying = np.ptp(x_train, axis=0) > 1e-12
    if not np.any(varying):
        raise ValueError("training split has no varying features")
    x_train = x_train[:, varying]
    x_test = x_test[:, varying]

    positives = int(y_train.sum())
    negatives = len(y_train) - positives
    positive_weight = negatives / positives if positives else 1.0
    if model == "logistic":
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        classifier = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=0.5,
                class_weight="balanced",
                max_iter=500,
                random_state=seed,
            ),
        )
    elif model == "hgb_lmt":
        from sklearn.ensemble import HistGradientBoostingClassifier

        classifier = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=6,
            max_iter=250,
            l2_regularization=1.0,
            random_state=seed,
        )
    else:
        from xgboost import XGBClassifier

        classifier = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            min_child_weight=20,
            reg_lambda=2.0,
            scale_pos_weight=positive_weight,
            eval_metric="logloss",
            tree_method="hist",
            n_jobs=max(1, int(os.environ.get("ML_WORKER_THREADS", "4"))),
            random_state=seed,
        )
    classifier.fit(x_train, y_train)
    probabilities = classifier.predict_proba(x_test)[:, 1]
    return [float(probability - 0.5) for probability in probabilities]


def _fit_predict_average(
    *,
    model: str,
    train: list[Sample],
    test: list[Sample],
    seeds: tuple[int, ...],
) -> list[float]:
    import numpy as np

    predictions = [
        _fit_predict_one(model=model, train=train, test=test, seed=seed)
        for seed in seeds
    ]
    matrix = np.asarray(predictions, dtype=float)
    return [float(value) for value in np.mean(matrix, axis=0)]


def run_worker(
    *,
    snapshot_dir: Path,
    output: Path,
    run_id: str,
    spec: ShardSpec,
    outer_folds: int,
    calibration_days: int,
    test_days: int,
    lockbox_days: int,
    min_train_days: int,
    min_history: int,
    max_abs_return: float,
) -> dict[str, int | str]:
    """Train calibration/test fits for one matrix shard and write predictions."""
    loaded = load_bar_snapshot(snapshot_dir)
    base = build_samples(
        loaded.series,
        horizon=spec.horizon,
        min_history=min_history,
        max_abs_return=max_abs_return,
    )
    samples = _enrich_cross_section(_demean_by_day(base))
    dates = sorted({sample.as_of for sample in samples})
    split = build_outer_split(
        dates,
        outer_fold=spec.outer_fold,
        outer_folds=outer_folds,
        calibration_days=calibration_days,
        test_days=test_days,
        lockbox_days=lockbox_days,
        embargo_days=max(5, spec.horizon),
        min_train_days=min_train_days,
    )

    calibration_train = _rows_for_dates(samples, split.calibration_train_dates)
    calibration = _rows_for_dates(samples, split.calibration_dates)
    test_train = _rows_for_dates(samples, split.test_train_dates)
    test = _rows_for_dates(samples, split.test_dates)
    calibration_scores = _fit_predict_average(
        model=spec.model,
        train=calibration_train,
        test=calibration,
        seeds=spec.seeds,
    )
    test_scores = _fit_predict_average(
        model=spec.model,
        train=test_train,
        test=test,
        seeds=spec.seeds,
    )

    predictions = [
        Prediction(
            partition="calibration",
            symbol=sample.symbol,
            as_of=sample.as_of,
            horizon=sample.horizon,
            y_dir=1 if sample.y_dir > 0 else -1,
            score=score,
        )
        for sample, score in zip(calibration, calibration_scores, strict=True)
    ]
    predictions.extend(
        Prediction(
            partition="test",
            symbol=sample.symbol,
            as_of=sample.as_of,
            horizon=sample.horizon,
            y_dir=1 if sample.y_dir > 0 else -1,
            score=score,
        )
        for sample, score in zip(test, test_scores, strict=True)
    )
    write_prediction_artifact(
        output,
        run_id=run_id,
        snapshot_sha256=loaded.manifest.bars_sha256,
        spec=spec,
        predictions=predictions,
    )
    return {
        "shard_id": spec.shard_id,
        "model": spec.model,
        "calibration_rows": len(calibration),
        "test_rows": len(test),
        "lockbox_days": len(split.lockbox_dates),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run one distributed ML shard")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--model", choices=ALLOWED_MODELS, required=True)
    parser.add_argument("--outer-fold", type=int, required=True)
    parser.add_argument("--outer-folds", type=int, default=6)
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--calibration-days", type=int, default=126)
    parser.add_argument("--test-days", type=int, default=42)
    parser.add_argument("--lockbox-days", type=int, default=63)
    parser.add_argument("--min-train-days", type=int, default=504)
    parser.add_argument("--min-history", type=int, default=252)
    parser.add_argument("--max-abs-return", type=float, default=0.50)
    args = parser.parse_args(argv)
    spec = ShardSpec(
        shard_id=args.shard_id,
        model=args.model,
        outer_fold=args.outer_fold,
        horizon=args.horizon,
        seeds=_parse_csv_ints(args.seeds),
    )
    result = run_worker(
        snapshot_dir=args.snapshot,
        output=args.output,
        run_id=args.run_id,
        spec=spec,
        outer_folds=args.outer_folds,
        calibration_days=args.calibration_days,
        test_days=args.test_days,
        lockbox_days=args.lockbox_days,
        min_train_days=args.min_train_days,
        min_history=args.min_history,
        max_abs_return=args.max_abs_return,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
