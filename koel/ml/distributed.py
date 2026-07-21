"""Fan-out specifications and leakage-safe fan-in evaluation for ML jobs."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable

ARTIFACT_SCHEMA_VERSION = 1
ALLOWED_MODELS = ("logistic", "hgb_lmt", "xgb_lmt")
PARTITIONS = ("calibration", "test")


@dataclass(frozen=True, slots=True)
class SuccessContract:
    target_precision: float = 0.90
    min_precision_lcb: float = 0.90
    confidence_level: float = 0.95
    min_emits: int = 500
    min_symbols: int = 80
    min_coverage: float = 0.01
    min_fold_precision: float = 0.85
    min_fold_pass_fraction: float = 2 / 3
    max_symbol_share: float = 0.05
    min_calibration_emits: int = 50


@dataclass(frozen=True, slots=True)
class ShardSpec:
    shard_id: str
    model: str
    outer_fold: int
    horizon: int
    seeds: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Prediction:
    partition: str
    symbol: str
    as_of: date
    horizon: int
    y_dir: int
    score: float


@dataclass(frozen=True, slots=True)
class PredictionArtifact:
    run_id: str
    snapshot_sha256: str
    spec: ShardSpec
    predictions: tuple[Prediction, ...]


@dataclass(frozen=True, slots=True)
class EnsemblePrediction:
    outer_fold: int
    partition: str
    symbol: str
    as_of: date
    horizon: int
    y_dir: int
    score: float
    disagreement: float


def _parse_csv_ints(raw: str) -> tuple[int, ...]:
    values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("at least one integer is required")
    return values


def _parse_csv_strings(raw: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("at least one value is required")
    return values


def build_training_matrix(
    *,
    models: tuple[str, ...] = ALLOWED_MODELS,
    outer_folds: int = 6,
    horizons: tuple[int, ...] = (1,),
    seeds: tuple[int, ...] = (0, 1, 2),
) -> list[ShardSpec]:
    """Return a stable fold × model matrix; seeds stay inside each worker."""
    if outer_folds < 2:
        raise ValueError("outer_folds must be at least 2")
    unknown = sorted(set(models) - set(ALLOWED_MODELS))
    if unknown:
        raise ValueError(f"unsupported models: {', '.join(unknown)}")
    if not models or not seeds:
        raise ValueError("models and seeds must not be empty")
    if any(horizon < 1 or horizon > 30 for horizon in horizons):
        raise ValueError("horizons must be between 1 and 30")

    specs: list[ShardSpec] = []
    for horizon in sorted(set(horizons)):
        for outer_fold in range(outer_folds):
            for model in models:
                specs.append(
                    ShardSpec(
                        shard_id=f"h{horizon}-f{outer_fold:02d}-{model}",
                        model=model,
                        outer_fold=outer_fold,
                        horizon=horizon,
                        seeds=seeds,
                    )
                )
    return specs


def _prediction_payload(prediction: Prediction) -> dict[str, Any]:
    return {
        "kind": "prediction",
        "partition": prediction.partition,
        "symbol": prediction.symbol,
        "as_of": prediction.as_of.isoformat(),
        "horizon": prediction.horizon,
        "y_dir": prediction.y_dir,
        "score": prediction.score,
    }


def write_prediction_artifact(
    path: Path,
    *,
    run_id: str,
    snapshot_sha256: str,
    spec: ShardSpec,
    predictions: Iterable[Prediction],
) -> None:
    """Write one deterministic, checksummed-by-Actions prediction artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "kind": "metadata",
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": run_id,
        "snapshot_sha256": snapshot_sha256,
        "spec": asdict(spec),
    }
    with (
        path.open("wb") as raw_handle,
        gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0) as compressed,
    ):
        compressed.write(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
            + b"\n"
        )
        for prediction in predictions:
            if prediction.partition not in PARTITIONS:
                raise ValueError(f"unsupported partition {prediction.partition!r}")
            if prediction.y_dir not in (-1, 1):
                raise ValueError("y_dir must be -1 or 1")
            if not math.isfinite(prediction.score):
                raise ValueError("prediction score must be finite")
            compressed.write(
                json.dumps(
                    _prediction_payload(prediction),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )


def load_prediction_artifact(path: Path) -> PredictionArtifact:
    """Read and validate one worker artifact."""
    with gzip.open(path, mode="rt", encoding="utf-8") as handle:
        try:
            metadata = json.loads(next(handle))
        except StopIteration as exc:
            raise ValueError(f"empty prediction artifact: {path}") from exc
        if metadata.get("kind") != "metadata":
            raise ValueError(f"missing metadata line: {path}")
        if int(metadata.get("schema_version", -1)) != ARTIFACT_SCHEMA_VERSION:
            raise ValueError(f"unsupported artifact schema: {path}")
        raw_spec = dict(metadata["spec"])
        spec = ShardSpec(
            shard_id=str(raw_spec["shard_id"]),
            model=str(raw_spec["model"]),
            outer_fold=int(raw_spec["outer_fold"]),
            horizon=int(raw_spec["horizon"]),
            seeds=tuple(int(seed) for seed in raw_spec["seeds"]),
        )
        predictions: list[Prediction] = []
        seen: set[tuple[str, str, date, int]] = set()
        for line_number, line in enumerate(handle, start=2):
            raw = json.loads(line)
            if raw.get("kind") != "prediction":
                raise ValueError(f"invalid row kind at {path}:{line_number}")
            prediction = Prediction(
                partition=str(raw["partition"]),
                symbol=str(raw["symbol"]).strip().upper(),
                as_of=date.fromisoformat(str(raw["as_of"])),
                horizon=int(raw["horizon"]),
                y_dir=int(raw["y_dir"]),
                score=float(raw["score"]),
            )
            if prediction.partition not in PARTITIONS:
                raise ValueError(f"invalid partition at {path}:{line_number}")
            if prediction.y_dir not in (-1, 1) or not math.isfinite(prediction.score):
                raise ValueError(f"invalid prediction at {path}:{line_number}")
            key = (
                prediction.partition,
                prediction.symbol,
                prediction.as_of,
                prediction.horizon,
            )
            if key in seen:
                raise ValueError(f"duplicate prediction at {path}:{line_number}")
            seen.add(key)
            predictions.append(prediction)
    return PredictionArtifact(
        run_id=str(metadata["run_id"]),
        snapshot_sha256=str(metadata["snapshot_sha256"]),
        spec=spec,
        predictions=tuple(predictions),
    )


def ensemble_artifacts(
    artifacts: list[PredictionArtifact],
    *,
    expected_models: tuple[str, ...],
) -> list[EnsemblePrediction]:
    """Align model shards and average scores without touching gate labels."""
    if not artifacts:
        raise ValueError("no prediction artifacts supplied")
    if len(set(expected_models)) != len(expected_models):
        raise ValueError("expected_models contains duplicates")
    run_ids = {artifact.run_id for artifact in artifacts}
    snapshots = {artifact.snapshot_sha256 for artifact in artifacts}
    if len(run_ids) != 1:
        raise ValueError("prediction artifacts contain multiple run IDs")
    if len(snapshots) != 1:
        raise ValueError("prediction artifacts contain multiple dataset snapshots")

    shard_keys: set[tuple[int, int, str]] = set()
    scores: dict[
        tuple[int, str, str, date, int], dict[str, tuple[int, float]]
    ] = defaultdict(dict)
    for artifact in artifacts:
        spec = artifact.spec
        shard_key = (spec.outer_fold, spec.horizon, spec.model)
        if shard_key in shard_keys:
            raise ValueError(f"duplicate shard for fold/horizon/model {shard_key}")
        shard_keys.add(shard_key)
        if spec.model not in expected_models:
            raise ValueError(f"unexpected model artifact {spec.model}")
        for prediction in artifact.predictions:
            if prediction.horizon != spec.horizon:
                raise ValueError(
                    f"artifact {spec.shard_id} contains a mismatched horizon"
                )
            key = (
                spec.outer_fold,
                prediction.partition,
                prediction.symbol,
                prediction.as_of,
                prediction.horizon,
            )
            if spec.model in scores[key]:
                raise ValueError(f"duplicate model prediction for {key}")
            scores[key][spec.model] = (prediction.y_dir, prediction.score)

    expected = set(expected_models)
    out: list[EnsemblePrediction] = []
    for key, by_model in sorted(scores.items()):
        if set(by_model) != expected:
            missing = sorted(expected - set(by_model))
            raise ValueError(f"incomplete ensemble row {key}; missing {missing}")
        directions = {item[0] for item in by_model.values()}
        if len(directions) != 1:
            raise ValueError(f"models disagree on ground truth for {key}")
        model_scores = [by_model[model][1] for model in expected_models]
        outer_fold, partition, symbol, as_of, horizon = key
        out.append(
            EnsemblePrediction(
                outer_fold=outer_fold,
                partition=partition,
                symbol=symbol,
                as_of=as_of,
                horizon=horizon,
                y_dir=directions.pop(),
                score=statistics.fmean(model_scores),
                disagreement=(
                    statistics.pstdev(model_scores) if len(model_scores) > 1 else 0.0
                ),
            )
        )
    return out


def _is_hit(row: EnsemblePrediction) -> bool:
    return (row.score > 0 and row.y_dir > 0) or (
        row.score < 0 and row.y_dir < 0
    )


def select_calibration_threshold(
    rows: list[EnsemblePrediction],
    *,
    target_precision: float,
    min_emits: int,
) -> float | None:
    """Choose maximum calibration coverage at the target precision."""
    usable = sorted(
        (row for row in rows if row.score != 0 and math.isfinite(row.score)),
        key=lambda row: abs(row.score),
        reverse=True,
    )
    if not usable:
        return None
    hits = 0
    count = 0
    best: float | None = None
    index = 0
    while index < len(usable):
        magnitude = abs(usable[index].score)
        group: list[EnsemblePrediction] = []
        while index < len(usable) and abs(usable[index].score) == magnitude:
            group.append(usable[index])
            index += 1
        count += len(group)
        hits += sum(1 for row in group if _is_hit(row))
        if count >= min_emits and hits / count >= target_precision:
            best = magnitude
    return best


def wilson_lower_bound(
    hits: int,
    total: int,
    *,
    confidence_level: float = 0.95,
) -> float | None:
    """One-sided Wilson score lower bound for a binomial proportion."""
    if total <= 0:
        return None
    if not 0.5 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0.5 and 1")
    z = NormalDist().inv_cdf(confidence_level)
    proportion = hits / total
    z2 = z * z
    denominator = 1 + z2 / total
    centre = proportion + z2 / (2 * total)
    margin = z * math.sqrt(
        (proportion * (1 - proportion) + z2 / (4 * total)) / total
    )
    return max(0.0, (centre - margin) / denominator)


def evaluate_nested_ensemble(
    rows: list[EnsemblePrediction],
    *,
    contract: SuccessContract,
) -> dict[str, Any]:
    """Calibrate gates per outer fold, then score only corresponding tests."""
    group_keys = sorted({(row.outer_fold, row.horizon) for row in rows})
    folds: list[dict[str, Any]] = []
    emitted_rows: list[EnsemblePrediction] = []
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
        threshold = select_calibration_threshold(
            calibration,
            target_precision=contract.target_precision,
            min_emits=contract.min_calibration_emits,
        )
        emitted = (
            [row for row in test if abs(row.score) >= threshold and row.score != 0]
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
                "threshold": threshold,
                "emits": len(emitted),
                "hits": hits,
                "precision": precision,
                "coverage": len(emitted) / len(test) if test else 0.0,
            }
        )

    hits = sum(1 for row in emitted_rows if _is_hit(row))
    emits = len(emitted_rows)
    precision = hits / emits if emits else None
    coverage = emits / total_test_rows if total_test_rows else 0.0
    symbol_counts = Counter(row.symbol for row in emitted_rows)
    symbols = len(symbol_counts)
    max_symbol_share = max(symbol_counts.values(), default=0) / emits if emits else 0.0
    precision_lcb = wilson_lower_bound(
        hits,
        emits,
        confidence_level=contract.confidence_level,
    )
    stable_folds = sum(
        1
        for fold in folds
        if fold["precision"] is not None
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
    }
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "contract_met": all(checks.values()),
        "checks": checks,
        "contract": asdict(contract),
        "summary": {
            "test_rows": total_test_rows,
            "emits": emits,
            "hits": hits,
            "precision": precision,
            "precision_lcb": precision_lcb,
            "coverage": coverage,
            "symbols": symbols,
            "max_symbol_share": max_symbol_share,
            "stable_folds": stable_folds,
            "folds": len(folds),
        },
        "folds": folds,
    }


def render_report(report: dict[str, Any]) -> str:
    summary = dict(report["summary"])
    checks = dict(report["checks"])
    lines = [
        "# Distributed ML nested evaluation",
        "",
        f"**Contract met:** **{report['contract_met']}**",
        "",
        "## Aggregate test-only result",
        "",
        "| Precision | 95% one-sided LCB | Emits | Coverage | Symbols |",
        "|---:|---:|---:|---:|---:|",
        (
            f"| {summary['precision']} | {summary['precision_lcb']} | "
            f"{summary['emits']} | {summary['coverage']} | {summary['symbols']} |"
        ),
        "",
        "## Contract checks",
        "",
    ]
    lines.extend(
        f"- {'PASS' if passed else 'FAIL'} `{name}`"
        for name, passed in checks.items()
    )
    lines.extend(
        [
            "",
            "Calibration thresholds were selected only on each outer fold's "
            "calibration partition; aggregate metrics use test partitions only.",
            "",
            "Research only — not financial advice.",
            "",
        ]
    )
    return "\n".join(lines)


def _matrix_payload(specs: list[ShardSpec]) -> dict[str, list[dict[str, Any]]]:
    return {
        "include": [
            {
                "shard_id": spec.shard_id,
                "model": spec.model,
                "outer_fold": spec.outer_fold,
                "horizon": spec.horizon,
                "seeds": ",".join(str(seed) for seed in spec.seeds),
            }
            for spec in specs
        ]
    }


def _aggregate_command(args: argparse.Namespace) -> None:
    paths = sorted(args.input_dir.rglob("*.predictions.jsonl.gz"))
    artifacts = [load_prediction_artifact(path) for path in paths]
    expected_models = _parse_csv_strings(args.models)
    rows = ensemble_artifacts(artifacts, expected_models=expected_models)
    contract = SuccessContract(
        target_precision=args.target_precision,
        min_precision_lcb=args.min_precision_lcb,
        min_emits=args.min_emits,
        min_symbols=args.min_symbols,
        min_coverage=args.min_coverage,
    )
    report = evaluate_nested_ensemble(rows, contract=contract)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_markdown.write_text(render_report(report), encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Distributed ML job orchestration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    matrix = subparsers.add_parser("matrix")
    matrix.add_argument("--models", default=",".join(ALLOWED_MODELS))
    matrix.add_argument("--folds", type=int, default=6)
    matrix.add_argument("--horizons", default="1")
    matrix.add_argument("--seeds", default="0,1,2")
    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("--input-dir", type=Path, required=True)
    aggregate.add_argument("--models", default=",".join(ALLOWED_MODELS))
    aggregate.add_argument("--output-json", type=Path, required=True)
    aggregate.add_argument("--output-markdown", type=Path, required=True)
    aggregate.add_argument("--target-precision", type=float, default=0.90)
    aggregate.add_argument("--min-precision-lcb", type=float, default=0.90)
    aggregate.add_argument("--min-emits", type=int, default=500)
    aggregate.add_argument("--min-symbols", type=int, default=80)
    aggregate.add_argument("--min-coverage", type=float, default=0.01)
    args = parser.parse_args(argv)

    if args.command == "matrix":
        specs = build_training_matrix(
            models=_parse_csv_strings(args.models),
            outer_folds=args.folds,
            horizons=_parse_csv_ints(args.horizons),
            seeds=_parse_csv_ints(args.seeds),
        )
        print(json.dumps(_matrix_payload(specs), separators=(",", ":")))
        return
    _aggregate_command(args)


if __name__ == "__main__":
    main()
