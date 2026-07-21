"""Distributed ML orchestration tests (no database required)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from koel.ml.distributed import (
    EnsemblePrediction,
    Prediction,
    PredictionArtifact,
    ShardSpec,
    SuccessContract,
    build_training_matrix,
    ensemble_artifacts,
    evaluate_nested_ensemble,
    load_prediction_artifact,
    write_prediction_artifact,
)
from koel.ml.distributed_worker import build_outer_split


def test_training_matrix_is_stable_and_unique() -> None:
    specs = build_training_matrix(
        models=("logistic", "hgb_lmt", "xgb_lmt"),
        outer_folds=6,
        horizons=(1,),
        seeds=(0, 1, 2),
    )
    assert len(specs) == 18
    assert specs[0].shard_id == "h1-f00-logistic"
    assert specs[-1].shard_id == "h1-f05-xgb_lmt"
    assert len({spec.shard_id for spec in specs}) == len(specs)


def test_prediction_artifact_round_trip(tmp_path) -> None:
    path = tmp_path / "shard.predictions.jsonl.gz"
    spec = ShardSpec(
        shard_id="h1-f00-logistic",
        model="logistic",
        outer_fold=0,
        horizon=1,
        seeds=(0, 1),
    )
    predictions = [
        Prediction(
            partition="calibration",
            symbol="A.N0000",
            as_of=date(2025, 1, 1),
            horizon=1,
            y_dir=1,
            score=0.4,
        ),
        Prediction(
            partition="test",
            symbol="A.N0000",
            as_of=date(2025, 2, 1),
            horizon=1,
            y_dir=-1,
            score=-0.3,
        ),
    ]
    write_prediction_artifact(
        path,
        run_id="run-1",
        snapshot_sha256="abc123",
        spec=spec,
        predictions=predictions,
    )
    loaded = load_prediction_artifact(path)
    assert loaded.run_id == "run-1"
    assert loaded.snapshot_sha256 == "abc123"
    assert loaded.spec == spec
    assert list(loaded.predictions) == predictions


def _artifact(
    *,
    model: str,
    fold: int,
    calibration_hits: int = 54,
    test_hits: int = 54,
) -> PredictionArtifact:
    predictions: list[Prediction] = []
    start = date(2025, 1, 1) + timedelta(days=fold * 300)
    for partition, hit_count, offset in (
        ("calibration", calibration_hits, 0),
        ("test", test_hits, 120),
    ):
        for i in range(100):
            high_confidence = i < 60
            hit = i < hit_count if high_confidence else False
            predictions.append(
                Prediction(
                    partition=partition,
                    symbol=f"S{i:03d}.N0000",
                    as_of=start + timedelta(days=offset + i),
                    horizon=1,
                    y_dir=1 if hit else -1,
                    score=(0.40 if model == "logistic" else 0.42)
                    if high_confidence
                    else 0.10,
                )
            )
    spec = ShardSpec(
        shard_id=f"h1-f{fold:02d}-{model}",
        model=model,
        outer_fold=fold,
        horizon=1,
        seeds=(0, 1, 2),
    )
    return PredictionArtifact(
        run_id="run-1",
        snapshot_sha256="snapshot-1",
        spec=spec,
        predictions=tuple(predictions),
    )


def test_nested_ensemble_uses_calibration_gate_and_test_labels() -> None:
    artifacts = [
        _artifact(model=model, fold=fold)
        for fold in range(2)
        for model in ("logistic", "hgb_lmt")
    ]
    rows = ensemble_artifacts(
        artifacts,
        expected_models=("logistic", "hgb_lmt"),
    )
    report = evaluate_nested_ensemble(
        rows,
        contract=SuccessContract(
            target_precision=0.90,
            min_precision_lcb=0.80,
            min_emits=100,
            min_symbols=50,
            min_coverage=0.50,
            max_symbol_share=0.05,
            min_calibration_emits=50,
        ),
    )
    assert report["contract_met"] is True
    assert report["summary"]["emits"] == 120
    assert report["summary"]["hits"] == 108
    assert report["summary"]["precision"] == pytest.approx(0.90)
    assert all(fold["threshold"] == pytest.approx(0.41) for fold in report["folds"])

    failed_artifacts = [
        _artifact(model=model, fold=fold, test_hits=30)
        for fold in range(2)
        for model in ("logistic", "hgb_lmt")
    ]
    failed_rows = ensemble_artifacts(
        failed_artifacts,
        expected_models=("logistic", "hgb_lmt"),
    )
    failed = evaluate_nested_ensemble(
        failed_rows,
        contract=SuccessContract(
            target_precision=0.90,
            min_precision_lcb=0.80,
            min_emits=100,
            min_symbols=50,
            min_coverage=0.50,
            max_symbol_share=0.05,
            min_calibration_emits=50,
        ),
    )
    assert failed["contract_met"] is False
    assert failed["summary"]["precision"] == pytest.approx(0.50)
    assert all(fold["threshold"] == pytest.approx(0.41) for fold in failed["folds"])


def test_ensemble_rejects_missing_model() -> None:
    with pytest.raises(ValueError, match="missing"):
        ensemble_artifacts(
            [_artifact(model="logistic", fold=0)],
            expected_models=("logistic", "hgb_lmt"),
        )


def test_outer_split_reserves_disjoint_lockbox() -> None:
    dates = [date(2000, 1, 1) + timedelta(days=i) for i in range(1200)]
    split = build_outer_split(
        dates,
        outer_fold=5,
        outer_folds=6,
        calibration_days=126,
        test_days=42,
        lockbox_days=63,
        embargo_days=5,
        min_train_days=504,
    )
    assert len(split.calibration_dates) == 126
    assert len(split.test_dates) == 42
    assert len(split.lockbox_dates) == 63
    assert max(split.calibration_train_dates) < min(split.calibration_dates)
    assert max(split.calibration_dates) < min(split.test_dates)
    assert max(split.test_dates) < min(split.lockbox_dates)
    assert not split.test_dates & split.lockbox_dates
