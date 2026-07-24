"""Calibration-only selective mining with multi-model disagreement gates.

Loads 2–3 nested prediction artifacts, aligns rows on
(outer_fold, partition, symbol, as_of), and searches predeclared score +
disagreement gates on calibration only before applying them to test.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from koel.ml.distributed import (
    ARTIFACT_SCHEMA_VERSION,
    PredictionArtifact,
    SuccessContract,
    ensemble_artifacts,
    load_prediction_artifact,
    wilson_lower_bound,
)
from koel.ml.selective_gates import (
    DEFAULT_ABS_SCORE_GRID,
    SelectiveRow,
    _contract_checks,
)

DEFAULT_COVERAGE_GRID: tuple[float, ...] = (0.005, 0.01, 0.02, 0.05, 0.10)
DEFAULT_MAX_DISAGREEMENT_GRID: tuple[float, ...] = (
    0.02,
    0.05,
    0.08,
    0.10,
    0.15,
    0.20,
    0.30,
)
DisagreementMode = Literal["stdev", "range"]


@dataclass(frozen=True, slots=True)
class DisagreementRow:
    outer_fold: int
    partition: str
    symbol: str
    as_of: date
    horizon: int
    y_dir: int
    primary_score: float
    disagreement: float
    y_ret: float | None
    target_date: date | None
    domain: str
    component_scores: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class DisagreementGateGrid:
    coverage_grid: tuple[float, ...] = DEFAULT_COVERAGE_GRID
    abs_score_grid: tuple[float, ...] = DEFAULT_ABS_SCORE_GRID
    max_disagreement_grid: tuple[float, ...] = DEFAULT_MAX_DISAGREEMENT_GRID


DEFAULT_GATE_GRID = DisagreementGateGrid()
DEFAULT_CONTRACT = SuccessContract()


def _parse_float_csv(raw: str) -> tuple[float, ...]:
    if raw.strip() == "":
        return ()
    values = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("grid values must be positive finite numbers")
    return tuple(sorted(set(values)))


def _parse_models_csv(raw: str) -> tuple[str, ...]:
    models = tuple(part.strip() for part in raw.split(",") if part.strip())
    if len(models) < 2:
        raise ValueError("at least two models are required")
    if len(models) != len(set(models)):
        raise ValueError("models must be unique")
    return models


def _is_hit(row: DisagreementRow) -> bool:
    return (row.primary_score > 0 and row.y_dir > 0) or (
        row.primary_score < 0 and row.y_dir < 0
    )


def _compute_disagreement(
    scores: Sequence[float],
    *,
    mode: DisagreementMode,
) -> float:
    if len(scores) < 2:
        return 0.0
    if mode == "range":
        return max(scores) - min(scores)
    return statistics.pstdev(scores)


def load_model_artifacts(
    nested_dir: Path,
    *,
    models: Sequence[str],
) -> list[PredictionArtifact]:
    """Load one artifact per fold/model from a nested shard directory."""
    if len(models) < 2:
        raise ValueError("at least two models are required")
    artifacts: list[PredictionArtifact] = []
    for model in models:
        paths = sorted(nested_dir.glob(f"*-{model}.predictions.jsonl.gz"))
        if not paths:
            raise FileNotFoundError(
                f"no prediction artifacts for {model} in {nested_dir}"
            )
        for path in paths:
            artifact = load_prediction_artifact(path)
            if artifact.spec.model != model:
                raise ValueError(
                    f"{path} contains model {artifact.spec.model}, not {model}"
                )
            artifacts.append(artifact)
    return artifacts


def align_disagreement_rows(
    artifacts: Sequence[PredictionArtifact],
    *,
    models: Sequence[str],
    primary_model: str | None = None,
    disagreement_mode: DisagreementMode = "stdev",
) -> list[DisagreementRow]:
    """Align model shards and attach primary score plus cross-model disagreement."""
    model_tuple = tuple(models)
    if len(model_tuple) < 2:
        raise ValueError("at least two models are required")
    primary = primary_model or model_tuple[0]
    if primary not in model_tuple:
        raise ValueError(f"primary model {primary!r} is not in {model_tuple}")

    aligned = ensemble_artifacts(list(artifacts), expected_models=model_tuple)
    rows: list[DisagreementRow] = []
    for row in aligned:
        component = dict(row.component_scores)
        scores = [component[model] for model in model_tuple]
        rows.append(
            DisagreementRow(
                outer_fold=row.outer_fold,
                partition=row.partition,
                symbol=row.symbol,
                as_of=row.as_of,
                horizon=row.horizon,
                y_dir=row.y_dir,
                primary_score=component[primary],
                disagreement=_compute_disagreement(scores, mode=disagreement_mode),
                y_ret=row.y_ret,
                target_date=row.target_date,
                domain=row.domain,
                component_scores=row.component_scores,
            )
        )
    return rows


def _gate_metrics(
    rows: Sequence[DisagreementRow],
    *,
    score_threshold: float,
    max_disagreement: float,
    confidence_level: float,
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row.primary_score != 0
        and math.isfinite(row.primary_score)
        and math.isfinite(row.disagreement)
        and abs(row.primary_score) >= score_threshold
        and row.disagreement <= max_disagreement
    ]
    hits = sum(1 for row in selected if _is_hit(row))
    precision = hits / len(selected) if selected else None
    return {
        "score_threshold": score_threshold,
        "max_disagreement": max_disagreement,
        "emits": len(selected),
        "hits": hits,
        "precision": precision,
        "precision_lcb": wilson_lower_bound(
            hits,
            len(selected),
            confidence_level=confidence_level,
        ),
        "coverage": len(selected) / len(rows) if rows else 0.0,
    }


def _candidate_gates(
    rows: Sequence[DisagreementRow],
    *,
    contract: SuccessContract,
    grid: DisagreementGateGrid,
) -> list[dict[str, Any]]:
    usable = sorted(
        (
            row
            for row in rows
            if row.primary_score != 0
            and math.isfinite(row.primary_score)
            and math.isfinite(row.disagreement)
        ),
        key=lambda row: abs(row.primary_score),
        reverse=True,
    )
    if not usable:
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[float, float, float | None, str]] = set()
    floors: tuple[float | None, ...] = (None, *grid.abs_score_grid)

    for requested_coverage in sorted(set(grid.coverage_grid)):
        if not 0 < requested_coverage <= 1:
            raise ValueError("calibration coverage levels must be in (0, 1]")
        requested = math.ceil(len(usable) * requested_coverage)
        if requested > len(usable):
            continue
        coverage_threshold = abs(usable[requested - 1].primary_score)
        for score_floor in floors:
            score_threshold = (
                coverage_threshold
                if score_floor is None
                else max(coverage_threshold, score_floor)
            )
            kind = "coverage" if score_floor is None else "coverage_abs_floor"
            for max_disagreement in sorted(set(grid.max_disagreement_grid)):
                key = (score_threshold, max_disagreement, requested_coverage, kind)
                if key in seen:
                    continue
                seen.add(key)
                metrics = _gate_metrics(
                    usable,
                    score_threshold=score_threshold,
                    max_disagreement=max_disagreement,
                    confidence_level=contract.confidence_level,
                )
                metrics.update(
                    {
                        "kind": kind,
                        "requested_coverage": requested_coverage,
                        "requested_rows": requested,
                        "score_floor": score_floor,
                    }
                )
                candidates.append(metrics)

    for score_floor in sorted(set(grid.abs_score_grid)):
        for max_disagreement in sorted(set(grid.max_disagreement_grid)):
            key = (score_floor, max_disagreement, None, "abs_floor")
            if key in seen:
                continue
            seen.add(key)
            metrics = _gate_metrics(
                usable,
                score_threshold=score_floor,
                max_disagreement=max_disagreement,
                confidence_level=contract.confidence_level,
            )
            metrics.update(
                {
                    "kind": "abs_floor",
                    "requested_coverage": None,
                    "requested_rows": None,
                    "score_floor": score_floor,
                }
            )
            candidates.append(metrics)

    return candidates


def select_calibration_gate_disagreement(
    rows: Sequence[DisagreementRow],
    *,
    contract: SuccessContract,
    grid: DisagreementGateGrid = DEFAULT_GATE_GRID,
) -> dict[str, Any] | None:
    """Select a predeclared score + disagreement gate using calibration only."""
    viable: list[dict[str, Any]] = []
    for candidate in _candidate_gates(rows, contract=contract, grid=grid):
        precision = candidate["precision"]
        precision_lcb = candidate["precision_lcb"]
        if int(candidate["emits"]) < contract.min_calibration_emits:
            continue
        if precision is None or precision < contract.target_precision:
            continue
        if precision_lcb is None or precision_lcb < contract.min_calibration_lcb:
            continue
        viable.append(candidate)

    if not viable:
        return None
    return max(
        viable,
        key=lambda candidate: (
            int(candidate["emits"]),
            float(candidate["precision_lcb"]),
            float(candidate["precision"]),
            -float(candidate["score_threshold"]),
            -float(candidate["max_disagreement"]),
        ),
    )


def _apply_gate(
    rows: Sequence[DisagreementRow],
    gate: dict[str, Any] | None,
) -> list[DisagreementRow]:
    if gate is None:
        return []
    score_threshold = float(gate["score_threshold"])
    max_disagreement = float(gate["max_disagreement"])
    return [
        row
        for row in rows
        if row.primary_score != 0
        and math.isfinite(row.primary_score)
        and math.isfinite(row.disagreement)
        and abs(row.primary_score) >= score_threshold
        and row.disagreement <= max_disagreement
    ]


def evaluate_selective_disagreement(
    artifacts: Sequence[PredictionArtifact],
    *,
    models: Sequence[str],
    primary_model: str | None = None,
    disagreement_mode: DisagreementMode = "stdev",
    contract: SuccessContract = DEFAULT_CONTRACT,
    grid: DisagreementGateGrid = DEFAULT_GATE_GRID,
) -> dict[str, Any]:
    """Evaluate disagreement gates without reading test labels during selection."""
    if len(models) < 2:
        raise ValueError("at least two models are required")

    model_tuple = tuple(models)
    primary = primary_model or model_tuple[0]
    rows = align_disagreement_rows(
        artifacts,
        models=model_tuple,
        primary_model=primary,
        disagreement_mode=disagreement_mode,
    )
    group_keys = sorted({(row.outer_fold, row.horizon) for row in rows})
    folds: list[dict[str, Any]] = []
    emitted_rows: list[DisagreementRow] = []
    total_test_rows = 0

    for outer_fold, horizon in group_keys:
        calibration = [
            row
            for row in rows
            if row.outer_fold == outer_fold
            and row.horizon == horizon
            and row.partition == "calibration"
        ]
        test = [
            row
            for row in rows
            if row.outer_fold == outer_fold
            and row.horizon == horizon
            and row.partition == "test"
        ]
        total_test_rows += len(test)
        gate = select_calibration_gate_disagreement(
            calibration,
            contract=contract,
            grid=grid,
        )
        emitted = _apply_gate(test, gate)
        emitted_rows.extend(emitted)
        hits = sum(1 for row in emitted if _is_hit(row))
        precision = hits / len(emitted) if emitted else None
        folds.append(
            {
                "outer_fold": outer_fold,
                "horizon": horizon,
                "calibration_rows": len(calibration),
                "test_rows": len(test),
                "selected_gate": gate,
                "score_threshold": (
                    float(gate["score_threshold"]) if gate is not None else None
                ),
                "max_disagreement": (
                    float(gate["max_disagreement"]) if gate is not None else None
                ),
                "emits": len(emitted),
                "hits": hits,
                "precision": precision,
                "precision_lcb": wilson_lower_bound(
                    hits,
                    len(emitted),
                    confidence_level=contract.confidence_level,
                ),
                "coverage": len(emitted) / len(test) if test else 0.0,
            }
        )

    selective_rows = [
        SelectiveRow(
            outer_fold=row.outer_fold,
            partition=row.partition,
            symbol=row.symbol,
            as_of=row.as_of,
            horizon=row.horizon,
            y_dir=row.y_dir,
            score=row.primary_score,
            y_ret=row.y_ret,
            target_date=row.target_date,
            domain=row.domain,
        )
        for row in emitted_rows
    ]
    checks, summary = _contract_checks(
        rows=selective_rows,
        total_test_rows=total_test_rows,
        folds=folds,
        contract=contract,
    )
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "kind": "selective_disagreement_evaluation",
        "models": list(model_tuple),
        "primary_model": primary,
        "disagreement_mode": disagreement_mode,
        "target": artifacts[0].spec.target if artifacts else "relative",
        "run_id": artifacts[0].run_id if artifacts else "",
        "snapshot_sha256": artifacts[0].snapshot_sha256 if artifacts else "",
        "contract_met": all(checks.values()),
        "checks": checks,
        "contract": asdict(contract),
        "grid": asdict(grid),
        "summary": summary,
        "folds": folds,
        "artifact_count": len(artifacts),
    }


def render_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    checks = report["checks"]
    lines = [
        f"# Selective disagreement — {report['primary_model']} + "
        f"{len(report['models'])} models",
        "",
        f"- models: `{', '.join(report['models'])}`",
        f"- primary: `{report['primary_model']}`",
        f"- disagreement: `{report['disagreement_mode']}`",
        f"- target: `{report['target']}`",
        f"- run_id: `{report['run_id']}`",
        f"- snapshot: `{str(report['snapshot_sha256'])[:16]}...`",
        f"- contract_met: `{report['contract_met']}`",
        "",
        "## Aggregate test-only result",
        "",
        "| Precision | LCB | Emits | Symbols | Coverage | Max symbol | Max session |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {summary['precision']} | {summary['precision_lcb']} | "
            f"{summary['emits']} | {summary['symbols']} | {summary['coverage']} | "
            f"{summary['max_symbol_share']} | {summary['max_session_share']} |"
        ),
        "",
        "## Contract checks",
        "",
    ]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} `{name}`" for name, passed in checks.items())
    lines.extend(
        [
            "",
            "## Fold gates",
            "",
            "| Fold | Score thr | Max disagree | Gate kind | Cal emits | Test emits | Test precision |",
            "|---:|---:|---:|---|---:|---:|---:|",
        ]
    )
    for fold in report["folds"]:
        gate = fold["selected_gate"] or {}
        lines.append(
            f"| {fold['outer_fold']} | {fold['score_threshold']} | "
            f"{fold['max_disagreement']} | {gate.get('kind')} | "
            f"{gate.get('emits')} | {fold['emits']} | {fold['precision']} |"
        )
    lines.extend(
        [
            "",
            "Calibration gates were selected per fold before test labels were read. "
            "Research only — not financial advice.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = (
        f"{report['primary_model']}.selective_disagreement."
        f"{report['disagreement_mode']}"
    )
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_report(report), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--nested-dir",
        type=Path,
        required=True,
        help="Directory containing nested *.predictions.jsonl.gz shards",
    )
    parser.add_argument(
        "--models",
        required=True,
        help="Comma-separated model list (2–3 models; first is primary unless overridden)",
    )
    parser.add_argument(
        "--primary-model",
        help="Primary score model (defaults to first entry in --models)",
    )
    parser.add_argument(
        "--disagreement-mode",
        choices=("stdev", "range"),
        default="stdev",
        help="Cross-model disagreement metric",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/cpu-selective-disagree"),
    )
    parser.add_argument(
        "--coverage-grid",
        default=",".join(str(value) for value in DEFAULT_COVERAGE_GRID),
        help="Comma-separated predeclared calibration coverage grid",
    )
    parser.add_argument(
        "--abs-score-grid",
        default=",".join(str(value) for value in DEFAULT_ABS_SCORE_GRID),
        help="Comma-separated optional absolute |primary score| floor grid; empty disables",
    )
    parser.add_argument(
        "--max-disagreement-grid",
        default=",".join(str(value) for value in DEFAULT_MAX_DISAGREEMENT_GRID),
        help="Comma-separated maximum allowed disagreement grid",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    models = _parse_models_csv(args.models)
    grid = DisagreementGateGrid(
        coverage_grid=_parse_float_csv(args.coverage_grid),
        abs_score_grid=_parse_float_csv(args.abs_score_grid),
        max_disagreement_grid=_parse_float_csv(args.max_disagreement_grid),
    )
    artifacts = load_model_artifacts(args.nested_dir, models=models)
    report = evaluate_selective_disagreement(
        artifacts,
        models=models,
        primary_model=args.primary_model,
        disagreement_mode=args.disagreement_mode,
        contract=SuccessContract(),
        grid=grid,
    )
    json_path, md_path = write_outputs(report, args.output_dir)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "contract_met": report["contract_met"],
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
