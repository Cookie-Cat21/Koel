"""Fan-out specifications and leakage-safe fan-in evaluation for ML jobs."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import date
from itertools import combinations
from pathlib import Path
from statistics import NormalDist
from typing import Any

from koel.ml.metrics import (
    balanced_direction_accuracy,
    cost_adjusted_top_bottom_spread,
    matthews_direction_correlation,
    mean_daily_rank_ic,
)

ARTIFACT_SCHEMA_VERSION = 2
ALLOWED_MODELS = (
    "logistic",
    "ridge_return",
    "hgb_lmt",
    "hgb_deep",
    "hgb_bagged",
    "hgb_weighted",
    "hgb_domain",
    "hgb_two_stage",
    "hgb_regressor",
    "xgb_lmt",
    "xgb_domain",
    "xgb_two_stage",
    "xgb_regressor",
    "xgb_rank_pairwise",
    "xgb_rank_ndcg",
    "lgb_lmt",
    "lgb_domain",
    "lgb_lambdarank",
    "qlib_lgb_native",
    "double_ensemble_native",
    "blend_de_lgb",
    "blend_de_ridge",
    "qlib_lgb_exact",
    "qlib_double_ensemble_exact",
    "qlib_tra",
    "master",
    "kronos_features",
)
PARTITIONS = ("calibration", "test")
TARGETS = ("absolute", "relative")


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
    min_calibration_lcb: float = 0.80
    calibration_coverages: tuple[float, ...] = (0.005, 0.01, 0.02, 0.05, 0.10)
    min_emit_days: int = 60
    max_session_share: float = 0.05
    min_fold_emits: int = 30


@dataclass(frozen=True, slots=True)
class ShardSpec:
    shard_id: str
    model: str
    outer_fold: int
    horizon: int
    seeds: tuple[int, ...]
    target: str = "absolute"


@dataclass(frozen=True, slots=True)
class Prediction:
    partition: str
    symbol: str
    as_of: date
    horizon: int
    y_dir: int
    score: float
    y_ret: float | None = None
    target_date: date | None = None
    domain: str = "unknown"


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
    y_ret: float | None = None
    target_date: date | None = None
    domain: str = "unknown"
    component_scores: tuple[tuple[str, float], ...] = ()


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
    target: str = "absolute",
) -> list[ShardSpec]:
    """Return a stable fold × model matrix; seeds stay inside each worker."""
    if outer_folds < 2:
        raise ValueError("outer_folds must be at least 2")
    unknown = sorted(set(models) - set(ALLOWED_MODELS))
    if unknown:
        raise ValueError(f"unsupported models: {', '.join(unknown)}")
    if not models or not seeds:
        raise ValueError("models and seeds must not be empty")
    if target not in TARGETS:
        raise ValueError(f"target must be one of {', '.join(TARGETS)}")
    if any(horizon < 1 or horizon > 30 for horizon in horizons):
        raise ValueError("horizons must be between 1 and 30")

    specs: list[ShardSpec] = []
    for horizon in sorted(set(horizons)):
        for outer_fold in range(outer_folds):
            for model in models:
                specs.append(
                    ShardSpec(
                        shard_id=(
                            f"{target[:3]}-h{horizon}-f{outer_fold:02d}-{model}"
                        ),
                        model=model,
                        outer_fold=outer_fold,
                        horizon=horizon,
                        seeds=seeds,
                        target=target,
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
        "y_ret": prediction.y_ret,
        "target_date": (
            prediction.target_date.isoformat() if prediction.target_date else None
        ),
        "domain": prediction.domain,
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
            if prediction.y_dir not in (-1, 0, 1):
                raise ValueError("y_dir must be -1, 0, or 1")
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
            target=str(raw_spec.get("target") or "relative"),
        )
        predictions: list[Prediction] = []
        seen: set[tuple[str, str, date, int, date | None]] = set()
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
                y_ret=(
                    float(raw["y_ret"]) if raw.get("y_ret") is not None else None
                ),
                target_date=(
                    date.fromisoformat(str(raw["target_date"]))
                    if raw.get("target_date")
                    else None
                ),
                domain=str(raw.get("domain") or "unknown"),
            )
            if prediction.partition not in PARTITIONS:
                raise ValueError(f"invalid partition at {path}:{line_number}")
            if prediction.y_dir not in (-1, 0, 1) or not math.isfinite(
                prediction.score
            ):
                raise ValueError(f"invalid prediction at {path}:{line_number}")
            key = (
                prediction.partition,
                prediction.symbol,
                prediction.as_of,
                prediction.horizon,
                prediction.target_date,
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
    targets = {artifact.spec.target for artifact in artifacts}
    if len(targets) != 1:
        raise ValueError("prediction artifacts contain multiple targets")

    shard_keys: set[tuple[str, int, int, str]] = set()
    scores: dict[
        tuple[int, str, str, date, int, date | None],
        dict[str, tuple[int, float, str, float | None]],
    ] = defaultdict(dict)
    for artifact in artifacts:
        spec = artifact.spec
        shard_key = (spec.target, spec.outer_fold, spec.horizon, spec.model)
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
                prediction.target_date,
            )
            if spec.model in scores[key]:
                raise ValueError(f"duplicate model prediction for {key}")
            scores[key][spec.model] = (
                prediction.y_dir,
                prediction.score,
                prediction.domain,
                prediction.y_ret,
            )

    expected = set(expected_models)
    out: list[EnsemblePrediction] = []
    for key, by_model in sorted(scores.items()):
        if set(by_model) != expected:
            missing = sorted(expected - set(by_model))
            raise ValueError(f"incomplete ensemble row {key}; missing {missing}")
        directions = {item[0] for item in by_model.values()}
        if len(directions) != 1:
            raise ValueError(f"models disagree on ground truth for {key}")
        domains = {item[2] for item in by_model.values()}
        if len(domains) != 1:
            raise ValueError(f"models disagree on domain for {key}")
        returns = {item[3] for item in by_model.values()}
        if len(returns) != 1:
            raise ValueError(f"models disagree on realized return for {key}")
        model_scores = [by_model[model][1] for model in expected_models]
        outer_fold, partition, symbol, as_of, horizon, target_date = key
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
                y_ret=returns.pop(),
                target_date=target_date,
                domain=domains.pop(),
                component_scores=tuple(
                    (model, by_model[model][1]) for model in expected_models
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


def select_calibration_gate(
    rows: list[EnsemblePrediction],
    *,
    target_precision: float,
    min_emits: int,
    min_lcb: float,
    confidence_level: float,
    coverage_grid: tuple[float, ...],
) -> dict[str, float | int] | None:
    """Select only among predeclared coverage levels using calibration labels."""
    usable = sorted(
        (row for row in rows if row.score != 0 and math.isfinite(row.score)),
        key=lambda row: abs(row.score),
        reverse=True,
    )
    best: dict[str, float | int] | None = None
    for requested_coverage in sorted(set(coverage_grid)):
        if not 0 < requested_coverage <= 1:
            raise ValueError("calibration coverage levels must be in (0, 1]")
        requested = math.ceil(len(usable) * requested_coverage)
        if requested < min_emits or requested > len(usable):
            continue
        threshold = abs(usable[requested - 1].score)
        selected = [row for row in usable if abs(row.score) >= threshold]
        hits = sum(1 for row in selected if _is_hit(row))
        precision = hits / len(selected)
        lcb = wilson_lower_bound(
            hits,
            len(selected),
            confidence_level=confidence_level,
        )
        if precision < target_precision or lcb is None or lcb < min_lcb:
            continue
        candidate: dict[str, float | int] = {
            "threshold": threshold,
            "emits": len(selected),
            "hits": hits,
            "precision": precision,
            "precision_lcb": lcb,
            "coverage": len(selected) / len(usable),
            "requested_coverage": requested_coverage,
        }
        if best is None or int(candidate["emits"]) > int(best["emits"]):
            best = candidate
    return best


def _ensemble_candidates(models: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Predeclared bounded search: singles, pairs, and the full ensemble."""
    singles = [(model,) for model in models]
    pairs = list(combinations(models, 2))
    full = [models] if len(models) > 2 else []
    return tuple(singles + pairs + full)


def _rescore_rows(
    rows: list[EnsemblePrediction],
    models: tuple[str, ...],
) -> list[EnsemblePrediction]:
    rescored: list[EnsemblePrediction] = []
    for row in rows:
        components = dict(row.component_scores)
        values = [components[model] for model in models]
        rescored.append(
            replace(
                row,
                score=statistics.fmean(values),
                disagreement=(
                    statistics.pstdev(values) if len(values) > 1 else 0.0
                ),
            )
        )
    return rescored


def evaluate_nested_ensemble(
    rows: list[EnsemblePrediction],
    *,
    contract: SuccessContract,
    ensemble_mode: str = "equal",
) -> dict[str, Any]:
    """Calibrate gates per outer fold, then score only corresponding tests."""
    group_keys = sorted({(row.outer_fold, row.horizon) for row in rows})
    folds: list[dict[str, Any]] = []
    emitted_rows: list[EnsemblePrediction] = []
    all_test_rows: list[EnsemblePrediction] = []
    total_test_rows = 0

    for outer_fold, horizon in group_keys:
        calibration_base = [
            row
            for row in rows
            if row.outer_fold == outer_fold
            and row.horizon == horizon
            and row.partition == "calibration"
        ]
        test_base = [
            row
            for row in rows
            if row.outer_fold == outer_fold
            and row.horizon == horizon
            and row.partition == "test"
        ]
        total_test_rows += len(test_base)
        all_test_rows.extend(test_base)
        component_models = tuple(
            model for model, _score in calibration_base[0].component_scores
        ) if calibration_base else ()
        if not component_models:
            candidates = ()
        elif ensemble_mode == "equal":
            candidates = (component_models,)
        elif ensemble_mode == "calibration_select":
            candidates = _ensemble_candidates(component_models)
        else:
            raise ValueError("ensemble_mode must be equal or calibration_select")

        selected_models: tuple[str, ...] | None = None
        test: list[EnsemblePrediction] = []
        gate: dict[str, float | int] | None = None
        for candidate_models in candidates:
            candidate_calibration = _rescore_rows(
                calibration_base,
                candidate_models,
            )
            candidate_gate = select_calibration_gate(
                candidate_calibration,
                target_precision=contract.target_precision,
                min_emits=contract.min_calibration_emits,
                min_lcb=contract.min_calibration_lcb,
                confidence_level=contract.confidence_level,
                coverage_grid=contract.calibration_coverages,
            )
            if candidate_gate is None:
                continue
            candidate_rank = (
                int(candidate_gate["emits"]),
                float(candidate_gate["precision_lcb"]),
                float(candidate_gate["precision"]),
                -len(candidate_models),
            )
            current_rank = (
                int(gate["emits"]),
                float(gate["precision_lcb"]),
                float(gate["precision"]),
                -len(selected_models or ()),
            ) if gate is not None else None
            if current_rank is None or candidate_rank > current_rank:
                selected_models = candidate_models
                test = _rescore_rows(test_base, candidate_models)
                gate = candidate_gate
        threshold = float(gate["threshold"]) if gate is not None else None
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
                "calibration_rows": len(calibration_base),
                "test_rows": len(test_base),
                "selected_models": list(selected_models or ()),
                "threshold": threshold,
                "calibration_gate": gate,
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
    session_counts = Counter(row.as_of for row in emitted_rows)
    domain_counts = Counter(row.domain for row in emitted_rows)
    symbols = len(symbol_counts)
    emit_days = len(session_counts)
    max_symbol_share = max(symbol_counts.values(), default=0) / emits if emits else 0.0
    max_session_share = (
        max(session_counts.values(), default=0) / emits if emits else 0.0
    )
    precision_lcb = wilson_lower_bound(
        hits,
        emits,
        confidence_level=contract.confidence_level,
    )
    stable_folds = sum(
        1
        for fold in folds
        if fold["precision"] is not None
        and int(fold["emits"]) >= contract.min_fold_emits
        and float(fold["precision"]) >= contract.min_fold_precision
    )
    fold_pass_fraction = stable_folds / len(folds) if folds else 0.0
    ranking_rows = [row for row in all_test_rows if row.y_ret is not None]
    rank_ic, rank_ic_sessions = (
        mean_daily_rank_ic(
            [row.as_of for row in ranking_rows],
            [row.score for row in ranking_rows],
            [float(row.y_ret) for row in ranking_rows],
            min_names=20,
        )
        if ranking_rows
        else (None, 0)
    )
    all_balanced_accuracy = (
        balanced_direction_accuracy(
            [float(row.y_dir) for row in all_test_rows],
            [row.score for row in all_test_rows],
        )
        if all_test_rows
        else None
    )
    all_mcc = (
        matthews_direction_correlation(
            [float(row.y_dir) for row in all_test_rows],
            [row.score for row in all_test_rows],
        )
        if all_test_rows
        else None
    )
    spread = (
        cost_adjusted_top_bottom_spread(
            [row.as_of for row in ranking_rows],
            [row.symbol for row in ranking_rows],
            [row.score for row in ranking_rows],
            [float(row.y_ret) for row in ranking_rows],
            fraction=0.10,
            cost_bps=112.0,
            min_names=20,
        )
        if ranking_rows
        else None
    )
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
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "ensemble_mode": ensemble_mode,
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
            "emit_days": emit_days,
            "max_symbol_share": max_symbol_share,
            "max_session_share": max_session_share,
            "domain_counts": dict(sorted(domain_counts.items())),
            "flat_outcomes": sum(1 for row in emitted_rows if row.y_dir == 0),
            "rank_ic": rank_ic,
            "rank_ic_sessions": rank_ic_sessions,
            "balanced_accuracy": all_balanced_accuracy,
            "mcc": all_mcc,
            "post_cost_mean_return": (
                spread.mean_net_return if spread is not None else None
            ),
            "post_cost_sessions": spread.sessions if spread is not None else 0,
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
        f"**Target:** `{report.get('target', 'unknown')}`",
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
        "## Full-coverage challenger metrics",
        "",
        (
            f"- RankIC: `{summary.get('rank_ic')}` "
            f"over `{summary.get('rank_ic_sessions')}` sessions"
        ),
        f"- Balanced accuracy: `{summary.get('balanced_accuracy')}`",
        f"- MCC: `{summary.get('mcc')}`",
        (
            f"- Mean post-cost top/bottom return: "
            f"`{summary.get('post_cost_mean_return')}`"
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
                "target": spec.target,
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
    report = evaluate_nested_ensemble(
        rows,
        contract=contract,
        ensemble_mode=args.ensemble_mode,
    )
    report["target"] = artifacts[0].spec.target
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
    matrix.add_argument("--target", choices=TARGETS, default="absolute")
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
    aggregate.add_argument(
        "--ensemble-mode",
        choices=("equal", "calibration_select"),
        default="calibration_select",
    )
    args = parser.parse_args(argv)

    if args.command == "matrix":
        specs = build_training_matrix(
            models=_parse_csv_strings(args.models),
            outer_folds=args.folds,
            horizons=_parse_csv_ints(args.horizons),
            seeds=_parse_csv_ints(args.seeds),
            target=args.target,
        )
        print(json.dumps(_matrix_payload(specs), separators=(",", ":")))
        return
    _aggregate_command(args)


if __name__ == "__main__":
    main()
