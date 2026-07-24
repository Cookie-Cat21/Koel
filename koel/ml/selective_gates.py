"""Selective gate mining for one model's nested prediction artifacts.

This module searches only predeclared score gates on each fold's calibration
partition, then applies the selected gate to that same fold's test partition.
It is an offline research harness and never writes live policies.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from koel.ml.distributed import (
    ARTIFACT_SCHEMA_VERSION,
    PredictionArtifact,
    SuccessContract,
    load_prediction_artifact,
    wilson_lower_bound,
)

DEFAULT_COVERAGE_GRID: tuple[float, ...] = (
    0.0025,
    0.005,
    0.0075,
    0.01,
    0.0125,
    0.015,
    0.02,
    0.025,
    0.03,
    0.04,
    0.05,
    0.075,
    0.10,
    0.125,
    0.15,
)

DEFAULT_ABS_SCORE_GRID: tuple[float, ...] = (
    0.01,
    0.025,
    0.05,
    0.075,
    0.10,
    0.125,
    0.15,
    0.175,
    0.20,
    0.225,
    0.25,
    0.30,
    0.35,
    0.40,
    0.50,
    0.75,
    1.00,
)


@dataclass(frozen=True, slots=True)
class SelectiveRow:
    outer_fold: int
    partition: str
    symbol: str
    as_of: date
    horizon: int
    y_dir: int
    score: float
    y_ret: float | None
    target_date: date | None
    domain: str


@dataclass(frozen=True, slots=True)
class GateGrid:
    coverage_grid: tuple[float, ...] = DEFAULT_COVERAGE_GRID
    abs_score_grid: tuple[float, ...] = DEFAULT_ABS_SCORE_GRID


DEFAULT_GATE_GRID = GateGrid()
DEFAULT_CONTRACT = SuccessContract()


def _is_hit(row: SelectiveRow) -> bool:
    return (row.score > 0 and row.y_dir > 0) or (
        row.score < 0 and row.y_dir < 0
    )


def _parse_float_csv(raw: str) -> tuple[float, ...]:
    if raw.strip() == "":
        return ()
    values = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("grid values must be positive finite numbers")
    return tuple(sorted(set(values)))


def _rows_from_artifacts(artifacts: Sequence[PredictionArtifact]) -> list[SelectiveRow]:
    rows: list[SelectiveRow] = []
    for artifact in artifacts:
        for prediction in artifact.predictions:
            rows.append(
                SelectiveRow(
                    outer_fold=artifact.spec.outer_fold,
                    partition=prediction.partition,
                    symbol=prediction.symbol,
                    as_of=prediction.as_of,
                    horizon=prediction.horizon,
                    y_dir=prediction.y_dir,
                    score=prediction.score,
                    y_ret=prediction.y_ret,
                    target_date=prediction.target_date,
                    domain=prediction.domain,
                )
            )
    return rows


def load_model_artifacts(
    paths: Iterable[Path],
    *,
    model: str | None = None,
) -> list[PredictionArtifact]:
    """Load prediction artifacts and validate they represent one model."""
    loaded = [load_prediction_artifact(path) for path in sorted(set(paths))]
    if model is not None:
        loaded = [artifact for artifact in loaded if artifact.spec.model == model]
    if not loaded:
        raise ValueError("no prediction artifacts matched the requested model")

    models = {artifact.spec.model for artifact in loaded}
    if len(models) != 1:
        raise ValueError(f"expected artifacts for one model, got {sorted(models)}")
    run_ids = {artifact.run_id for artifact in loaded}
    snapshots = {artifact.snapshot_sha256 for artifact in loaded}
    targets = {artifact.spec.target for artifact in loaded}
    if len(run_ids) != 1:
        raise ValueError("prediction artifacts contain multiple run IDs")
    if len(snapshots) != 1:
        raise ValueError("prediction artifacts contain multiple dataset snapshots")
    if len(targets) != 1:
        raise ValueError("prediction artifacts contain multiple targets")

    shard_keys: set[tuple[int, int]] = set()
    for artifact in loaded:
        key = (artifact.spec.outer_fold, artifact.spec.horizon)
        if key in shard_keys:
            raise ValueError(f"duplicate shard for fold/horizon {key}")
        shard_keys.add(key)
    return sorted(loaded, key=lambda artifact: (artifact.spec.outer_fold, artifact.spec.horizon))


def _gate_metrics(
    rows: Sequence[SelectiveRow],
    *,
    threshold: float,
    confidence_level: float,
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row.score != 0 and math.isfinite(row.score) and abs(row.score) >= threshold
    ]
    hits = sum(1 for row in selected if _is_hit(row))
    precision = hits / len(selected) if selected else None
    return {
        "threshold": threshold,
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
    rows: Sequence[SelectiveRow],
    *,
    contract: SuccessContract,
    grid: GateGrid,
) -> list[dict[str, Any]]:
    usable = sorted(
        (row for row in rows if row.score != 0 and math.isfinite(row.score)),
        key=lambda row: abs(row.score),
        reverse=True,
    )
    if not usable:
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[float, float | None, str]] = set()
    floors: tuple[float | None, ...] = (None, *grid.abs_score_grid)

    for requested_coverage in sorted(set(grid.coverage_grid)):
        if not 0 < requested_coverage <= 1:
            raise ValueError("calibration coverage levels must be in (0, 1]")
        requested = math.ceil(len(usable) * requested_coverage)
        if requested > len(usable):
            continue
        coverage_threshold = abs(usable[requested - 1].score)
        for score_floor in floors:
            threshold = (
                coverage_threshold
                if score_floor is None
                else max(coverage_threshold, score_floor)
            )
            kind = "coverage" if score_floor is None else "coverage_abs_floor"
            key = (threshold, requested_coverage, kind)
            if key in seen:
                continue
            seen.add(key)
            metrics = _gate_metrics(
                usable,
                threshold=threshold,
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
        key = (score_floor, None, "abs_floor")
        if key in seen:
            continue
        seen.add(key)
        metrics = _gate_metrics(
            usable,
            threshold=score_floor,
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


def select_calibration_gate_dense(
    rows: Sequence[SelectiveRow],
    *,
    contract: SuccessContract,
    grid: GateGrid = DEFAULT_GATE_GRID,
) -> dict[str, Any] | None:
    """Select a predeclared gate using calibration labels only."""
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
            -float(candidate["threshold"]),
        ),
    )


def _contract_checks(
    *,
    rows: Sequence[SelectiveRow],
    total_test_rows: int,
    folds: Sequence[dict[str, Any]],
    contract: SuccessContract,
) -> tuple[dict[str, bool], dict[str, Any]]:
    hits = sum(1 for row in rows if _is_hit(row))
    emits = len(rows)
    precision = hits / emits if emits else None
    precision_lcb = wilson_lower_bound(
        hits,
        emits,
        confidence_level=contract.confidence_level,
    )
    coverage = emits / total_test_rows if total_test_rows else 0.0
    symbol_counts = Counter(row.symbol for row in rows)
    session_counts = Counter(row.as_of for row in rows)
    domain_counts = Counter(row.domain for row in rows)
    symbols = len(symbol_counts)
    emit_days = len(session_counts)
    max_symbol_share = max(symbol_counts.values(), default=0) / emits if emits else 0.0
    max_session_share = (
        max(session_counts.values(), default=0) / emits if emits else 0.0
    )
    stable_folds = sum(
        1
        for fold in folds
        if fold["precision"] is not None
        and int(fold["emits"]) >= contract.min_fold_emits
        and float(fold["precision"]) >= contract.min_fold_precision
    )
    fold_pass_fraction = stable_folds / len(folds) if folds else 0.0
    checks = {
        "point_precision": precision is not None
        and precision >= contract.target_precision,
        "precision_lcb": precision_lcb is not None
        and precision_lcb >= contract.min_precision_lcb,
        "emits": emits >= contract.min_emits,
        "symbols": symbols >= contract.min_symbols,
        "coverage": coverage >= contract.min_coverage,
        "fold_stability": fold_pass_fraction >= contract.min_fold_pass_fraction,
        "symbol_concentration": max_symbol_share <= contract.max_symbol_share,
        "emit_days": emit_days >= contract.min_emit_days,
        "session_concentration": max_session_share <= contract.max_session_share,
    }
    summary = {
        "test_rows": total_test_rows,
        "emits": emits,
        "hits": hits,
        "precision": precision,
        "precision_lcb": precision_lcb,
        "coverage": coverage,
        "symbols": symbols,
        "emit_days": emit_days,
        "max_symbol_share": max_symbol_share,
        "max_session_share": max_session_share,
        "domain_counts": dict(sorted(domain_counts.items())),
        "flat_outcomes": sum(1 for row in rows if row.y_dir == 0),
        "stable_folds": stable_folds,
        "folds": len(folds),
    }
    return checks, summary


def evaluate_selective_gates(
    artifacts: Sequence[PredictionArtifact],
    *,
    contract: SuccessContract = DEFAULT_CONTRACT,
    grid: GateGrid = DEFAULT_GATE_GRID,
) -> dict[str, Any]:
    """Evaluate dense selective gates for one model without test-label peeking."""
    if not artifacts:
        raise ValueError("at least one artifact is required")
    model = artifacts[0].spec.model
    if any(artifact.spec.model != model for artifact in artifacts):
        raise ValueError("evaluate_selective_gates accepts one model at a time")

    rows = _rows_from_artifacts(artifacts)
    group_keys = sorted({(row.outer_fold, row.horizon) for row in rows})
    folds: list[dict[str, Any]] = []
    emitted_rows: list[SelectiveRow] = []
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
        gate = select_calibration_gate_dense(
            calibration,
            contract=contract,
            grid=grid,
        )
        threshold = float(gate["threshold"]) if gate is not None else None
        emitted = (
            [
                row
                for row in test
                if row.score != 0
                and math.isfinite(row.score)
                and threshold is not None
                and abs(row.score) >= threshold
            ]
            if threshold is not None
            else []
        )
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
                "threshold": threshold,
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

    checks, summary = _contract_checks(
        rows=emitted_rows,
        total_test_rows=total_test_rows,
        folds=folds,
        contract=contract,
    )
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "kind": "selective_gate_evaluation",
        "model": model,
        "target": artifacts[0].spec.target,
        "run_id": artifacts[0].run_id,
        "snapshot_sha256": artifacts[0].snapshot_sha256,
        "contract_met": all(checks.values()),
        "checks": checks,
        "contract": asdict(contract),
        "grid": asdict(grid),
        "summary": summary,
        "folds": folds,
        "artifact_count": len(artifacts),
    }


def near_miss_key(report: dict[str, Any]) -> tuple[float, float, int, int, float]:
    """Rank failed offline reports by closeness to the precision contract."""
    summary = report["summary"]
    return (
        float(summary["precision_lcb"] or 0.0),
        float(summary["precision"] or 0.0),
        int(summary["emits"]),
        int(summary["symbols"]),
        float(summary["coverage"]),
    )


def render_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    checks = report["checks"]
    lines = [
        f"# Selective gates — {report['model']}",
        "",
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
            "| Fold | Threshold | Gate kind | Cal precision | Test emits | Test precision |",
            "|---:|---:|---|---:|---:|---:|",
        ]
    )
    for fold in report["folds"]:
        gate = fold["selected_gate"] or {}
        lines.append(
            f"| {fold['outer_fold']} | {fold['threshold']} | "
            f"{gate.get('kind')} | {gate.get('precision')} | "
            f"{fold['emits']} | {fold['precision']} |"
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


def _expand_artifact_args(values: Sequence[str]) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        path = Path(value)
        if path.is_dir():
            paths.extend(sorted(path.glob("*.predictions.jsonl.gz")))
        else:
            matches = sorted(glob.glob(value))
            paths.extend(Path(match) for match in matches)
    if not paths:
        raise ValueError("no artifact paths matched")
    return paths


def write_outputs(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{report['model']}.selective_gates"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_report(report), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", help="Prediction artifact files, globs, or dirs")
    parser.add_argument("--model", help="Model to select when artifact inputs include many models")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/cpu-selective-gates"),
    )
    parser.add_argument(
        "--coverage-grid",
        default=",".join(str(value) for value in DEFAULT_COVERAGE_GRID),
        help="Comma-separated predeclared calibration coverage grid",
    )
    parser.add_argument(
        "--abs-score-grid",
        default=",".join(str(value) for value in DEFAULT_ABS_SCORE_GRID),
        help="Comma-separated optional absolute |score| floor grid; empty disables",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    grid = GateGrid(
        coverage_grid=_parse_float_csv(args.coverage_grid),
        abs_score_grid=_parse_float_csv(args.abs_score_grid),
    )
    artifacts = load_model_artifacts(
        _expand_artifact_args(args.artifacts),
        model=args.model,
    )
    report = evaluate_selective_gates(
        artifacts,
        contract=SuccessContract(),
        grid=grid,
    )
    json_path, md_path = write_outputs(report, args.output_dir)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
