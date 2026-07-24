"""Selective gate mining tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from koel.ml.distributed import Prediction, PredictionArtifact, ShardSpec, SuccessContract
from koel.ml.selective_gates import (
    GateGrid,
    evaluate_selective_gates,
)


def _artifact(
    *,
    fold: int,
    model: str = "xgb_two_stage",
    test_hits: int = 18,
) -> PredictionArtifact:
    predictions: list[Prediction] = []
    start = date(2026, 1, 1) + timedelta(days=fold * 100)
    for partition, hit_count, offset in (
        ("calibration", 20, 0),
        ("test", test_hits, 40),
    ):
        for i in range(100):
            high_score = i < 20
            hit = i < hit_count if high_score else False
            predictions.append(
                Prediction(
                    partition=partition,
                    symbol=f"S{fold:01d}{i:03d}.N0000",
                    as_of=start + timedelta(days=offset + i),
                    horizon=1,
                    y_dir=1 if hit else -1,
                    score=0.80 if high_score else 0.10,
                    y_ret=0.01 if hit else -0.01,
                )
            )
    return PredictionArtifact(
        run_id="run-1",
        snapshot_sha256="snapshot-1",
        spec=ShardSpec(
            shard_id=f"rel-h1-f{fold:02d}-{model}",
            model=model,
            outer_fold=fold,
            horizon=1,
            seeds=(0, 1, 2),
            target="relative",
        ),
        predictions=tuple(predictions),
    )


def _contract() -> SuccessContract:
    return SuccessContract(
        target_precision=0.90,
        min_precision_lcb=0.80,
        min_emits=50,
        min_symbols=50,
        min_coverage=0.10,
        min_fold_precision=0.85,
        min_fold_pass_fraction=2 / 3,
        max_symbol_share=0.05,
        min_calibration_emits=10,
        min_calibration_lcb=0.75,
        min_emit_days=50,
        max_session_share=0.05,
        min_fold_emits=10,
    )


def test_selective_gates_apply_calibration_chosen_thresholds_to_test() -> None:
    report = evaluate_selective_gates(
        [_artifact(fold=fold) for fold in range(3)],
        contract=_contract(),
        grid=GateGrid(coverage_grid=(0.20,), abs_score_grid=()),
    )

    assert report["contract_met"] is True
    assert report["summary"]["emits"] == 60
    assert report["summary"]["hits"] == 54
    assert report["summary"]["precision"] == pytest.approx(0.90)
    assert report["summary"]["symbols"] == 60
    assert all(fold["threshold"] == pytest.approx(0.80) for fold in report["folds"])


def test_selective_gates_do_not_use_test_labels_to_reject_bad_gate() -> None:
    report = evaluate_selective_gates(
        [_artifact(fold=fold, test_hits=0) for fold in range(3)],
        contract=_contract(),
        grid=GateGrid(coverage_grid=(0.20,), abs_score_grid=()),
    )

    assert report["contract_met"] is False
    assert report["summary"]["emits"] == 60
    assert report["summary"]["hits"] == 0
    assert all(fold["selected_gate"] is not None for fold in report["folds"])


def test_absolute_score_floor_can_rescue_a_lower_coverage_gate() -> None:
    rows = []
    artifact = _artifact(fold=0)
    for prediction in artifact.predictions:
        if prediction.partition == "calibration":
            index = int(prediction.symbol[2:5])
            rows.append(
                replace(
                    prediction,
                    score=0.90 if index < 10 else 0.40 if index < 50 else 0.05,
                    y_dir=1 if index < 10 else -1,
                )
            )
    selective_rows = [
        row
        for row in evaluate_selective_gates(
            [
                PredictionArtifact(
                    run_id=artifact.run_id,
                    snapshot_sha256=artifact.snapshot_sha256,
                    spec=artifact.spec,
                    predictions=tuple(rows),
                )
            ],
            contract=SuccessContract(
                target_precision=0.90,
                min_precision_lcb=0.50,
                min_emits=1,
                min_symbols=1,
                min_coverage=0.01,
                min_fold_precision=0.0,
                min_fold_pass_fraction=0.0,
                max_symbol_share=1.0,
                min_calibration_emits=5,
                min_calibration_lcb=0.50,
                min_emit_days=1,
                max_session_share=1.0,
                min_fold_emits=1,
            ),
            grid=GateGrid(coverage_grid=(0.50,), abs_score_grid=(0.90,)),
        )["folds"]
    ]

    assert selective_rows[0]["selected_gate"]["threshold"] == pytest.approx(0.90)
    assert selective_rows[0]["selected_gate"]["emits"] == 10
