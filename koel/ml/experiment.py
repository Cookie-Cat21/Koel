"""Orchestrate offline ML walk-forward experiment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from koel.logging_setup import get_logger
from koel.ml import sklearn_available
from koel.ml.dataset import load_symbol_bars
from koel.ml.report import write_report
from koel.ml.walkforward import (
    WalkForwardResult,
    decide,
    evaluate_b0_naive,
    run_walkforward_sklearn,
)
from koel.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    horizons: tuple[int, ...] = (1, 5)
    limit_symbols: int | None = None
    min_history: int = 60
    min_train_days: int = 120
    fold_step: int = 20
    out_dir: Path = Path("docs/experiments")


async def run_ml_experiment(
    *,
    storage: Storage,
    config: ExperimentConfig | None = None,
) -> WalkForwardResult:
    cfg = config or ExperimentConfig()
    if not sklearn_available():
        result = WalkForwardResult(
            decision="UNCLEAR",
            reasons=["sklearn/numpy not installed — pip install -e '.[ml]'"],
            leakage_ok=True,
        )
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        write_report(
            result,
            out_md=cfg.out_dir / f"ml_walkforward_{stamp}.md",
            symbols=0,
            bars_hint="n/a",
        )
        return result

    series = await load_symbol_bars(storage, limit_symbols=cfg.limit_symbols)
    n_bars = sum(len(v) for v in series.values())
    log.info(
        "ml_experiment_loaded",
        symbols=len(series),
        bars=n_bars,
        horizons=list(cfg.horizons),
    )

    all_metrics = []
    for horizon in cfg.horizons:
        if horizon == 5:
            all_metrics.append(
                evaluate_b0_naive(
                    series,
                    horizon=horizon,
                    min_history=cfg.min_history,
                )
            )
        all_metrics.extend(
            run_walkforward_sklearn(
                series,
                horizon=horizon,
                min_history=cfg.min_history,
                min_train_days=cfg.min_train_days,
                fold_step=cfg.fold_step,
            )
        )

    result = decide(all_metrics)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_md = cfg.out_dir / f"ml_walkforward_{stamp}.md"
    write_report(
        result,
        out_md=out_md,
        symbols=len(series),
        bars_hint=f"{n_bars} daily_bars rows",
    )
    log.info(
        "ml_experiment_done",
        decision=result.decision,
        report=str(out_md),
        metrics=len(result.metrics),
    )
    return result
