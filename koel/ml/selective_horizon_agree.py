"""Selective gates requiring multi-horizon score sign agreement.

Loads nested prediction shards for the same model at two horizons (typically
h1 + h3), keeps rows where scores agree in sign, then mines coverage / abs-score
gates on calibration only. Research / SuccessContract offline only — never
writes live policies, forecast_points, or Telegram.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from koel.ml.distributed import (
    PredictionArtifact,
    SuccessContract,
    load_prediction_artifact,
    wilson_lower_bound,
)
from koel.ml.selective_gates import (
    DEFAULT_ABS_SCORE_GRID,
    DEFAULT_COVERAGE_GRID,
    GateGrid,
    SelectiveRow,
    _contract_checks,
    _is_hit,
    select_calibration_gate_dense,
)

DEFAULT_CONTRACT = SuccessContract()
DEFAULT_GATE_GRID = GateGrid()


@dataclass(frozen=True, slots=True)
class HorizonAgreeRow:
    outer_fold: int
    partition: str
    symbol: str
    as_of: date
    primary_horizon: int
    secondary_horizon: int
    y_dir: int
    primary_score: float
    secondary_score: float
    y_ret: float | None
    target_date: date | None
    domain: str


def _parse_float_csv(raw: str) -> tuple[float, ...]:
    if raw.strip() == "":
        return ()
    values = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("grid values must be positive finite numbers")
    return tuple(sorted(set(values)))


def load_model_nested(
    nested_dir: Path,
    *,
    model: str,
) -> list[PredictionArtifact]:
    paths = sorted(nested_dir.glob(f"*-{model}.predictions.jsonl.gz"))
    if not paths:
        raise FileNotFoundError(
            f"no prediction artifacts for {model} in {nested_dir}"
        )
    artifacts: list[PredictionArtifact] = []
    for path in paths:
        artifact = load_prediction_artifact(path)
        if artifact.spec.model != model:
            raise ValueError(
                f"{path} contains model {artifact.spec.model}, not {model}"
            )
        artifacts.append(artifact)
    return artifacts


def _index_predictions(
    artifacts: Sequence[PredictionArtifact],
) -> dict[tuple[int, str, str, date], tuple[float, int, float | None, date | None, str, int]]:
    """Map (fold, partition, symbol, as_of) -> score payload."""
    out: dict[
        tuple[int, str, str, date],
        tuple[float, int, float | None, date | None, str, int],
    ] = {}
    for artifact in artifacts:
        for row in artifact.predictions:
            if row.partition not in {"calibration", "test"}:
                continue
            if not math.isfinite(row.score) or row.score == 0:
                continue
            key = (
                int(artifact.spec.outer_fold),
                row.partition,
                row.symbol,
                row.as_of,
            )
            out[key] = (
                float(row.score),
                int(row.y_dir),
                float(row.y_ret) if row.y_ret is not None else None,
                row.target_date,
                str(row.domain or "unknown"),
                int(artifact.spec.horizon),
            )
    return out


def align_horizon_agree_rows(
    primary_artifacts: Sequence[PredictionArtifact],
    secondary_artifacts: Sequence[PredictionArtifact],
) -> list[HorizonAgreeRow]:
    """Keep rows where primary and secondary scores agree in sign."""
    primary = _index_predictions(primary_artifacts)
    secondary = _index_predictions(secondary_artifacts)
    rows: list[HorizonAgreeRow] = []
    for key, payload in primary.items():
        other = secondary.get(key)
        if other is None:
            continue
        p_score, p_dir, p_ret, p_target, domain, p_h = payload
        s_score, _s_dir, _s_ret, _s_target, _s_domain, s_h = other
        if p_score == 0 or s_score == 0:
            continue
        if (p_score > 0) != (s_score > 0):
            continue
        rows.append(
            HorizonAgreeRow(
                outer_fold=key[0],
                partition=key[1],
                symbol=key[2],
                as_of=key[3],
                primary_horizon=p_h,
                secondary_horizon=s_h,
                y_dir=p_dir,
                primary_score=p_score,
                secondary_score=s_score,
                y_ret=p_ret,
                target_date=p_target,
                domain=domain,
            )
        )
    return rows


def _to_selective(rows: Sequence[HorizonAgreeRow]) -> list[SelectiveRow]:
    return [
        SelectiveRow(
            outer_fold=row.outer_fold,
            partition=row.partition,
            symbol=row.symbol,
            as_of=row.as_of,
            horizon=row.primary_horizon,
            y_dir=row.y_dir,
            score=row.primary_score,
            y_ret=row.y_ret,
            target_date=row.target_date,
            domain=row.domain,
        )
        for row in rows
    ]


def evaluate_selective_horizon_agree(
    primary_artifacts: Sequence[PredictionArtifact],
    secondary_artifacts: Sequence[PredictionArtifact],
    *,
    contract: SuccessContract = DEFAULT_CONTRACT,
    grid: GateGrid = DEFAULT_GATE_GRID,
) -> dict[str, Any]:
    """Mine dense selective gates on horizon-agree rows (calibration only)."""
    if not primary_artifacts or not secondary_artifacts:
        raise ValueError("primary and secondary artifacts are required")
    model = primary_artifacts[0].spec.model
    if any(a.spec.model != model for a in primary_artifacts):
        raise ValueError("primary artifacts must share one model")
    if any(a.spec.model != model for a in secondary_artifacts):
        raise ValueError("secondary artifacts must match primary model")

    agree = align_horizon_agree_rows(primary_artifacts, secondary_artifacts)
    rows = _to_selective(agree)
    group_keys = sorted({row.outer_fold for row in rows})
    folds: list[dict[str, Any]] = []
    emitted_rows: list[SelectiveRow] = []
    total_test_rows = 0
    # Denominator: all primary test rows (pre-agreement), for honest coverage.
    primary_test = sum(
        1
        for artifact in primary_artifacts
        for row in artifact.predictions
        if row.partition == "test"
    )

    for outer_fold in group_keys:
        calibration = [
            row
            for row in rows
            if row.outer_fold == outer_fold and row.partition == "calibration"
        ]
        test = [
            row
            for row in rows
            if row.outer_fold == outer_fold and row.partition == "test"
        ]
        total_test_rows += len(test)
        gate = select_calibration_gate_dense(
            calibration,
            contract=contract,
            grid=grid,
        )
        fold_emits: list[SelectiveRow] = []
        if gate is not None:
            threshold = float(gate["threshold"])
            fold_emits = [
                row
                for row in test
                if row.y_dir != 0
                and math.isfinite(row.score)
                and abs(row.score) >= threshold
            ]
            emitted_rows.extend(fold_emits)
        hits = sum(1 for row in fold_emits if _is_hit(row))
        precision = hits / len(fold_emits) if fold_emits else None
        folds.append(
            {
                "outer_fold": outer_fold,
                "gate": gate,
                "emits": len(fold_emits),
                "hits": hits,
                "precision": precision,
                "agree_cal_rows": len(calibration),
                "agree_test_rows": len(test),
            }
        )

    checks, summary = _contract_checks(
        rows=emitted_rows,
        total_test_rows=max(primary_test, 1),
        folds=folds,
        contract=contract,
    )
    # Prefer primary-test denominator in summary for coverage honesty.
    summary["agree_test_rows"] = total_test_rows
    summary["primary_test_rows"] = primary_test
    summary["coverage_vs_primary"] = (
        summary["emits"] / primary_test if primary_test else 0.0
    )
    return {
        "model": model,
        "primary_horizon": primary_artifacts[0].spec.horizon,
        "secondary_horizon": secondary_artifacts[0].spec.horizon,
        "agree_rows": len(agree),
        "contract_met": all(checks.values()),
        "checks": checks,
        "summary": summary,
        "folds": folds,
        "gate_grid": asdict(grid),
        "symbol_top": Counter(row.symbol for row in emitted_rows).most_common(10),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-nested-dir", type=Path, required=True)
    parser.add_argument("--secondary-nested-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--coverage-grid",
        default=",".join(str(x) for x in DEFAULT_COVERAGE_GRID),
    )
    parser.add_argument(
        "--abs-score-grid",
        default=",".join(str(x) for x in DEFAULT_ABS_SCORE_GRID),
    )
    args = parser.parse_args(argv)
    grid = GateGrid(
        coverage_grid=_parse_float_csv(args.coverage_grid) or DEFAULT_COVERAGE_GRID,
        abs_score_grid=_parse_float_csv(args.abs_score_grid) or DEFAULT_ABS_SCORE_GRID,
    )
    primary = load_model_nested(args.primary_nested_dir, model=args.model)
    secondary = load_model_nested(args.secondary_nested_dir, model=args.model)
    report = evaluate_selective_horizon_agree(
        primary,
        secondary,
        contract=DEFAULT_CONTRACT,
        grid=grid,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"{args.model}.horizon_agree.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "model": report["model"],
                "contract_met": report["contract_met"],
                "precision": report["summary"].get("precision"),
                "precision_lcb": report["summary"].get("precision_lcb"),
                "emits": report["summary"].get("emits"),
                "path": str(out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
