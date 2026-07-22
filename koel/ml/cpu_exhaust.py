"""Exhaustive CPU challenger search: family screen → nested deep → 10k LGB screen.

Selection for the 10k LightGBM grid uses **calibration RankIC only**.
Held-out test metrics are computed once for the shortlisted winners.
Never writes live policies / forecast_points / Telegram.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

from koel.ml.cpu_challengers import (
    CPU_EXHAUST_MODELS,
    lgb_hyperparam_grid,
    predict_lgb_tuned,
)
from koel.ml.dataset import Sample, build_samples
from koel.ml.distributed import (
    ALLOWED_MODELS,
    Prediction,
    ShardSpec,
    SuccessContract,
    ensemble_artifacts,
    evaluate_nested_ensemble,
    write_prediction_artifact,
)
from koel.ml.distributed_worker import (
    _fit_predict_average,
    _rows_for_dates,
    build_outer_split,
)
from koel.ml.harden import _demean_by_day
from koel.ml.iterate import _enrich_cross_section
from koel.ml.metrics import (
    balanced_direction_accuracy,
    cost_adjusted_top_bottom_spread,
    matthews_direction_correlation,
    mean_daily_rank_ic,
)
from koel.ml.research_features import (
    build_research_bar_metadata,
    enrich_market_context,
    enrich_research_quality,
)
from koel.ml.research_fundamentals import enrich_fundamentals
from koel.ml.snapshot import load_bar_snapshot

BASELINE_RANK_IC = 0.2526


def config_fingerprint(config: dict[str, float | int]) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return f"lgb_{digest}"


def _prepare_samples(
    snapshot_dir: Path,
    *,
    horizon: int,
    target: str,
    min_history: int = 60,
    max_abs_return: float = 0.35,
) -> tuple[list[Sample], dict, list[date], str]:
    loaded = load_bar_snapshot(snapshot_dir)
    metadata = build_research_bar_metadata(
        loaded.series,
        dataset=loaded.manifest.dataset,
    )
    base = build_samples(
        loaded.series,
        horizon=horizon,
        min_history=min_history,
        max_abs_return=max_abs_return,
        include_flat=target == "absolute",
    )
    research = enrich_research_quality(base, metadata)
    research = enrich_fundamentals(research, loaded.fundamentals)
    research = enrich_market_context(research)
    if target == "relative":
        research = _demean_by_day(research)
    samples = _enrich_cross_section(research)
    dates = sorted(
        {
            bar.trade_date
            for symbol_bars in loaded.series.values()
            for bar in symbol_bars
        }
    )
    composite = hashlib.sha256(
        (
            loaded.manifest.bars_sha256
            + (loaded.manifest.fundamentals_sha256 or "")
        ).encode("utf-8")
    ).hexdigest()
    return samples, metadata, dates, composite


def _partition_metrics(rows: list[Sample], scores: list[float]) -> dict[str, Any]:
    as_of = [sample.as_of for sample in rows]
    y_ret = [sample.y_ret for sample in rows]
    y_dir = [sample.y_dir for sample in rows]
    rank_ic, sessions = mean_daily_rank_ic(as_of, scores, y_ret)
    return {
        "rank_ic": rank_ic,
        "balanced_accuracy": balanced_direction_accuracy(y_dir, scores),
        "mcc": matthews_direction_correlation(y_dir, scores),
        "n_rows": len(rows),
        "n_sessions": sessions,
        "spread_112": _spread(rows, scores, cost_bps=112.0),
        "spread_30": _spread(rows, scores, cost_bps=30.0),
    }


def _spread(
    rows: list[Sample],
    scores: list[float],
    *,
    cost_bps: float,
) -> float | None:
    result = cost_adjusted_top_bottom_spread(
        [sample.as_of for sample in rows],
        [sample.symbol for sample in rows],
        scores,
        [sample.y_ret for sample in rows],
        fraction=0.10,
        cost_bps=cost_bps,
    )
    if result is None:
        return None
    return float(result.mean_net_return)


def _run_one_model_fold(
    *,
    samples: list[Sample],
    metadata: dict,
    dates: list[date],
    model: str,
    outer_fold: int,
    outer_folds: int,
    horizon: int,
    target: str,
    seeds: tuple[int, ...],
    evaluation_domain: str,
    max_flat_fraction: float,
    snapshot_sha: str,
    run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    if model not in ALLOWED_MODELS:
        raise ValueError(f"unsupported model {model}")
    split = build_outer_split(
        dates,
        outer_fold=outer_fold,
        outer_folds=outer_folds,
        calibration_days=40,
        test_days=40,
        lockbox_days=60,
        embargo_days=max(5, horizon),
        min_train_days=250,
    )
    domain = None if evaluation_domain == "all" else evaluation_domain
    train = _rows_for_dates(
        samples,
        split.calibration_train_dates,
        metadata=metadata,
    )
    calibration = _rows_for_dates(
        samples,
        split.calibration_dates,
        metadata=metadata,
        domain=domain,
        max_flat_fraction=max_flat_fraction,
    )
    test = _rows_for_dates(
        samples,
        split.test_dates,
        metadata=metadata,
        domain=domain,
        max_flat_fraction=max_flat_fraction,
    )
    started = time.perf_counter()
    # Match distributed_worker: one fit on calibration_train, score cal+test.
    evaluation_rows = calibration + test
    evaluation_scores = _fit_predict_average(
        model=model, train=train, test=evaluation_rows, seeds=seeds
    )
    cal_scores = evaluation_scores[: len(calibration)]
    test_scores = evaluation_scores[len(calibration) :]
    elapsed = time.perf_counter() - started
    predictions: list[Prediction] = []
    for sample, score in zip(calibration, cal_scores, strict=True):
        predictions.append(
            Prediction(
                partition="calibration",
                symbol=sample.symbol,
                as_of=sample.as_of,
                horizon=horizon,
                y_dir=1 if sample.y_dir > 0 else -1 if sample.y_dir < 0 else 0,
                score=float(score),
                y_ret=sample.y_ret,
                target_date=sample.target_date,
                domain=evaluation_domain,
            )
        )
    for sample, score in zip(test, test_scores, strict=True):
        predictions.append(
            Prediction(
                partition="test",
                symbol=sample.symbol,
                as_of=sample.as_of,
                horizon=horizon,
                y_dir=1 if sample.y_dir > 0 else -1 if sample.y_dir < 0 else 0,
                score=float(score),
                y_ret=sample.y_ret,
                target_date=sample.target_date,
                domain=evaluation_domain,
            )
        )
    spec = ShardSpec(
        shard_id=f"{target[:3]}-h{horizon}-f{outer_fold:02d}-{model}",
        model=model,
        outer_fold=outer_fold,
        horizon=horizon,
        seeds=seeds,
        target=target,
    )
    path = output_dir / f"{spec.shard_id}.predictions.jsonl.gz"
    write_prediction_artifact(
        path,
        run_id=run_id,
        snapshot_sha256=snapshot_sha,
        spec=spec,
        predictions=predictions,
    )
    cal_metrics = _partition_metrics(calibration, cal_scores)
    test_metrics = _partition_metrics(test, test_scores)
    return {
        "model": model,
        "outer_fold": outer_fold,
        "horizon": horizon,
        "target": target,
        "seconds": elapsed,
        "artifact": str(path),
        "calibration": cal_metrics,
        "test": test_metrics,
    }


def phase_family_screen(
    *,
    samples: list[Sample],
    metadata: dict,
    dates: list[date],
    models: tuple[str, ...],
    horizon: int,
    target: str,
    snapshot_sha: str,
    run_id: str,
    output_dir: Path,
    evaluation_domain: str,
    max_flat_fraction: float,
    workers: int,
) -> list[dict[str, Any]]:
    """Fold-0 screen of every CPU family (calibration RankIC ranks survivors)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    # Process pool would re-import/reload snapshot samples — keep shared-memory
    # sequential for the heavy sample list; models themselves use internal threads.
    os.environ.setdefault("ML_WORKER_THREADS", str(max(1, workers)))
    for model in models:
        try:
            result = _run_one_model_fold(
                samples=samples,
                metadata=metadata,
                dates=dates,
                model=model,
                outer_fold=0,
                outer_folds=3,
                horizon=horizon,
                target=target,
                seeds=(0,),
                evaluation_domain=evaluation_domain,
                max_flat_fraction=max_flat_fraction,
                snapshot_sha=snapshot_sha,
                run_id=run_id,
                output_dir=output_dir / "screen",
            )
            results.append(result)
            print(
                f"[screen] {model}: cal_RankIC={result['calibration']['rank_ic']} "
                f"test_RankIC={result['test']['rank_ic']} "
                f"({result['seconds']:.1f}s)",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - exhaust must keep going
            results.append(
                {
                    "model": model,
                    "error": f"{type(exc).__name__}: {exc}",
                    "calibration": {"rank_ic": None},
                    "test": {"rank_ic": None},
                }
            )
            print(f"[screen] {model}: FAILED {exc}", flush=True)
    results.sort(
        key=lambda row: (
            row.get("calibration", {}).get("rank_ic") is None,
            -(row.get("calibration", {}).get("rank_ic") or -1.0),
        )
    )
    return results


def phase_nested_deep(
    *,
    samples: list[Sample],
    metadata: dict,
    dates: list[date],
    models: tuple[str, ...],
    horizon: int,
    target: str,
    snapshot_sha: str,
    run_id: str,
    output_dir: Path,
    evaluation_domain: str,
    max_flat_fraction: float,
    outer_folds: int,
    seeds: tuple[int, ...],
) -> dict[str, Any]:
    shards_dir = output_dir / "nested"
    shards_dir.mkdir(parents=True, exist_ok=True)
    fold_rows: list[dict[str, Any]] = []
    for model in models:
        for outer_fold in range(outer_folds):
            try:
                result = _run_one_model_fold(
                    samples=samples,
                    metadata=metadata,
                    dates=dates,
                    model=model,
                    outer_fold=outer_fold,
                    outer_folds=outer_folds,
                    horizon=horizon,
                    target=target,
                    seeds=seeds,
                    evaluation_domain=evaluation_domain,
                    max_flat_fraction=max_flat_fraction,
                    snapshot_sha=snapshot_sha,
                    run_id=run_id,
                    output_dir=shards_dir,
                )
                fold_rows.append(result)
                print(
                    f"[nested] {model} fold={outer_fold}: "
                    f"test_RankIC={result['test']['rank_ic']} "
                    f"({result['seconds']:.1f}s)",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                fold_rows.append(
                    {
                        "model": model,
                        "outer_fold": outer_fold,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                print(f"[nested] {model} fold={outer_fold}: FAILED {exc}", flush=True)

    from koel.ml.distributed import load_prediction_artifact

    artifacts = [
        load_prediction_artifact(Path(row["artifact"]))
        for row in fold_rows
        if "artifact" in row
    ]
    report: dict[str, Any] = {"fold_rows": fold_rows}
    if artifacts:
        ensembled = ensemble_artifacts(artifacts, mode="calibration_select")
        contract = SuccessContract()
        report["nested_evaluation"] = evaluate_nested_ensemble(
            ensembled,
            contract=contract,
            ensemble_mode="calibration_select",
        )
        # Per-model pooled test RankIC
        per_model: dict[str, Any] = {}
        for model in models:
            model_arts = [a for a in artifacts if a.spec.model == model]
            if not model_arts:
                continue
            test_as_of: list[date] = []
            test_symbols: list[str] = []
            test_scores: list[float] = []
            test_y: list[float] = []
            test_dir: list[float] = []
            for art in model_arts:
                for prediction in art.predictions:
                    if prediction.partition != "test" or prediction.y_ret is None:
                        continue
                    test_as_of.append(prediction.as_of)
                    test_symbols.append(prediction.symbol)
                    test_scores.append(prediction.score)
                    test_y.append(prediction.y_ret)
                    test_dir.append(float(prediction.y_dir))
            rank_ic, sessions = mean_daily_rank_ic(test_as_of, test_scores, test_y)
            # Rebuild Sample-shaped rows for the cost helper.
            spread_rows = [
                Sample(
                    symbol=symbol,
                    as_of=as_of,
                    x=(0.0,),
                    y_ret=y_ret,
                    y_dir=y_dir,
                    horizon=horizon,
                )
                for symbol, as_of, y_ret, y_dir in zip(
                    test_symbols,
                    test_as_of,
                    test_y,
                    test_dir,
                    strict=True,
                )
            ]
            per_model[model] = {
                "rank_ic": rank_ic,
                "sessions": sessions,
                "n_rows": len(test_scores),
                "balanced_accuracy": balanced_direction_accuracy(test_dir, test_scores),
                "mcc": matthews_direction_correlation(test_dir, test_scores),
                "spread_112": _spread(spread_rows, test_scores, cost_bps=112.0),
                "spread_30": _spread(spread_rows, test_scores, cost_bps=30.0),
                "beats_baseline": (
                    rank_ic is not None and rank_ic > BASELINE_RANK_IC
                ),
            }
        report["per_model_pooled"] = per_model
    return report


def _lgb_screen_worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Module-level worker for ProcessPoolExecutor (must be picklable)."""
    train: list[Sample] = payload["train"]
    calibration: list[Sample] = payload["calibration"]
    config: dict[str, float | int] = payload["config"]
    seed: int = payload["seed"]
    # Fast screen estimators; winners are re-fit with full budget below.
    screen_config = {**config, "n_estimators": int(payload.get("n_estimators", 120))}
    started = time.perf_counter()
    try:
        scores = predict_lgb_tuned(train, calibration, seed=seed, **screen_config)
        metrics = _partition_metrics(calibration, scores)
        return {
            "config": config,
            "fingerprint": config_fingerprint(config),
            "calibration": metrics,
            "seconds": time.perf_counter() - started,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "config": config,
            "fingerprint": config_fingerprint(config),
            "calibration": {"rank_ic": None},
            "seconds": time.perf_counter() - started,
            "error": f"{type(exc).__name__}: {exc}",
        }


def phase_lgb_10k_screen(
    *,
    samples: list[Sample],
    metadata: dict,
    dates: list[date],
    horizon: int,
    target: str,
    evaluation_domain: str,
    max_flat_fraction: float,
    limit: int,
    workers: int,
    seed: int,
    top_k: int,
    output_dir: Path,
) -> dict[str, Any]:
    """Run up to ``limit`` LightGBM configs; rank by calibration RankIC only."""
    split = build_outer_split(
        dates,
        outer_fold=0,
        outer_folds=3,
        calibration_days=40,
        test_days=40,
        lockbox_days=60,
        embargo_days=max(5, horizon),
        min_train_days=250,
    )
    domain = None if evaluation_domain == "all" else evaluation_domain
    train = _rows_for_dates(
        samples,
        split.calibration_train_dates,
        metadata=metadata,
    )
    calibration = _rows_for_dates(
        samples,
        split.calibration_dates,
        metadata=metadata,
        domain=domain,
        max_flat_fraction=max_flat_fraction,
    )
    test = _rows_for_dates(
        samples,
        split.test_dates,
        metadata=metadata,
        domain=domain,
        max_flat_fraction=max_flat_fraction,
    )
    grid = lgb_hyperparam_grid(limit=limit)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"[10k] screening {len(grid)} LightGBM configs on calibration "
        f"(train={len(train)} cal={len(calibration)} test={len(test)}) "
        f"workers={workers}",
        flush=True,
    )
    payloads = [
        {
            "train": train,
            "calibration": calibration,
            "config": config,
            "seed": seed,
        }
        for config in grid
    ]
    rows: list[dict[str, Any]] = []
    # Prefer threads via env for LGBM; process pool for true parallelism of configs.
    # Large sample lists make process-pool pickling expensive — batch sequential
    # with high LGBM thread count when workers==1, else process pool on chunks.
    if workers <= 1:
        os.environ["ML_WORKER_THREADS"] = "4"
        for index, payload in enumerate(payloads, start=1):
            row = _lgb_screen_worker(payload)
            rows.append(row)
            if index % 25 == 0 or index == len(payloads):
                best = max(
                    (
                        r.get("calibration", {}).get("rank_ic")
                        for r in rows
                        if r.get("calibration", {}).get("rank_ic") is not None
                    ),
                    default=None,
                )
                print(
                    f"[10k] {index}/{len(payloads)} done; best_cal_RankIC={best}",
                    flush=True,
                )
    else:
        os.environ["ML_WORKER_THREADS"] = "1"
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_lgb_screen_worker, payload) for payload in payloads]
            for index, future in enumerate(as_completed(futures), start=1):
                rows.append(future.result())
                if index % 25 == 0 or index == len(payloads):
                    best = max(
                        (
                            r.get("calibration", {}).get("rank_ic")
                            for r in rows
                            if r.get("calibration", {}).get("rank_ic") is not None
                        ),
                        default=None,
                    )
                    print(
                        f"[10k] {index}/{len(payloads)} done; best_cal_RankIC={best}",
                        flush=True,
                    )

    rows.sort(
        key=lambda row: (
            row.get("calibration", {}).get("rank_ic") is None,
            -(row.get("calibration", {}).get("rank_ic") or -1.0),
        )
    )
    winners = [row for row in rows if row.get("calibration", {}).get("rank_ic") is not None][
        :top_k
    ]
    # One-shot test evaluation of winners (same protocol as worker).
    evaluated = []
    evaluation_rows = calibration + test
    for winner in winners:
        config = winner["config"]
        try:
            scores = predict_lgb_tuned(
                train,
                evaluation_rows,
                seed=seed,
                n_estimators=600,
                **config,
            )
            test_scores = scores[len(calibration) :]
            test_metrics = _partition_metrics(test, test_scores)
            evaluated.append(
                {
                    "fingerprint": winner["fingerprint"],
                    "config": config,
                    "calibration": winner["calibration"],
                    "test": test_metrics,
                    "beats_baseline": (
                        (test_metrics.get("rank_ic") or -1) > BASELINE_RANK_IC
                    ),
                }
            )
            print(
                f"[10k-winner] {winner['fingerprint']}: "
                f"cal={winner['calibration']['rank_ic']:.4f} "
                f"test={test_metrics['rank_ic']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            evaluated.append(
                {
                    "fingerprint": winner["fingerprint"],
                    "config": config,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    payload = {
        "screened": len(rows),
        "limit": limit,
        "top_k": top_k,
        "leaderboard_head": rows[:50],
        "winners_test": evaluated,
        "baseline_rank_ic": BASELINE_RANK_IC,
    }
    (output_dir / "lgb_10k_screen.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return payload


def run_exhaust(
    *,
    snapshot_dir: Path,
    output_dir: Path,
    target: str = "relative",
    horizon: int = 1,
    evaluation_domain: str = "cse",
    max_flat_fraction: float = 0.40,
    screen_top_k: int = 6,
    nested_folds: int = 3,
    nested_seeds: tuple[int, ...] = (0, 1, 2),
    hyper_limit: int = 10_000,
    hyper_top_k: int = 10,
    hyper_workers: int = 1,
    skip_hyper: bool = False,
    models: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"cpu-exhaust-{int(time.time())}"
    print(f"[exhaust] loading snapshot from {snapshot_dir}", flush=True)
    samples, metadata, dates, snapshot_sha = _prepare_samples(
        snapshot_dir, horizon=horizon, target=target
    )
    print(
        f"[exhaust] samples={len(samples)} dates={len(dates)} "
        f"sha={snapshot_sha[:16]}… target={target} h={horizon}",
        flush=True,
    )
    chosen_models = models or CPU_EXHAUST_MODELS
    unknown = sorted(set(chosen_models) - set(ALLOWED_MODELS))
    if unknown:
        raise ValueError(f"unsupported models: {', '.join(unknown)}")

    screen = phase_family_screen(
        samples=samples,
        metadata=metadata,
        dates=dates,
        models=chosen_models,
        horizon=horizon,
        target=target,
        snapshot_sha=snapshot_sha,
        run_id=run_id,
        output_dir=output_dir,
        evaluation_domain=evaluation_domain,
        max_flat_fraction=max_flat_fraction,
        workers=4,
    )
    (output_dir / "phase_family_screen.json").write_text(
        json.dumps(screen, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    survivors = [
        row["model"]
        for row in screen
        if row.get("calibration", {}).get("rank_ic") is not None
    ][:screen_top_k]
    # Always keep the known champion in the deep set.
    if "double_ensemble_native" not in survivors:
        survivors.append("double_ensemble_native")
    print(f"[exhaust] deep survivors: {survivors}", flush=True)

    nested = phase_nested_deep(
        samples=samples,
        metadata=metadata,
        dates=dates,
        models=tuple(survivors),
        horizon=horizon,
        target=target,
        snapshot_sha=snapshot_sha,
        run_id=run_id,
        output_dir=output_dir,
        evaluation_domain=evaluation_domain,
        max_flat_fraction=max_flat_fraction,
        outer_folds=nested_folds,
        seeds=nested_seeds,
    )
    (output_dir / "phase_nested_deep.json").write_text(
        json.dumps(nested, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    hyper: dict[str, Any] | None = None
    if not skip_hyper:
        hyper = phase_lgb_10k_screen(
            samples=samples,
            metadata=metadata,
            dates=dates,
            horizon=horizon,
            target=target,
            evaluation_domain=evaluation_domain,
            max_flat_fraction=max_flat_fraction,
            limit=hyper_limit,
            workers=hyper_workers,
            seed=0,
            top_k=hyper_top_k,
            output_dir=output_dir / "hyper",
        )

    summary = {
        "run_id": run_id,
        "snapshot_sha": snapshot_sha,
        "target": target,
        "horizon": horizon,
        "evaluation_domain": evaluation_domain,
        "baseline_rank_ic": BASELINE_RANK_IC,
        "screen_top": [
            {
                "model": row.get("model"),
                "cal_rank_ic": row.get("calibration", {}).get("rank_ic"),
                "test_rank_ic": row.get("test", {}).get("rank_ic"),
                "error": row.get("error"),
            }
            for row in screen[:15]
        ],
        "nested_per_model": nested.get("per_model_pooled"),
        "nested_contract_met": (
            nested.get("nested_evaluation", {}).get("contract_met")
            if nested.get("nested_evaluation")
            else None
        ),
        "hyper_best_test": (hyper or {}).get("winners_test", [None])[:3],
        "any_beats_baseline": any(
            (row or {}).get("beats_baseline")
            for row in (nested.get("per_model_pooled") or {}).values()
        )
        or any(
            (row or {}).get("beats_baseline")
            for row in (hyper or {}).get("winners_test", [])
        ),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    _write_markdown(summary, output_dir / "summary.md")
    print(json.dumps(summary, indent=2, default=str), flush=True)
    return summary


def _write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# CPU exhaust summary",
        "",
        f"- run_id: `{summary['run_id']}`",
        f"- snapshot: `{summary['snapshot_sha']}`",
        (
            f"- target/horizon/domain: `{summary['target']}` / "
            f"h{summary['horizon']} / `{summary['evaluation_domain']}`"
        ),
        f"- baseline RankIC (DoubleEnsemble): {summary['baseline_rank_ic']}",
        f"- any_beats_baseline: **{summary['any_beats_baseline']}**",
        f"- nested contract_met: `{summary.get('nested_contract_met')}`",
        "",
        "## Family screen (fold 0)",
        "",
        "| model | cal RankIC | test RankIC | error |",
        "|---|---:|---:|---|",
    ]
    for row in summary.get("screen_top") or []:
        lines.append(
            f"| {row.get('model')} | {row.get('cal_rank_ic')} | "
            f"{row.get('test_rank_ic')} | {row.get('error') or ''} |"
        )
    lines.extend(["", "## Nested pooled (survivors)", ""])
    per = summary.get("nested_per_model") or {}
    if per:
        lines.append(
            "| model | RankIC | BA | MCC | spread@112 | beats baseline |"
        )
        lines.append("|---|---:|---:|---:|---:|---|")
        for model, metrics in sorted(
            per.items(),
            key=lambda item: -(item[1].get("rank_ic") or -1),
        ):
            lines.append(
                f"| {model} | {metrics.get('rank_ic')} | "
                f"{metrics.get('balanced_accuracy')} | {metrics.get('mcc')} | "
                f"{metrics.get('spread_112')} | {metrics.get('beats_baseline')} |"
            )
    else:
        lines.append("_no nested results_")
    lines.extend(["", "## 10k LightGBM winners (test once)", ""])
    winners = summary.get("hyper_best_test") or []
    if winners:
        for winner in winners:
            if not winner:
                continue
            cal = winner.get("calibration", {}).get("rank_ic")
            test = winner.get("test", {}).get("rank_ic")
            lines.append(
                f"- `{winner.get('fingerprint')}` cal={cal} test={test} "
                f"beats={winner.get('beats_baseline')} "
                f"config=`{winner.get('config')}`"
            )
    else:
        lines.append("_hyper screen skipped or empty_")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", choices=("absolute", "relative"), default="relative")
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--evaluation-domain", default="cse")
    parser.add_argument("--max-flat-fraction", type=float, default=0.40)
    parser.add_argument("--screen-top-k", type=int, default=6)
    parser.add_argument("--nested-folds", type=int, default=3)
    parser.add_argument("--nested-seeds", default="0,1,2")
    parser.add_argument("--hyper-limit", type=int, default=10_000)
    parser.add_argument("--hyper-top-k", type=int, default=10)
    parser.add_argument("--hyper-workers", type=int, default=1)
    parser.add_argument("--skip-hyper", action="store_true")
    parser.add_argument(
        "--models",
        default="",
        help="Optional comma-separated subset; default = full CPU_EXHAUST_MODELS",
    )
    args = parser.parse_args(argv)
    models = (
        tuple(part.strip() for part in args.models.split(",") if part.strip())
        or None
    )
    seeds = tuple(
        int(part.strip()) for part in args.nested_seeds.split(",") if part.strip()
    )
    run_exhaust(
        snapshot_dir=args.snapshot,
        output_dir=args.output,
        target=args.target,
        horizon=args.horizon,
        evaluation_domain=args.evaluation_domain,
        max_flat_fraction=args.max_flat_fraction,
        screen_top_k=args.screen_top_k,
        nested_folds=args.nested_folds,
        nested_seeds=seeds,
        hyper_limit=args.hyper_limit,
        hyper_top_k=args.hyper_top_k,
        hyper_workers=args.hyper_workers,
        skip_hyper=args.skip_hyper,
        models=models,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
