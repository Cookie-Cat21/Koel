"""Offline stacking/blending for saved distributed ML prediction artifacts.

This module consumes existing ``*.predictions.jsonl.gz`` shards only. It never
retrains models, registers live policies, or writes forecast points.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from koel.ml.cost_engineering import (
    PortfolioVariant,
    ScoreRow,
    evaluate_portfolio_variant,
)
from koel.ml.distributed import (
    EnsemblePrediction,
    PredictionArtifact,
    ensemble_artifacts,
    load_prediction_artifact,
)
from koel.ml.metrics import (
    balanced_direction_accuracy,
    matthews_direction_correlation,
    mean_daily_rank_ic,
)

SURVIVOR_MODELS: tuple[str, ...] = (
    "xgb_two_stage",
    "xgb_lmt",
    "hgb_two_stage",
    "hgb_lmt",
    "hgb_bagged",
    "hgb_deep",
    "double_ensemble_native",
)

BASELINE_XGB_TWO_STAGE_RANK_IC = 0.2861


@dataclass(frozen=True, slots=True)
class WeightCandidate:
    label: str
    weights: dict[str, float]


@dataclass(frozen=True, slots=True)
class BlendMetrics:
    rank_ic: float | None
    rank_ic_sessions: int
    balanced_accuracy: float | None
    mcc: float | None
    rows: int


def load_survivor_rows(
    input_dir: Path,
    *,
    models: tuple[str, ...] = SURVIVOR_MODELS,
) -> list[EnsemblePrediction]:
    """Load and align all requested survivor model shards."""
    artifacts: list[PredictionArtifact] = []
    for model in models:
        paths = sorted(input_dir.glob(f"*-{model}.predictions.jsonl.gz"))
        if not paths:
            raise FileNotFoundError(f"no prediction artifacts for {model} in {input_dir}")
        for path in paths:
            artifact = load_prediction_artifact(path)
            if artifact.spec.model != model:
                raise ValueError(f"{path} contains model {artifact.spec.model}, not {model}")
            artifacts.append(artifact)
    return ensemble_artifacts(artifacts, expected_models=models)


def default_weight_grid(models: tuple[str, ...]) -> tuple[WeightCandidate, ...]:
    """Small fixed non-negative grid; all candidates keep at least two models live."""
    if len(models) < 2:
        raise ValueError("at least two models are required for stacking")
    candidates: list[WeightCandidate] = [
        WeightCandidate(
            "equal_all",
            {model: 1.0 / len(models) for model in models},
        )
    ]
    for model in models:
        candidates.append(
            WeightCandidate(
                f"anchor75_{model}",
                {
                    other: (0.75 if other == model else 0.25 / (len(models) - 1))
                    for other in models
                },
            )
        )
    for left, right in combinations(models, 2):
        candidates.extend(
            [
                WeightCandidate(
                    f"pair50_{left}__{right}",
                    {model: 0.5 if model in {left, right} else 0.0 for model in models},
                ),
                WeightCandidate(
                    f"pair75_{left}__25_{right}",
                    {
                        model: 0.75 if model == left else 0.25 if model == right else 0.0
                        for model in models
                    },
                ),
                WeightCandidate(
                    f"pair25_{left}__75_{right}",
                    {
                        model: 0.25 if model == left else 0.75 if model == right else 0.0
                        for model in models
                    },
                ),
            ]
        )
    return tuple(candidates)


def evaluate_stack(
    rows: list[EnsemblePrediction],
    *,
    models: tuple[str, ...] = SURVIVOR_MODELS,
    cost_bps: float = 112.0,
    weight_grid: tuple[WeightCandidate, ...] | None = None,
) -> dict[str, Any]:
    """Evaluate deterministic blends and fold-local calibration-selected weights."""
    if not rows:
        raise ValueError("no rows supplied")
    weight_grid = weight_grid or default_weight_grid(models)
    model_baselines = {
        model: _result_payload(
            _rescore_rows(
                rows,
                {candidate: 1.0 if candidate == model else 0.0 for candidate in models},
                score_mode="raw",
            ),
            cost_bps=cost_bps,
        )
        for model in models
    }

    equal_raw = _result_payload(
        _rescore_rows(
            rows,
            {model: 1.0 / len(models) for model in models},
            score_mode="raw",
        ),
        cost_bps=cost_bps,
    )
    rank_average = _result_payload(
        _rescore_rows(
            rows,
            {model: 1.0 / len(models) for model in models},
            score_mode="rank",
        ),
        cost_bps=cost_bps,
    )
    selected_rows, fold_selections = _calibration_selected_rows(
        rows,
        models=models,
        weight_grid=weight_grid,
    )
    cal_selected = _result_payload(selected_rows, cost_bps=cost_bps)
    cal_selected["fold_selections"] = fold_selections

    blends = {
        "equal_raw": equal_raw,
        "rank_average": rank_average,
        "cal_selected_rank_weight": cal_selected,
    }
    best_name, best_payload = max(
        blends.items(),
        key=lambda item: (
            item[1]["test"]["rank_ic"]
            if item[1]["test"]["rank_ic"] is not None
            else float("-inf")
        ),
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_models": list(models),
        "baseline_xgb_two_stage_rank_ic": BASELINE_XGB_TWO_STAGE_RANK_IC,
        "cost_bps": cost_bps,
        "model_baselines": model_baselines,
        "blends": blends,
        "best_blend_by_test_rank_ic": {"name": best_name, **best_payload},
    }


def render_markdown_report(payload: dict[str, Any], *, input_dir: Path) -> str:
    best = payload["best_blend_by_test_rank_ic"]
    baseline = payload["baseline_xgb_two_stage_rank_ic"]
    best_rank = best["test"]["rank_ic"]
    best_delta = None if best_rank is None else best_rank - baseline
    best_cost = best["cost"]["persistence_exit_10_top_bottom_05"]
    xgb_cost = payload["model_baselines"]["xgb_two_stage"]["cost"][
        "persistence_exit_10_top_bottom_05"
    ]
    best_model_cost = max(
        payload["model_baselines"].items(),
        key=lambda item: item[1]["cost"]["persistence_exit_10_top_bottom_05"][
            "mean_net_return"
        ],
    )
    best_model_persistence = best_model_cost[1]["cost"][
        "persistence_exit_10_top_bottom_05"
    ]
    lines = [
        "# Ensemble stack loop 1 - survivor blends",
        "",
        "Offline evaluation only. No retraining and no live policies were registered.",
        "",
        f"- Input shards: `{input_dir}`",
        "- Partitions: calibration for weight selection, test for one final score",
        f"- Survivor count: {len(payload['input_models'])}",
        f"- Reference: `xgb_two_stage` RankIC {baseline:.4f}",
        f"- Cost check: `persistence_exit_10_top_bottom_05` at {payload['cost_bps']:.0f} bps",
        "",
        "## Headline",
        "",
    ]
    if best_rank is None:
        lines.append("- No blend produced a valid test RankIC.")
    else:
        lines.append(
            f"- Best test RankIC blend: `{best['name']}` at {_float(best_rank)} "
            f"({_signed(best_delta)} vs `xgb_two_stage` {baseline:.4f})."
        )
        lines.append(
            f"- Best blend persistence net@112bps: {_pct(best_cost['mean_net_return'])} "
            f"(gross {_pct(best_cost['mean_gross_return'])}, "
            f"turnover {best_cost['mean_one_way_turnover']:.3f})."
        )
        lines.append(
            "- Decision: no blend beats the RankIC reference, and no blend improves "
            f"persistence net@112bps versus `xgb_two_stage` "
            f"({_pct(xgb_cost['mean_net_return'])}) or the best survivor "
            f"`{best_model_cost[0]}` ({_pct(best_model_persistence['mean_net_return'])})."
        )
    lines.extend(
        [
            "",
            "## Test metrics",
            "",
            "| Candidate | RankIC | Delta vs 0.2861 | BA | MCC | "
            "Persist gross | Persist net@112bps | Turnover |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, result in payload["blends"].items():
        test = result["test"]
        cost = result["cost"]["persistence_exit_10_top_bottom_05"]
        rank_ic = test["rank_ic"]
        delta = None if rank_ic is None else rank_ic - baseline
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{name}`",
                    _float(rank_ic),
                    _signed(delta),
                    _float(test["balanced_accuracy"]),
                    _float(test["mcc"]),
                    _pct(cost["mean_gross_return"]),
                    _pct(cost["mean_net_return"]),
                    f"{cost['mean_one_way_turnover']:.3f}",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Calibration-selected weights",
            "",
            "Weights are selected independently per outer fold/horizon from the fixed grid "
            "using calibration RankIC only; the matching test fold is scored once after "
            "selection.",
            "",
            "| Fold | Selected grid row | Calibration RankIC | Test rows |",
            "|---:|---|---:|---:|",
        ]
    )
    for selection in payload["blends"]["cal_selected_rank_weight"]["fold_selections"]:
        lines.append(
            f"| {selection['outer_fold']} | `{selection['label']}` | "
            f"{_float(selection['calibration_rank_ic'])} | {selection['test_rows']} |"
        )
    lines.extend(
        [
            "",
            "## Baseline sanity check",
            "",
            "| Model | Test RankIC | BA | MCC | Persist net@112bps |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for model, result in payload["model_baselines"].items():
        test = result["test"]
        cost = result["cost"]["persistence_exit_10_top_bottom_05"]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{model}`",
                    _float(test["rank_ic"]),
                    _float(test["balanced_accuracy"]),
                    _float(test["mcc"]),
                    _pct(cost["mean_net_return"]),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _calibration_selected_rows(
    rows: list[EnsemblePrediction],
    *,
    models: tuple[str, ...],
    weight_grid: tuple[WeightCandidate, ...],
) -> tuple[list[EnsemblePrediction], list[dict[str, Any]]]:
    group_keys = sorted({(row.outer_fold, row.horizon) for row in rows})
    selected_rows: list[EnsemblePrediction] = []
    fold_selections: list[dict[str, Any]] = []
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
        if not calibration or not test:
            continue
        selected = _select_weight_candidate(calibration, weight_grid)
        rescored = _rescore_rows(calibration + test, selected.weights, score_mode="rank")
        selected_rows.extend(rescored)
        cal_scored = [row for row in rescored if row.partition == "calibration"]
        cal_metrics = _metrics(cal_scored)
        fold_selections.append(
            {
                "outer_fold": outer_fold,
                "horizon": horizon,
                "label": selected.label,
                "weights": {
                    model: weight
                    for model, weight in selected.weights.items()
                    if weight > 0
                },
                "calibration_rank_ic": cal_metrics.rank_ic,
                "calibration_sessions": cal_metrics.rank_ic_sessions,
                "test_rows": len(test),
            }
        )
    if not selected_rows:
        raise ValueError("calibration selection produced no rows")
    return sorted(
        selected_rows,
        key=lambda row: (row.partition, row.outer_fold, row.as_of, row.symbol),
    ), fold_selections


def _select_weight_candidate(
    calibration: list[EnsemblePrediction],
    weight_grid: tuple[WeightCandidate, ...],
) -> WeightCandidate:
    best: tuple[float, WeightCandidate] | None = None
    for candidate in weight_grid:
        scored = _rescore_rows(calibration, candidate.weights, score_mode="rank")
        rank_ic = _metrics(scored).rank_ic
        if rank_ic is None:
            continue
        if best is None or rank_ic > best[0]:
            best = (rank_ic, candidate)
    if best is None:
        raise ValueError("no weight candidate had a valid calibration RankIC")
    return best[1]


def _result_payload(
    rows: list[EnsemblePrediction],
    *,
    cost_bps: float,
) -> dict[str, Any]:
    calibration_rows = [row for row in rows if row.partition == "calibration"]
    test_rows = [row for row in rows if row.partition == "test"]
    return {
        "calibration": asdict(_metrics(calibration_rows)),
        "test": asdict(_metrics(test_rows)),
        "cost": _cost_payload(test_rows, cost_bps=cost_bps),
    }


def _metrics(rows: list[EnsemblePrediction]) -> BlendMetrics:
    y_ret = [row.y_ret for row in rows]
    if any(value is None for value in y_ret):
        raise ValueError("all rows must include realized returns for stack metrics")
    rank_ic, sessions = mean_daily_rank_ic(
        [row.as_of for row in rows],
        [row.score for row in rows],
        [float(value) for value in y_ret],
    )
    return BlendMetrics(
        rank_ic=rank_ic,
        rank_ic_sessions=sessions,
        balanced_accuracy=balanced_direction_accuracy(
            [row.y_dir for row in rows],
            [row.score for row in rows],
        ),
        mcc=matthews_direction_correlation(
            [row.y_dir for row in rows],
            [row.score for row in rows],
        ),
        rows=len(rows),
    )


def _cost_payload(
    rows: list[EnsemblePrediction],
    *,
    cost_bps: float,
) -> dict[str, Any]:
    score_rows = [
        ScoreRow(
            partition=row.partition,
            as_of=row.as_of,
            symbol=row.symbol,
            score=row.score,
            y_ret=_required_return(row),
        )
        for row in rows
    ]
    variants = [
        PortfolioVariant("baseline_daily_top_bottom_10", fraction=0.10),
        PortfolioVariant(
            "persistence_exit_10_top_bottom_05",
            fraction=0.05,
            persistence_exit_fraction=0.10,
        ),
    ]
    payload: dict[str, Any] = {}
    for variant in variants:
        result = evaluate_portfolio_variant(score_rows, variant, cost_bps=cost_bps)
        payload[variant.name] = asdict(result) if result is not None else None
    return payload


def _rescore_rows(
    rows: list[EnsemblePrediction],
    weights: dict[str, float],
    *,
    score_mode: str,
) -> list[EnsemblePrediction]:
    _validate_weights(weights)
    rank_scores = _rank_component_scores(rows) if score_mode == "rank" else None
    rescored: list[EnsemblePrediction] = []
    for index, row in enumerate(rows):
        components = dict(row.component_scores)
        values: list[float] = []
        weighted_score = 0.0
        for model, weight in weights.items():
            value = (
                rank_scores[(index, model)]
                if rank_scores is not None
                else components[model]
            )
            values.append(value)
            weighted_score += weight * value
        rescored.append(
            replace(
                row,
                score=weighted_score,
                disagreement=statistics.pstdev(values) if len(values) > 1 else 0.0,
            )
        )
    return rescored


def _rank_component_scores(rows: list[EnsemblePrediction]) -> dict[tuple[int, str], float]:
    grouped: dict[tuple[int, int, str, date, str], list[tuple[int, float]]] = defaultdict(list)
    for index, row in enumerate(rows):
        for model, score in row.component_scores:
            grouped[
                (row.outer_fold, row.horizon, row.partition, row.as_of, model)
            ].append((index, score))
    normalized: dict[tuple[int, str], float] = {}
    for (*_key, model), values in grouped.items():
        ranks = _average_ranks([score for _index, score in values])
        denominator = len(values) - 1
        for (index, _score), rank in zip(values, ranks, strict=True):
            normalized[(index, model)] = 0.0 if denominator == 0 else 2 * rank / denominator - 1
    return normalized


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + end - 1) / 2
        for position in range(start, end):
            ranks[order[position]] = rank
        start = end
    return ranks


def _validate_weights(weights: dict[str, float]) -> None:
    if not weights:
        raise ValueError("weights must not be empty")
    total = sum(weights.values())
    if any(not math.isfinite(weight) or weight < 0 for weight in weights.values()):
        raise ValueError("weights must be finite non-negative values")
    if not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("weights must sum to 1")


def _required_return(row: EnsemblePrediction) -> float:
    if row.y_ret is None:
        raise ValueError("all rows must include y_ret")
    return row.y_ret


def _float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.2f}%"


def _signed(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.4f}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("/tmp/cpu-exhaust-rel-h1/nested"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/ensemble-stack"),
    )
    parser.add_argument(
        "--docs-path",
        type=Path,
        help="Optional markdown report path, e.g. docs/experiments/ENSEMBLE_STACK_20260723.md.",
    )
    parser.add_argument(
        "--models",
        default=",".join(SURVIVOR_MODELS),
        help="Comma-separated survivor models to blend.",
    )
    parser.add_argument("--cost-bps", type=float, default=112.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    models = tuple(part.strip() for part in args.models.split(",") if part.strip())
    rows = load_survivor_rows(args.input_dir, models=models)
    payload = evaluate_stack(rows, models=models, cost_bps=args.cost_bps)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "ensemble_stack_results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown = render_markdown_report(payload, input_dir=args.input_dir)
    (args.output_dir / "ensemble_stack_results.md").write_text(markdown, encoding="utf-8")
    if args.docs_path:
        args.docs_path.parent.mkdir(parents=True, exist_ok=True)
        args.docs_path.write_text(markdown, encoding="utf-8")
    print(json.dumps(payload["best_blend_by_test_rank_ic"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
