"""Offline turnover-aware portfolio construction for saved ML scores.

The functions in this module deliberately do not rescore, refit, or write live
policies. They consume existing per-session scores and realized returns, then
change only the portfolio construction cadence/rules used for cost accounting.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from koel.ml.distributed import load_prediction_artifact
from koel.ml.metrics import (
    CostAdjustedSpread,
    cost_adjusted_top_bottom_spread,
    mean_daily_rank_ic,
)


@dataclass(frozen=True, slots=True)
class ScoreRow:
    partition: str
    as_of: date
    symbol: str
    score: float
    y_ret: float


@dataclass(frozen=True, slots=True)
class PortfolioVariant:
    name: str
    fraction: float = 0.10
    rebalance_every: int = 1
    persistence_exit_fraction: float | None = None
    min_holding_period: int = 1
    rebalance_delay: int = 0
    min_names: int = 20

    def __post_init__(self) -> None:
        if not 0 < self.fraction < 0.5:
            raise ValueError("fraction must be in (0, 0.5)")
        if self.rebalance_every < 1:
            raise ValueError("rebalance_every must be >= 1")
        if self.persistence_exit_fraction is not None and not (
            self.fraction <= self.persistence_exit_fraction < 0.5
        ):
            raise ValueError("persistence_exit_fraction must be in [fraction, 0.5)")
        if self.min_holding_period < 1:
            raise ValueError("min_holding_period must be >= 1")
        if self.rebalance_delay < 0:
            raise ValueError("rebalance_delay must be >= 0")
        if self.min_names < 2:
            raise ValueError("min_names must be >= 2")


PERSIST_EXIT_10_TOP_BOTTOM_05 = PortfolioVariant(
    "persistence_exit_10_top_bottom_05",
    fraction=0.05,
    persistence_exit_fraction=0.10,
)


@dataclass(frozen=True, slots=True)
class BookState:
    weights: dict[str, float]
    holding_ages: dict[str, int]


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    sessions: int
    mean_gross_return: float
    mean_net_return: float
    compounded_net_return: float
    mean_one_way_turnover: float
    break_even_cost_bps: float | None
    rank_ic: float | None
    rank_ic_sessions: int


def default_variants() -> list[PortfolioVariant]:
    """Cost/turnover candidates that reuse the daily score stream."""
    return [
        PortfolioVariant("baseline_daily_top_bottom_10", fraction=0.10),
        PortfolioVariant("lower_fraction_daily_top_bottom_05", fraction=0.05),
        PortfolioVariant(
            "weekly_5_sessions_top_bottom_10",
            fraction=0.10,
            rebalance_every=5,
        ),
        PortfolioVariant(
            "weekly_5_sessions_top_bottom_05",
            fraction=0.05,
            rebalance_every=5,
        ),
        PortfolioVariant(
            "persistence_exit_15_top_bottom_10",
            fraction=0.10,
            persistence_exit_fraction=0.15,
        ),
        PortfolioVariant(
            "persistence_exit_20_top_bottom_10",
            fraction=0.10,
            persistence_exit_fraction=0.20,
        ),
        PERSIST_EXIT_10_TOP_BOTTOM_05,
        PortfolioVariant("min_hold_3_top_bottom_10", fraction=0.10, min_holding_period=3),
        PortfolioVariant("min_hold_5_top_bottom_10", fraction=0.10, min_holding_period=5),
        PortfolioVariant(
            "weekly_5_min_hold_3_top_bottom_10",
            fraction=0.10,
            rebalance_every=5,
            min_holding_period=3,
        ),
        PortfolioVariant("delayed_1_daily_top_bottom_10", fraction=0.10, rebalance_delay=1),
        PortfolioVariant(
            "delayed_1_weekly_5_top_bottom_10",
            fraction=0.10,
            rebalance_every=5,
            rebalance_delay=1,
        ),
    ]


def construct_session_book(
    scores: dict[str, float],
    *,
    variant: PortfolioVariant = PERSIST_EXIT_10_TOP_BOTTOM_05,
    previous: BookState | None = None,
) -> BookState | None:
    """Build one session's dollar-neutral top/bottom book with optional persistence.

    ``scores`` maps symbol -> model score (higher = more bullish).
    Returns None if ranking fails min_names / tie / empty leg rules (same as offline).
    """
    ranked = _ranked_rows(
        [(symbol, score, 0.0) for symbol, score in scores.items()],
        variant,
    )
    if ranked is None:
        return None

    previous_weights = previous.weights if previous is not None else {}
    previous_ages = previous.holding_ages if previous is not None else {}
    weights = _construct_weights(
        ranked,
        variant,
        previous_weights=previous_weights,
        holding_ages=previous_ages,
    )
    return BookState(
        weights=weights,
        holding_ages=_next_holding_ages(weights, previous_weights, previous_ages),
    )


def book_state_from_signed_scores(
    signed: dict[str, float],
    *,
    previous_ages: dict[str, int] | None = None,
) -> BookState:
    """Rebuild BookState from prior emitted y_pred signs.

    Nonzero weights are equal-weight per side.
    """
    longs = [symbol for symbol, score in signed.items() if score > 0]
    shorts = [symbol for symbol, score in signed.items() if score < 0]
    weights = {
        **{symbol: -1.0 / len(shorts) for symbol in shorts},
        **{symbol: 1.0 / len(longs) for symbol in longs},
    }
    ages = {
        symbol: previous_ages.get(symbol, 1) if previous_ages is not None else 1
        for symbol in weights
    }
    return BookState(weights=weights, holding_ages=ages)


def evaluate_portfolio_variant(
    rows: list[ScoreRow],
    variant: PortfolioVariant,
    *,
    cost_bps: float = 112.0,
) -> PortfolioResult | None:
    """Evaluate one leakage-safe construction variant on existing scores."""
    rank_ic, rank_ic_sessions = mean_daily_rank_ic(
        [row.as_of for row in rows],
        [row.score for row in rows],
        [row.y_ret for row in rows],
    )
    if variant.name == "baseline_daily_top_bottom_10" and variant.fraction == 0.10:
        baseline = cost_adjusted_top_bottom_spread(
            [row.as_of for row in rows],
            [row.symbol for row in rows],
            [row.score for row in rows],
            [row.y_ret for row in rows],
            fraction=variant.fraction,
            cost_bps=cost_bps,
            min_names=variant.min_names,
        )
        return _from_cost_adjusted(baseline, rank_ic, rank_ic_sessions)

    by_day = _group_by_day(rows)
    previous_weights: dict[str, float] = {}
    holding_ages: dict[str, int] = {}
    pending: dict[int, dict[str, float]] = {}
    gross_returns: list[float] = []
    net_returns: list[float] = []
    turnovers: list[float] = []
    total_gross = 0.0
    total_traded = 0.0

    valid_index = -1
    for session in sorted(by_day):
        ranked = _ranked_rows(by_day[session], variant)
        if ranked is None:
            continue
        valid_index += 1

        if valid_index % variant.rebalance_every == 0:
            desired = _construct_weights(
                ranked,
                variant,
                previous_weights=previous_weights,
                holding_ages=holding_ages,
            )
            apply_at = valid_index + variant.rebalance_delay
            pending[apply_at] = desired

        weights = pending.pop(valid_index, previous_weights)
        if not weights:
            previous_weights = {}
            holding_ages = {}
            continue

        realized_by_symbol = {symbol: realized for symbol, _score, realized in ranked}
        weights = {
            symbol: weight
            for symbol, weight in weights.items()
            if symbol in realized_by_symbol
        }
        if not weights:
            previous_weights = {}
            holding_ages = {}
            continue

        gross = sum(
            weight * realized_by_symbol[symbol] for symbol, weight in weights.items()
        )
        traded = sum(
            abs(weights.get(symbol, 0.0) - previous_weights.get(symbol, 0.0))
            for symbol in set(weights) | set(previous_weights)
        )
        net = gross - cost_bps / 10_000 * traded
        gross_returns.append(gross)
        net_returns.append(net)
        turnovers.append(traded / 2)
        total_gross += gross
        total_traded += traded
        holding_ages = _next_holding_ages(weights, previous_weights, holding_ages)
        previous_weights = weights

    if not gross_returns:
        return None
    return PortfolioResult(
        sessions=len(gross_returns),
        mean_gross_return=sum(gross_returns) / len(gross_returns),
        mean_net_return=sum(net_returns) / len(net_returns),
        compounded_net_return=math.prod(1.0 + value for value in net_returns) - 1.0,
        mean_one_way_turnover=sum(turnovers) / len(turnovers),
        break_even_cost_bps=(
            10_000 * total_gross / total_traded if total_traded > 0 else None
        ),
        rank_ic=rank_ic,
        rank_ic_sessions=rank_ic_sessions,
    )


def evaluate_models(
    input_dir: Path,
    *,
    models: tuple[str, ...],
    partitions: tuple[str, ...] = ("test",),
    variants: list[PortfolioVariant] | None = None,
    cost_bps: float = 112.0,
) -> dict[str, Any]:
    variants = variants or default_variants()
    model_results: dict[str, Any] = {}
    best: dict[str, Any] | None = None
    for model in models:
        rows = load_model_rows(input_dir, model=model, partitions=partitions)
        results: list[dict[str, Any]] = []
        for variant in variants:
            result = evaluate_portfolio_variant(rows, variant, cost_bps=cost_bps)
            if result is None:
                continue
            payload = {
                **asdict(variant),
                **asdict(result),
            }
            results.append(payload)
            if best is None or payload["mean_net_return"] > best["mean_net_return"]:
                best = {
                    "model": model,
                    "variant": variant.name,
                    **payload,
                }
        baseline = next(
            (
                row
                for row in results
                if row["name"] == "baseline_daily_top_bottom_10"
            ),
            None,
        )
        model_results[model] = {
            "rows": len(rows),
            "partitions": list(partitions),
            "baseline": baseline,
            "variants": sorted(
                results,
                key=lambda row: row["mean_net_return"],
                reverse=True,
            ),
        }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_dir": str(input_dir),
        "cost_bps": cost_bps,
        "models": model_results,
        "best": best,
    }


def load_model_rows(
    input_dir: Path,
    *,
    model: str,
    partitions: tuple[str, ...] = ("test",),
) -> list[ScoreRow]:
    paths = sorted(input_dir.glob(f"*-{model}.predictions.jsonl.gz"))
    if not paths:
        raise FileNotFoundError(f"no prediction shards for model {model} in {input_dir}")
    wanted = set(partitions)
    rows: list[ScoreRow] = []
    seen: set[tuple[str, date, str]] = set()
    for path in paths:
        artifact = load_prediction_artifact(path)
        if artifact.spec.model != model:
            continue
        for prediction in artifact.predictions:
            if prediction.partition not in wanted or prediction.y_ret is None:
                continue
            if not (
                math.isfinite(prediction.score) and math.isfinite(prediction.y_ret)
            ):
                continue
            key = (prediction.partition, prediction.as_of, prediction.symbol)
            if key in seen:
                raise ValueError(f"duplicate prediction row for {model}: {key}")
            seen.add(key)
            rows.append(
                ScoreRow(
                    partition=prediction.partition,
                    as_of=prediction.as_of,
                    symbol=prediction.symbol,
                    score=prediction.score,
                    y_ret=prediction.y_ret,
                )
            )
    if not rows:
        raise ValueError(f"no usable {partitions} rows for model {model}")
    return sorted(rows, key=lambda row: (row.as_of, row.symbol))


def write_cost_engineering_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cost_engineering_results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "cost_engineering_results.md").write_text(
        render_markdown_report(payload),
        encoding="utf-8",
    )


def render_markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Loop 1 cost/turnover engineering",
        "",
        f"- Input: `{payload['input_dir']}`",
        f"- Cost: {payload['cost_bps']:.0f} bps on traded notional",
        "- Scores are unchanged; RankIC is repeated per variant to make that explicit.",
        "",
    ]
    best = payload.get("best")
    if best:
        lines.extend(
            [
                "## Best net variant",
                "",
                (
                    f"- `{best['model']}` / `{best['variant']}`: "
                    f"net {_pct(best['mean_net_return'])}, "
                    f"gross {_pct(best['mean_gross_return'])}, "
                    f"turnover {best['mean_one_way_turnover']:.3f}, "
                    f"sessions {best['sessions']}"
                ),
                "",
            ]
        )
    for model, result in payload["models"].items():
        baseline = result.get("baseline")
        lines.extend([f"## {model}", ""])
        if baseline:
            lines.append(
                f"Baseline daily top/bottom 10%: net "
                f"{_pct(baseline['mean_net_return'])}, gross "
                f"{_pct(baseline['mean_gross_return'])}, turnover "
                f"{baseline['mean_one_way_turnover']:.3f}, RankIC "
                f"{_float(baseline['rank_ic'])}, sessions {baseline['sessions']}."
            )
            lines.append("")
        lines.extend(
            [
                "| Variant | RankIC | Gross | Net@112bps | Turnover | Sessions |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for row in result["variants"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{row['name']}`",
                        _float(row["rank_ic"]),
                        _pct(row["mean_gross_return"]),
                        _pct(row["mean_net_return"]),
                        f"{row['mean_one_way_turnover']:.3f}",
                        str(row["sessions"]),
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)


def _from_cost_adjusted(
    result: CostAdjustedSpread | None,
    rank_ic: float | None,
    rank_ic_sessions: int,
) -> PortfolioResult | None:
    if result is None:
        return None
    return PortfolioResult(
        sessions=result.sessions,
        mean_gross_return=result.mean_gross_return,
        mean_net_return=result.mean_net_return,
        compounded_net_return=result.compounded_net_return,
        mean_one_way_turnover=result.mean_one_way_turnover,
        break_even_cost_bps=result.break_even_cost_bps,
        rank_ic=rank_ic,
        rank_ic_sessions=rank_ic_sessions,
    )


def _group_by_day(
    rows: list[ScoreRow],
) -> dict[date, list[tuple[str, float, float]]]:
    by_day: dict[date, list[tuple[str, float, float]]] = defaultdict(list)
    for row in rows:
        if math.isfinite(row.score) and math.isfinite(row.y_ret):
            by_day[row.as_of].append((row.symbol, row.score, row.y_ret))
    return by_day


def _ranked_rows(
    rows: list[tuple[str, float, float]],
    variant: PortfolioVariant,
) -> list[tuple[str, float, float]] | None:
    if len(rows) < variant.min_names:
        return None
    ranked = sorted(rows, key=lambda row: (row[1], row[0]))
    leg_size = _leg_size(len(ranked), variant.fraction)
    if leg_size == 0 or leg_size * 2 >= len(ranked):
        return None
    if ranked[leg_size - 1][1] == ranked[leg_size][1]:
        return None
    if ranked[-leg_size - 1][1] == ranked[-leg_size][1]:
        return None
    return ranked


def _construct_weights(
    ranked: list[tuple[str, float, float]],
    variant: PortfolioVariant,
    *,
    previous_weights: dict[str, float],
    holding_ages: dict[str, int],
) -> dict[str, float]:
    leg_size = _leg_size(len(ranked), variant.fraction)
    rank_by_symbol = {symbol: index for index, (symbol, _score, _ret) in enumerate(ranked)}
    longs = _select_side(
        ranked,
        leg_size,
        variant,
        previous_weights=previous_weights,
        holding_ages=holding_ages,
        rank_by_symbol=rank_by_symbol,
        side=1,
    )
    shorts = _select_side(
        ranked,
        leg_size,
        variant,
        previous_weights=previous_weights,
        holding_ages=holding_ages,
        rank_by_symbol=rank_by_symbol,
        side=-1,
    )
    return {
        **{symbol: -1.0 / leg_size for symbol in shorts},
        **{symbol: 1.0 / leg_size for symbol in longs},
    }


def _select_side(
    ranked: list[tuple[str, float, float]],
    leg_size: int,
    variant: PortfolioVariant,
    *,
    previous_weights: dict[str, float],
    holding_ages: dict[str, int],
    rank_by_symbol: dict[str, int],
    side: int,
) -> list[str]:
    n = len(ranked)
    previous = [
        symbol
        for symbol, weight in previous_weights.items()
        if (weight > 0 and side > 0) or (weight < 0 and side < 0)
    ]
    exit_fraction = variant.persistence_exit_fraction or variant.fraction
    exit_size = max(leg_size, math.ceil(n * exit_fraction))

    def is_exit_rank(symbol: str) -> bool:
        rank = rank_by_symbol.get(symbol)
        if rank is None:
            return False
        return rank >= n - exit_size if side > 0 else rank < exit_size

    def is_locked(symbol: str) -> bool:
        return holding_ages.get(symbol, 0) < variant.min_holding_period

    kept = [
        symbol
        for symbol in previous
        if symbol in rank_by_symbol
        and (
            is_locked(symbol)
            or (
                variant.persistence_exit_fraction is not None
                and is_exit_rank(symbol)
            )
        )
    ]
    kept = sorted(
        set(kept),
        key=lambda symbol: rank_by_symbol[symbol],
        reverse=side > 0,
    )[:leg_size]
    if len(kept) >= leg_size:
        return kept

    ordered = (
        [symbol for symbol, _score, _ret in reversed(ranked)]
        if side > 0
        else [symbol for symbol, _score, _ret in ranked]
    )
    selected = list(kept)
    for symbol in ordered:
        if symbol in selected:
            continue
        selected.append(symbol)
        if len(selected) == leg_size:
            break
    return selected


def _next_holding_ages(
    weights: dict[str, float],
    previous_weights: dict[str, float],
    holding_ages: dict[str, int],
) -> dict[str, int]:
    next_ages: dict[str, int] = {}
    for symbol, weight in weights.items():
        previous = previous_weights.get(symbol)
        if previous is not None and previous * weight > 0:
            next_ages[symbol] = holding_ages.get(symbol, 0) + 1
        else:
            next_ages[symbol] = 1
    return next_ages


def _leg_size(n_rows: int, fraction: float) -> int:
    return max(1, math.floor(n_rows * fraction))


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.2f}%"


def _float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


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
        default=Path("/tmp/cpu-cost-eng"),
    )
    parser.add_argument(
        "--models",
        default="xgb_two_stage,double_ensemble_native,hgb_two_stage",
        help="Comma-separated model names to evaluate.",
    )
    parser.add_argument(
        "--partitions",
        default="test",
        help="Comma-separated prediction partitions to evaluate.",
    )
    parser.add_argument("--cost-bps", type=float, default=112.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = evaluate_models(
        args.input_dir,
        models=tuple(item.strip() for item in args.models.split(",") if item.strip()),
        partitions=tuple(
            item.strip() for item in args.partitions.split(",") if item.strip()
        ),
        cost_bps=args.cost_bps,
    )
    write_cost_engineering_report(payload, args.output_dir)
    print(json.dumps(payload["best"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
