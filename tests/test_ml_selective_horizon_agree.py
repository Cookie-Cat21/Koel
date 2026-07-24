"""Horizon-agreement selective alignment keeps only same-sign scores."""

from __future__ import annotations

from datetime import date

from koel.ml.distributed import Prediction, PredictionArtifact, ShardSpec
from koel.ml.selective_horizon_agree import align_horizon_agree_rows


def _artifact(
    *,
    model: str,
    horizon: int,
    outer_fold: int,
    rows: list[Prediction],
) -> PredictionArtifact:
    return PredictionArtifact(
        run_id="test-run",
        snapshot_sha256="a" * 64,
        spec=ShardSpec(
            shard_id=f"rel-h{horizon}-f{outer_fold:02d}-{model}",
            model=model,
            outer_fold=outer_fold,
            horizon=horizon,
            seeds=(0,),
            target="relative",
        ),
        predictions=tuple(rows),
    )


def test_align_horizon_agree_keeps_same_sign_only() -> None:
    day = date(2026, 7, 1)
    primary = _artifact(
        model="xgb_two_stage",
        horizon=1,
        outer_fold=0,
        rows=[
            Prediction(
                partition="test",
                symbol="AAA.N0000",
                as_of=day,
                horizon=1,
                y_dir=1,
                score=0.2,
                y_ret=0.01,
                target_date=day,
                domain="cse",
            ),
            Prediction(
                partition="test",
                symbol="BBB.N0000",
                as_of=day,
                horizon=1,
                y_dir=-1,
                score=-0.3,
                y_ret=-0.01,
                target_date=day,
                domain="cse",
            ),
        ],
    )
    secondary = _artifact(
        model="xgb_two_stage",
        horizon=3,
        outer_fold=0,
        rows=[
            Prediction(
                partition="test",
                symbol="AAA.N0000",
                as_of=day,
                horizon=3,
                y_dir=1,
                score=0.1,
                y_ret=0.02,
                target_date=day,
                domain="cse",
            ),
            Prediction(
                partition="test",
                symbol="BBB.N0000",
                as_of=day,
                horizon=3,
                y_dir=1,
                score=0.4,  # disagrees with primary short
                y_ret=0.02,
                target_date=day,
                domain="cse",
            ),
        ],
    )
    rows = align_horizon_agree_rows([primary], [secondary])
    assert len(rows) == 1
    assert rows[0].symbol == "AAA.N0000"
    assert rows[0].primary_score > 0
    assert rows[0].secondary_score > 0
