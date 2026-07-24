from __future__ import annotations

from datetime import date, timedelta

import pytest

from koel.ml.distributed import Prediction, ShardSpec, write_prediction_artifact
from koel.ml.ensemble_stack import (
    WeightCandidate,
    default_weight_grid,
    evaluate_stack,
    load_survivor_rows,
)


def _write_artifact(
    tmp_path,
    *,
    model: str,
    fold: int,
    calibration_scores: list[float],
    test_scores: list[float],
    returns: list[float],
) -> None:
    predictions: list[Prediction] = []
    for partition, offset, scores in (
        ("calibration", 0, calibration_scores),
        ("test", 10, test_scores),
    ):
        for day_offset in range(2):
            as_of = date(2026, 1, 1) + timedelta(days=fold * 30 + offset + day_offset)
            for index, (score, realized) in enumerate(zip(scores, returns, strict=True)):
                predictions.append(
                    Prediction(
                        partition=partition,
                        symbol=f"S{index:02d}.N0000",
                        as_of=as_of,
                        horizon=1,
                        y_dir=1 if realized > 0 else -1,
                        score=score,
                        y_ret=realized,
                        target_date=as_of + timedelta(days=1),
                        domain="synthetic",
                    )
                )
    spec = ShardSpec(
        shard_id=f"rel-h1-f{fold:02d}-{model}",
        model=model,
        outer_fold=fold,
        horizon=1,
        seeds=(0,),
        target="relative",
    )
    write_prediction_artifact(
        tmp_path / f"{spec.shard_id}.predictions.jsonl.gz",
        run_id="synthetic-stack",
        snapshot_sha256="snapshot-1",
        spec=spec,
        predictions=predictions,
    )


def test_weight_grid_is_predeclared_and_keeps_blends() -> None:
    models = ("xgb_two_stage", "hgb_lmt", "hgb_deep")
    grid = default_weight_grid(models)

    assert grid[0].label == "equal_all"
    assert all(sum(candidate.weights.values()) == pytest.approx(1.0) for candidate in grid)
    assert all(
        sum(1 for weight in candidate.weights.values() if weight > 0) >= 2
        for candidate in grid
    )


def test_rank_average_and_calibration_selected_stack_synthetic_artifacts(tmp_path) -> None:
    models = ("xgb_two_stage", "hgb_lmt")
    returns = [-0.03, -0.02, -0.01, 0.01, 0.02, 0.03]
    good = [-3, -2, -1, 1, 2, 3]
    bad = [3, 2, 1, -1, -2, -3]
    for fold in range(2):
        _write_artifact(
            tmp_path,
            model="xgb_two_stage",
            fold=fold,
            calibration_scores=good,
            test_scores=bad,
            returns=returns,
        )
        _write_artifact(
            tmp_path,
            model="hgb_lmt",
            fold=fold,
            calibration_scores=bad,
            test_scores=good,
            returns=returns,
        )

    rows = load_survivor_rows(tmp_path, models=models)
    payload = evaluate_stack(
        rows,
        models=models,
        cost_bps=0.0,
        weight_grid=(
            WeightCandidate("equal", {"xgb_two_stage": 0.5, "hgb_lmt": 0.5}),
            WeightCandidate("xgb75", {"xgb_two_stage": 0.75, "hgb_lmt": 0.25}),
            WeightCandidate("hgb75", {"xgb_two_stage": 0.25, "hgb_lmt": 0.75}),
        ),
    )

    assert payload["blends"]["equal_raw"]["test"]["rank_ic"] is None
    selected = payload["blends"]["cal_selected_rank_weight"]
    assert [row["label"] for row in selected["fold_selections"]] == ["xgb75", "xgb75"]
    assert selected["calibration"]["rank_ic"] == pytest.approx(1.0)
    assert selected["test"]["rank_ic"] == pytest.approx(-1.0)
    assert selected["test"]["balanced_accuracy"] == pytest.approx(0.0)
