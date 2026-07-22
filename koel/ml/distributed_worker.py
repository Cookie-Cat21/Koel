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
    TARGETS,
    Prediction,
    ShardSpec,
    _parse_csv_ints,
    write_prediction_artifact,
)
from koel.ml.features import FEATURE_NAMES
from koel.ml.harden import _demean_by_day
from koel.ml.iterate import _enrich_cross_section
from koel.ml.research_features import (
    ResearchBarMetadata,
    build_research_bar_metadata,
    enrich_market_context,
    enrich_research_quality,
    sample_domain,
)
from koel.ml.research_fundamentals import enrich_fundamentals
from koel.ml.snapshot import load_bar_snapshot

SOURCE_IS_CSE_INDEX = len(FEATURE_NAMES)


@dataclass(frozen=True, slots=True)
class OuterSplit:
    calibration_train_dates: frozenset[date]
    calibration_dates: frozenset[date]
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
    if calibration_train_end < min_train_days:
        raise ValueError("not enough history for requested nested split")

    return OuterSplit(
        calibration_train_dates=frozenset(unique_dates[:calibration_train_end]),
        calibration_dates=frozenset(
            unique_dates[calibration_start:calibration_end]
        ),
        test_dates=frozenset(unique_dates[test_start:test_end]),
        lockbox_dates=frozenset(unique_dates[development_end:]),
    )


def _rows_for_dates(
    samples: list[Sample],
    dates: frozenset[date],
    *,
    metadata: dict[tuple[str, date], ResearchBarMetadata],
    domain: str | None = None,
    max_flat_fraction: float | None = None,
) -> list[Sample]:
    """Keep rows whose decision and outcome both remain inside a partition."""
    return [
        sample
        for sample in samples
        if sample.as_of in dates
        and sample.target_date in dates
        and (domain is None or sample_domain(sample, metadata) == domain)
        and (
            max_flat_fraction is None
            or metadata[(sample.symbol, sample.as_of)].flat_fraction_60
            <= max_flat_fraction
        )
    ]


def _feature_matrices(
    train: list[Sample],
    test: list[Sample],
) -> tuple[object, object]:
    import numpy as np

    x_train = np.asarray([sample.x for sample in train], dtype=float)
    x_test = np.asarray([sample.x for sample in test], dtype=float)
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
    return x_train[:, varying], x_test[:, varying]


def _xgb_classifier(*, seed: int, positive_weight: float) -> object:
    from xgboost import XGBClassifier

    return XGBClassifier(
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


def _class_ratio(labels: object) -> float:
    import numpy as np

    values = np.asarray(labels, dtype=int)
    positives = int(values.sum())
    negatives = len(values) - positives
    return negatives / positives if positives else 1.0


def _domain_weights(samples: list[Sample]) -> object:
    """Upweight official-CSE and recent training rows without future inputs."""
    import numpy as np

    latest = max(sample.as_of for sample in samples)
    weights: list[float] = []
    for sample in samples:
        age_days = max(0, (latest - sample.as_of).days)
        recency = 2.0 ** (-age_days / 1825.0)
        source_is_cse = (
            len(sample.x) > SOURCE_IS_CSE_INDEX
            and math.isfinite(sample.x[SOURCE_IS_CSE_INDEX])
            and sample.x[SOURCE_IS_CSE_INDEX] >= 0.5
        )
        weights.append(recency * (20.0 if source_is_cse else 1.0))
    values = np.asarray(weights, dtype=float)
    mean = float(np.mean(values))
    return values / mean if mean > 0 else values


def _fit_predict_two_stage(
    *,
    model: str,
    train: list[Sample],
    test: list[Sample],
    seed: int,
) -> list[float]:
    """Predict material-move probability, then conditional direction."""
    import numpy as np

    nonflat = [sample for sample in train if sample.y_dir != 0]
    if len(nonflat) < 100 or len(test) < 10:
        raise ValueError("insufficient train/test samples")
    material_cut = float(np.median([abs(sample.y_ret) for sample in nonflat]))
    direction_rows = [
        sample for sample in nonflat if abs(sample.y_ret) >= material_cut
    ]
    x_train, x_test = _feature_matrices(train, test)
    train_index = {id(sample): index for index, sample in enumerate(train)}
    direction_indices = [train_index[id(sample)] for sample in direction_rows]
    y_direction = np.asarray(
        [1 if sample.y_dir > 0 else 0 for sample in direction_rows],
        dtype=int,
    )
    y_material = np.asarray(
        [1 if abs(sample.y_ret) >= material_cut else 0 for sample in train],
        dtype=int,
    )
    if len(set(y_direction.tolist())) < 2 or len(set(y_material.tolist())) < 2:
        raise ValueError("two-stage training split contains one class")

    if model == "hgb_two_stage":
        from sklearn.ensemble import HistGradientBoostingClassifier

        direction_model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=6,
            max_iter=250,
            l2_regularization=1.0,
            random_state=seed,
        )
        material_model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=4,
            max_iter=200,
            l2_regularization=1.0,
            random_state=seed + 10_000,
        )
    else:
        direction_model = _xgb_classifier(
            seed=seed,
            positive_weight=_class_ratio(y_direction),
        )
        material_model = _xgb_classifier(
            seed=seed + 10_000,
            positive_weight=_class_ratio(y_material),
        )
    direction_model.fit(x_train[direction_indices], y_direction)
    material_model.fit(x_train, y_material)
    direction_margin = direction_model.predict_proba(x_test)[:, 1] - 0.5
    material_probability = material_model.predict_proba(x_test)[:, 1]
    return [
        float(direction * magnitude)
        for direction, magnitude in zip(
            direction_margin,
            material_probability,
            strict=True,
        )
    ]


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
    if model == "qlib_lgb_native":
        from koel.ml.challengers import predict_qlib_lightgbm

        return predict_qlib_lightgbm(train, test, seed=seed)
    if model == "double_ensemble_native":
        from koel.ml.challengers import predict_native_double_ensemble

        return predict_native_double_ensemble(train, test, seed=seed)
    if model == "ridge_return":
        from koel.ml.cpu_challengers import predict_ridge_return

        return predict_ridge_return(train, test, seed=seed)
    if model == "hgb_regressor":
        from koel.ml.cpu_challengers import predict_hgb_regressor

        return predict_hgb_regressor(train, test, seed=seed)
    if model == "xgb_regressor":
        from koel.ml.cpu_challengers import predict_xgb_regressor

        return predict_xgb_regressor(train, test, seed=seed)
    if model == "hgb_bagged":
        from koel.ml.cpu_challengers import predict_hgb_bagged

        return predict_hgb_bagged(train, test, seed=seed)
    if model == "hgb_deep":
        from koel.ml.cpu_challengers import predict_hgb_deep

        return predict_hgb_deep(train, test, seed=seed)
    if model == "hgb_weighted":
        from koel.ml.cpu_challengers import predict_hgb_weighted

        return predict_hgb_weighted(train, test, seed=seed)
    if model == "xgb_rank_pairwise":
        from koel.ml.cpu_challengers import predict_xgb_rank_pairwise

        return predict_xgb_rank_pairwise(train, test, seed=seed)
    if model == "xgb_rank_ndcg":
        from koel.ml.cpu_challengers import predict_xgb_rank_ndcg

        return predict_xgb_rank_ndcg(train, test, seed=seed)
    if model == "lgb_lambdarank":
        from koel.ml.cpu_challengers import predict_lgb_lambdarank

        return predict_lgb_lambdarank(train, test, seed=seed)
    if model == "blend_de_lgb":
        from koel.ml.cpu_challengers import predict_blend_de_lgb

        return predict_blend_de_lgb(train, test, seed=seed)
    if model == "blend_de_ridge":
        from koel.ml.cpu_challengers import predict_blend_de_ridge

        return predict_blend_de_ridge(train, test, seed=seed)
    if model in {"qlib_lgb_exact", "qlib_double_ensemble_exact"}:
        from koel.ml.qlib_exact import predict_exact_qlib

        provider_uri = os.environ.get("QLIB_PROVIDER_URI")
        if not provider_uri:
            raise ValueError("QLIB_PROVIDER_URI is required for exact Qlib models")
        return predict_exact_qlib(
            train,
            test,
            model_name=model,
            provider_uri=provider_uri,
            seed=seed,
        )
    if model == "qlib_tra":
        from koel.ml.gpu_challengers import predict_qlib_tra

        return predict_qlib_tra(train, test, seed=seed)
    if model == "master":
        from koel.ml.gpu_challengers import predict_master

        return predict_master(train, test, seed=seed)
    if model == "kronos_features":
        from koel.ml.gpu_challengers import predict_kronos_features

        return predict_kronos_features(train, test, seed=seed)
    if model.endswith("_two_stage"):
        return _fit_predict_two_stage(
            model=model,
            train=train,
            test=test,
            seed=seed,
        )
    selected = [sample for sample in train if sample.y_dir != 0]
    domain_weighted = model.endswith("_domain")
    if model.endswith("_lmt") or domain_weighted:
        magnitudes = np.asarray(
            [abs(sample.y_ret) for sample in selected], dtype=float
        )
        threshold = float(np.median(magnitudes))
        selected = [
            sample for sample in selected if abs(sample.y_ret) >= threshold
        ]
    if len(selected) < 100 or len(test) < 10:
        raise ValueError("insufficient train/test samples")

    x_train, x_test = _feature_matrices(selected, test)
    y_train = np.asarray(
        [1 if sample.y_dir > 0 else 0 for sample in selected], dtype=int
    )
    if len(set(y_train.tolist())) < 2:
        raise ValueError("training split contains one class")

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
    elif model in {"hgb_lmt", "hgb_domain"}:
        from sklearn.ensemble import HistGradientBoostingClassifier

        classifier = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=6,
            max_iter=250,
            l2_regularization=1.0,
            random_state=seed,
        )
    elif model in {"lgb_lmt", "lgb_domain"}:
        from lightgbm import LGBMClassifier

        classifier = LGBMClassifier(
            n_estimators=300,
            learning_rate=0.04,
            num_leaves=31,
            min_child_samples=80,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=2.0,
            class_weight="balanced",
            n_jobs=max(1, int(os.environ.get("ML_WORKER_THREADS", "4"))),
            random_state=seed,
            verbosity=-1,
        )
    else:
        classifier = _xgb_classifier(
            seed=seed,
            positive_weight=_class_ratio(y_train),
        )
    sample_weight = _domain_weights(selected) if domain_weighted else None
    if sample_weight is None:
        classifier.fit(x_train, y_train)
    else:
        classifier.fit(x_train, y_train, sample_weight=sample_weight)
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
    evaluation_domain: str,
    max_flat_fraction: float,
) -> dict[str, int | str]:
    """Train calibration/test fits for one matrix shard and write predictions."""
    if evaluation_domain not in {"all", "cse", "yahoo"}:
        raise ValueError("evaluation_domain must be all, cse, or yahoo")
    if not 0 <= max_flat_fraction <= 1:
        raise ValueError("max_flat_fraction must be between 0 and 1")
    domain_filter = None if evaluation_domain == "all" else evaluation_domain
    loaded = load_bar_snapshot(snapshot_dir)
    metadata = build_research_bar_metadata(
        loaded.series,
        dataset=loaded.manifest.dataset,
    )
    base = build_samples(
        loaded.series,
        horizon=spec.horizon,
        min_history=min_history,
        max_abs_return=max_abs_return,
        include_flat=spec.target == "absolute",
    )
    research = enrich_research_quality(base, metadata)
    research = enrich_fundamentals(research, loaded.fundamentals)
    research = enrich_market_context(research)
    if spec.target == "relative":
        research = _demean_by_day(research)
    samples = _enrich_cross_section(research)
    dates = sorted(
        {
            bar.trade_date
            for symbol_bars in loaded.series.values()
            for bar in symbol_bars
        }
    )
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

    calibration_train = _rows_for_dates(
        samples,
        split.calibration_train_dates,
        metadata=metadata,
    )
    calibration = _rows_for_dates(
        samples,
        split.calibration_dates,
        metadata=metadata,
        domain=domain_filter,
        max_flat_fraction=max_flat_fraction,
    )
    test = _rows_for_dates(
        samples,
        split.test_dates,
        metadata=metadata,
        domain=domain_filter,
        max_flat_fraction=max_flat_fraction,
    )
    evaluation_rows = calibration + test
    evaluation_scores = _fit_predict_average(
        model=spec.model,
        train=calibration_train,
        test=evaluation_rows,
        seeds=spec.seeds,
    )
    calibration_scores = evaluation_scores[: len(calibration)]
    test_scores = evaluation_scores[len(calibration) :]

    predictions = [
        Prediction(
            partition="calibration",
            symbol=sample.symbol,
            as_of=sample.as_of,
            horizon=sample.horizon,
            y_dir=1 if sample.y_dir > 0 else -1 if sample.y_dir < 0 else 0,
            score=score,
            y_ret=sample.y_ret,
            target_date=sample.target_date,
            domain=sample_domain(sample, metadata) or "unknown",
        )
        for sample, score in zip(calibration, calibration_scores, strict=True)
    ]
    predictions.extend(
        Prediction(
            partition="test",
            symbol=sample.symbol,
            as_of=sample.as_of,
            horizon=sample.horizon,
            y_dir=1 if sample.y_dir > 0 else -1 if sample.y_dir < 0 else 0,
            score=score,
            y_ret=sample.y_ret,
            target_date=sample.target_date,
            domain=sample_domain(sample, metadata) or "unknown",
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
        "target": spec.target,
        "evaluation_domain": evaluation_domain,
        "max_flat_fraction": max_flat_fraction,
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
    parser.add_argument("--target", choices=TARGETS, default="absolute")
    parser.add_argument(
        "--evaluation-domain",
        choices=("all", "cse", "yahoo"),
        default="cse",
    )
    parser.add_argument("--calibration-days", type=int, default=126)
    parser.add_argument("--test-days", type=int, default=42)
    parser.add_argument("--lockbox-days", type=int, default=63)
    parser.add_argument("--min-train-days", type=int, default=504)
    parser.add_argument("--min-history", type=int, default=252)
    parser.add_argument("--max-abs-return", type=float, default=0.35)
    parser.add_argument("--max-flat-fraction", type=float, default=0.40)
    args = parser.parse_args(argv)
    spec = ShardSpec(
        shard_id=args.shard_id,
        model=args.model,
        outer_fold=args.outer_fold,
        horizon=args.horizon,
        seeds=_parse_csv_ints(args.seeds),
        target=args.target,
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
        evaluation_domain=args.evaluation_domain,
        max_flat_fraction=args.max_flat_fraction,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
