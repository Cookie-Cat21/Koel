"""Selective disagreement gate mining tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from koel.ml.distributed import Prediction, PredictionArtifact, ShardSpec, SuccessContract
from koel.ml.selective_disagreement import (
    DisagreementGateGrid,
    align_disagreement_rows,
    evaluate_selective_disagreement,
    select_calibration_gate_disagreement,
)


def _artifact(
    *,
    fold: int,
    model: str,
    score_scale: float = 1.0,
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
            base = 0.80 if high_score else 0.10
            if model == "hgb_two_stage":
                score = base * score_scale + (0.01 if high_score else 0.0)
            else:
                score = base * score_scale
            predictions.append(
                Prediction(
                    partition=partition,
                    symbol=f"S{fold:01d}{i:03d}.N0000",
                    as_of=start + timedelta(days=offset + i),
                    horizon=1,
                    y_dir=1 if hit else -1,
                    score=score,
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


def test_align_disagreement_rows_matches_keys_and_primary_score() -> None:
    artifacts = [
        _artifact(fold=0, model="xgb_two_stage"),
        _artifact(fold=0, model="hgb_two_stage", score_scale=0.95),
    ]
    rows = align_disagreement_rows(artifacts, models=("xgb_two_stage", "hgb_two_stage"))
    assert len(rows) == 200
    high = [row for row in rows if abs(row.primary_score) >= 0.79]
    assert len(high) == 40
    assert all(row.disagreement >= 0.0 for row in high)


def test_disagreement_gate_prefers_low_disagreement_high_score_rows() -> None:
    rows = align_disagreement_rows(
        [
            _artifact(fold=0, model="xgb_two_stage"),
            _artifact(fold=0, model="hgb_two_stage"),
        ],
        models=("xgb_two_stage", "hgb_two_stage"),
    )
    calibration = [row for row in rows if row.partition == "calibration"]
    gate = select_calibration_gate_disagreement(
        calibration,
        contract=SuccessContract(
            target_precision=0.90,
            min_precision_lcb=0.50,
            min_calibration_emits=10,
            min_calibration_lcb=0.50,
        ),
        grid=DisagreementGateGrid(
            coverage_grid=(0.20,),
            abs_score_grid=(),
            max_disagreement_grid=(0.30,),
        ),
    )
    assert gate is not None
    assert gate["score_threshold"] == pytest.approx(0.80)
    assert gate["max_disagreement"] == pytest.approx(0.30)


def test_evaluate_selective_disagreement_applies_calibration_gate_to_test() -> None:
    artifacts = []
    for fold in range(3):
        artifacts.append(_artifact(fold=fold, model="xgb_two_stage"))
        artifacts.append(_artifact(fold=fold, model="hgb_two_stage"))
    report = evaluate_selective_disagreement(
        artifacts,
        models=("xgb_two_stage", "hgb_two_stage"),
        contract=_contract(),
        grid=DisagreementGateGrid(
            coverage_grid=(0.20,),
            abs_score_grid=(),
            max_disagreement_grid=(0.30,),
        ),
    )

    assert report["contract_met"] is True
    assert report["summary"]["emits"] == 60
    assert report["summary"]["hits"] == 54
    assert report["summary"]["precision"] == pytest.approx(0.90)
    assert all(fold["score_threshold"] == pytest.approx(0.80) for fold in report["folds"])


def test_tight_disagreement_ceiling_reduces_emits() -> None:
    from koel.ml.selective_disagreement import _gate_metrics

    artifacts = [
        _artifact(fold=0, model="xgb_two_stage"),
        _artifact(fold=0, model="hgb_two_stage", score_scale=1.001),
    ]
    calibration = [
        row
        for row in align_disagreement_rows(
            artifacts,
            models=("xgb_two_stage", "hgb_two_stage"),
        )
        if row.partition == "calibration"
    ]
    loose = _gate_metrics(
        calibration,
        score_threshold=0.80,
        max_disagreement=0.30,
        confidence_level=0.95,
    )
    tight = _gate_metrics(
        calibration,
        score_threshold=0.80,
        max_disagreement=0.001,
        confidence_level=0.95,
    )
    assert loose["emits"] == 20
    assert tight["emits"] < loose["emits"]
