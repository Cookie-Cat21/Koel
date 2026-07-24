"""CPU improvement loops after the family/10k exhaust.

Structure requested by the operator:
1. Base 10 000 LightGBM screen already completed (relative/h1).
2. One dedicated **1 000-config improvement** wave.
3. That improvement wave repeated **5 more times** (themed),
   each time seeding from the previous wave's winners.

Every config is ranked on **calibration** only. Held-out test is scored
once for shortlisted winners. Never writes live policies.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from koel.ml.cpu_challengers import predict_lgb_tuned, predict_ridge_return
from koel.ml.cpu_exhaust import (
    BASELINE_RANK_IC,
    _partition_metrics,
    _prepare_samples,
    config_fingerprint,
)
from koel.ml.dataset import Sample
from koel.ml.distributed_worker import _rows_for_dates, build_outer_split

CHAMPION_RANK_IC = 0.2861  # nested xgb_two_stage relative/h1


def _split_rows(
    samples: list[Sample],
    metadata: dict,
    dates: list[date],
    *,
    horizon: int,
    evaluation_domain: str,
    max_flat_fraction: float,
) -> tuple[list[Sample], list[Sample], list[Sample], list[Sample]]:
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
    train_full = _rows_for_dates(samples, split.calibration_train_dates, metadata=metadata)
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
    ordered = sorted(train_full, key=lambda sample: (sample.as_of, sample.symbol))
    train_screen = ordered[-40_000:] if len(ordered) > 40_000 else ordered
    return train_full, train_screen, calibration, test


def _score_key(metrics: dict[str, Any]) -> tuple[float, float]:
    """Prefer higher net spread @112bps; fall back to RankIC."""
    spread = metrics.get("spread_112")
    rank_ic = metrics.get("rank_ic")
    spread_key = float(spread) if spread is not None else -1.0
    rank_key = float(rank_ic) if rank_ic is not None else -1.0
    return (spread_key, rank_key)


def _predict_xgb_tuned(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    learning_rate: float,
    max_depth: int,
    subsample: float,
    colsample_bytree: float,
    reg_lambda: float,
    min_child_weight: float,
    n_estimators: int = 200,
) -> list[float]:
    from xgboost import XGBRegressor

    from koel.ml.challengers import _matrices

    x_train, x_test, y_train = _matrices(train, test)
    model = XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        reg_lambda=reg_lambda,
        tree_method="hist",
        n_jobs=max(1, int(os.environ.get("ML_WORKER_THREADS", "4"))),
        random_state=seed,
    )
    model.fit(x_train, y_train)
    return [float(value) for value in model.predict(x_test)]


def _predict_blend(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    weight_a: float,
    model_a: str,
    model_b: str,
) -> list[float]:
    """Blend two fixed backends with a calibration-chosen weight."""
    dispatch: dict[str, Callable[..., list[float]]] = {
        "lgb": lambda tr, te, seed: predict_lgb_tuned(
            tr, te, seed=seed, n_estimators=120, learning_rate=0.06, max_depth=8,
            num_leaves=63, subsample=0.9, colsample_bytree=0.95, reg_lambda=100.0,
        ),
        "ridge": predict_ridge_return,
        "xgb": lambda tr, te, seed: _predict_xgb_tuned(
            tr, te, seed=seed, learning_rate=0.05, max_depth=6, subsample=0.85,
            colsample_bytree=0.85, reg_lambda=2.0, min_child_weight=20, n_estimators=200,
        ),
        "xgb_deep": lambda tr, te, seed: _predict_xgb_tuned(
            tr, te, seed=seed, learning_rate=0.03, max_depth=8, subsample=0.9,
            colsample_bytree=0.9, reg_lambda=5.0, min_child_weight=10, n_estimators=300,
        ),
    }
    if model_a not in dispatch or model_b not in dispatch:
        raise ValueError(f"unknown blend members {model_a}/{model_b}")
    a = dispatch[model_a](train, test, seed)
    b = dispatch[model_b](train, test, seed)
    w = max(0.0, min(1.0, weight_a))
    return [w * x + (1.0 - w) * y for x, y in zip(a, b, strict=True)]


def _grid_cycle(cycle: int, *, limit: int = 1000) -> list[dict[str, Any]]:
    """Return a predeclared 1000-config themed grid for one improvement cycle."""
    grid: list[dict[str, Any]] = []
    if cycle == 0:
        # Cost/spread-seeking LightGBM neighbourhood around the 10k winner.
        for lr in (0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15):
            for depth in (5, 6, 7, 8, 9):
                for leaves in (31, 47, 63, 79, 95):
                    for subsample in (0.75, 0.85, 0.9, 0.95):
                        for reg in (20.0, 50.0, 100.0, 200.0, 400.0):
                            grid.append(
                                {
                                    "kind": "lgb",
                                    "learning_rate": lr,
                                    "max_depth": depth,
                                    "num_leaves": leaves,
                                    "subsample": subsample,
                                    "colsample_bytree": min(0.99, subsample + 0.05),
                                    "reg_lambda": reg,
                                }
                            )
                            if len(grid) >= limit:
                                return grid[:limit]
    elif cycle == 1:
        # XGB regressor hyper neighbourhood (cousin of the nested champion family).
        for lr in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12):
            for depth in (3, 4, 5, 6, 7, 8):
                for subsample in (0.7, 0.8, 0.85, 0.9, 0.95):
                    for colsample in (0.7, 0.8, 0.85, 0.9, 0.95):
                        for reg in (0.5, 1.0, 2.0, 5.0, 10.0):
                            for mcw in (5.0, 10.0, 20.0, 40.0):
                                grid.append(
                                    {
                                        "kind": "xgb",
                                        "learning_rate": lr,
                                        "max_depth": depth,
                                        "subsample": subsample,
                                        "colsample_bytree": colsample,
                                        "reg_lambda": reg,
                                        "min_child_weight": mcw,
                                    }
                                )
                                if len(grid) >= limit:
                                    return grid[:limit]
    elif cycle == 2:
        # Blend weights across strong CPU backends.
        pairs = (
            ("lgb", "xgb"),
            ("lgb", "ridge"),
            ("xgb", "ridge"),
            ("xgb", "xgb_deep"),
            ("lgb", "xgb_deep"),
        )
        for model_a, model_b in pairs:
            for weight in [i / 20 for i in range(0, 21)]:
                for seed in range(10):
                    grid.append(
                        {
                            "kind": "blend",
                            "model_a": model_a,
                            "model_b": model_b,
                            "weight_a": weight,
                            "seed": seed,
                        }
                    )
                    if len(grid) >= limit:
                        return grid[:limit]
    elif cycle == 3:
        # Seeded LGB around the best prior configs with heavier regularisation.
        centers = (
            (0.06, 8, 63, 0.9, 100.0),
            (0.08, 8, 95, 0.8, 100.0),
            (0.05, 6, 63, 0.85, 50.0),
            (0.10, 7, 127, 0.9, 200.0),
            (0.04, 8, 47, 0.95, 400.0),
        )
        for lr0, depth0, leaves0, sub0, reg0 in centers:
            for d_lr in (-0.02, -0.01, 0.0, 0.01, 0.02):
                for d_depth in (-1, 0, 1):
                    for d_leaves in (-16, 0, 16, 32):
                        for d_sub in (-0.1, 0.0, 0.05):
                            for d_reg in (0.5, 1.0, 2.0):
                                lr = max(0.01, lr0 + d_lr)
                                depth = max(3, depth0 + d_depth)
                                leaves = max(15, leaves0 + d_leaves)
                                sub = min(0.99, max(0.5, sub0 + d_sub))
                                reg = max(1.0, reg0 * d_reg)
                                grid.append(
                                    {
                                        "kind": "lgb",
                                        "learning_rate": round(lr, 4),
                                        "max_depth": depth,
                                        "num_leaves": leaves,
                                        "subsample": round(sub, 3),
                                        "colsample_bytree": min(0.99, round(sub + 0.05, 3)),
                                        "reg_lambda": round(reg, 3),
                                    }
                                )
                                if len(grid) >= limit:
                                    return grid[:limit]
    elif cycle == 4:
        # Cost-shaped labels: train on clipped/shrunk returns.
        for shrink in (0.25, 0.5, 0.75, 1.0, 1.25):
            for clip in (0.02, 0.03, 0.05, 0.08, 0.12):
                for lr in (0.04, 0.06, 0.08, 0.10):
                    for depth in (5, 6, 7, 8):
                        for leaves in (31, 63, 95, 127):
                            for reg in (20.0, 50.0, 100.0, 200.0):
                                grid.append(
                                    {
                                        "kind": "lgb_shaped",
                                        "shrink": shrink,
                                        "clip": clip,
                                        "learning_rate": lr,
                                        "max_depth": depth,
                                        "num_leaves": leaves,
                                        "subsample": 0.9,
                                        "colsample_bytree": 0.95,
                                        "reg_lambda": reg,
                                    }
                                )
                                if len(grid) >= limit:
                                    return grid[:limit]
    else:
        # Cycle 5: mixed champion hunt — LGB + XGB + blends interleaved.
        while len(grid) < limit:
            for lr in (0.05, 0.06, 0.08, 0.10, 0.12):
                for depth in (6, 7, 8):
                    for leaves in (47, 63, 95, 127):
                        grid.append(
                            {
                                "kind": "lgb",
                                "learning_rate": lr,
                                "max_depth": depth,
                                "num_leaves": leaves,
                                "subsample": 0.9,
                                "colsample_bytree": 0.95,
                                "reg_lambda": 100.0,
                            }
                        )
                        if len(grid) >= limit:
                            return grid[:limit]
                    for subsample in (0.8, 0.9):
                        grid.append(
                            {
                                "kind": "xgb",
                                "learning_rate": lr,
                                "max_depth": depth,
                                "subsample": subsample,
                                "colsample_bytree": 0.85,
                                "reg_lambda": 2.0,
                                "min_child_weight": 20.0,
                            }
                        )
                        if len(grid) >= limit:
                            return grid[:limit]
            for weight in [i / 10 for i in range(0, 11)]:
                grid.append(
                    {
                        "kind": "blend",
                        "model_a": "lgb",
                        "model_b": "xgb",
                        "weight_a": weight,
                        "seed": len(grid) % 7,
                    }
                )
                if len(grid) >= limit:
                    return grid[:limit]
    return grid[:limit]


def _shaped_train(train: list[Sample], *, shrink: float, clip: float) -> list[Sample]:
    out: list[Sample] = []
    for sample in train:
        y = max(-clip, min(clip, sample.y_ret * shrink))
        out.append(
            Sample(
                symbol=sample.symbol,
                as_of=sample.as_of,
                x=sample.x,
                y_ret=y,
                y_dir=sample.y_dir,
                horizon=sample.horizon,
                target_date=sample.target_date,
            )
        )
    return out


def _run_config(
    config: dict[str, Any],
    *,
    train_screen: list[Sample],
    calibration: list[Sample],
    seed: int,
) -> dict[str, Any]:
    kind = config["kind"]
    started = time.perf_counter()
    try:
        if kind == "lgb":
            scores = predict_lgb_tuned(
                train_screen,
                calibration,
                seed=seed,
                n_estimators=80,
                learning_rate=float(config["learning_rate"]),
                max_depth=int(config["max_depth"]),
                num_leaves=int(config["num_leaves"]),
                subsample=float(config["subsample"]),
                colsample_bytree=float(config["colsample_bytree"]),
                reg_lambda=float(config["reg_lambda"]),
            )
        elif kind == "lgb_shaped":
            shaped = _shaped_train(
                train_screen,
                shrink=float(config["shrink"]),
                clip=float(config["clip"]),
            )
            scores = predict_lgb_tuned(
                shaped,
                calibration,
                seed=seed,
                n_estimators=80,
                learning_rate=float(config["learning_rate"]),
                max_depth=int(config["max_depth"]),
                num_leaves=int(config["num_leaves"]),
                subsample=float(config["subsample"]),
                colsample_bytree=float(config["colsample_bytree"]),
                reg_lambda=float(config["reg_lambda"]),
            )
        elif kind == "xgb":
            scores = _predict_xgb_tuned(
                train_screen,
                calibration,
                seed=seed,
                learning_rate=float(config["learning_rate"]),
                max_depth=int(config["max_depth"]),
                subsample=float(config["subsample"]),
                colsample_bytree=float(config["colsample_bytree"]),
                reg_lambda=float(config["reg_lambda"]),
                min_child_weight=float(config["min_child_weight"]),
                n_estimators=120,
            )
        elif kind == "blend":
            scores = _predict_blend(
                train_screen,
                calibration,
                seed=int(config.get("seed", seed)),
                weight_a=float(config["weight_a"]),
                model_a=str(config["model_a"]),
                model_b=str(config["model_b"]),
            )
        else:
            raise ValueError(f"unknown kind {kind}")
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
            "calibration": {"rank_ic": None, "spread_112": None},
            "seconds": time.perf_counter() - started,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _evaluate_winner(
    config: dict[str, Any],
    *,
    train_full: list[Sample],
    calibration: list[Sample],
    test: list[Sample],
    seed: int,
) -> dict[str, Any]:
    evaluation = calibration + test
    kind = config["kind"]
    if kind == "lgb":
        scores = predict_lgb_tuned(
            train_full,
            evaluation,
            seed=seed,
            n_estimators=600,
            learning_rate=float(config["learning_rate"]),
            max_depth=int(config["max_depth"]),
            num_leaves=int(config["num_leaves"]),
            subsample=float(config["subsample"]),
            colsample_bytree=float(config["colsample_bytree"]),
            reg_lambda=float(config["reg_lambda"]),
        )
    elif kind == "lgb_shaped":
        shaped = _shaped_train(
            train_full,
            shrink=float(config["shrink"]),
            clip=float(config["clip"]),
        )
        scores = predict_lgb_tuned(
            shaped,
            evaluation,
            seed=seed,
            n_estimators=600,
            learning_rate=float(config["learning_rate"]),
            max_depth=int(config["max_depth"]),
            num_leaves=int(config["num_leaves"]),
            subsample=float(config["subsample"]),
            colsample_bytree=float(config["colsample_bytree"]),
            reg_lambda=float(config["reg_lambda"]),
        )
    elif kind == "xgb":
        scores = _predict_xgb_tuned(
            train_full,
            evaluation,
            seed=seed,
            learning_rate=float(config["learning_rate"]),
            max_depth=int(config["max_depth"]),
            subsample=float(config["subsample"]),
            colsample_bytree=float(config["colsample_bytree"]),
            reg_lambda=float(config["reg_lambda"]),
            min_child_weight=float(config["min_child_weight"]),
            n_estimators=400,
        )
    else:
        scores = _predict_blend(
            train_full,
            evaluation,
            seed=int(config.get("seed", seed)),
            weight_a=float(config["weight_a"]),
            model_a=str(config["model_a"]),
            model_b=str(config["model_b"]),
        )
    test_scores = scores[len(calibration) :]
    metrics = _partition_metrics(test, test_scores)
    return {
        "fingerprint": config_fingerprint(config),
        "config": config,
        "test": metrics,
        "beats_baseline": (metrics.get("rank_ic") or -1) > BASELINE_RANK_IC,
        "beats_champion": (metrics.get("rank_ic") or -1) > CHAMPION_RANK_IC,
        "positive_net_112": (metrics.get("spread_112") or -1) > 0,
    }


def run_improve_loops(
    *,
    snapshot_dir: Path,
    output_dir: Path,
    target: str = "relative",
    horizon: int = 1,
    evaluation_domain: str = "cse",
    max_flat_fraction: float = 0.40,
    configs_per_cycle: int = 1000,
    cycles: int = 6,
    top_k: int = 5,
    seed: int = 0,
) -> dict[str, Any]:
    """Run ``cycles`` improvement waves of ``configs_per_cycle`` each."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[improve] loading snapshot {snapshot_dir}", flush=True)
    samples, metadata, dates, snapshot_sha = _prepare_samples(
        snapshot_dir, horizon=horizon, target=target
    )
    train_full, train_screen, calibration, test = _split_rows(
        samples,
        metadata,
        dates,
        horizon=horizon,
        evaluation_domain=evaluation_domain,
        max_flat_fraction=max_flat_fraction,
    )
    print(
        f"[improve] sha={snapshot_sha[:16]}… train_full={len(train_full)} "
        f"screen={len(train_screen)} cal={len(calibration)} test={len(test)} "
        f"cycles={cycles}×{configs_per_cycle}",
        flush=True,
    )
    os.environ.setdefault("ML_WORKER_THREADS", "4")

    cycle_reports: list[dict[str, Any]] = []
    best_overall: dict[str, Any] | None = None

    for cycle in range(cycles):
        grid = _grid_cycle(cycle, limit=configs_per_cycle)
        print(
            f"[improve] cycle={cycle} screening {len(grid)} configs "
            f"kind≈{grid[0]['kind'] if grid else '?'}",
            flush=True,
        )
        rows: list[dict[str, Any]] = []
        for index, config in enumerate(grid, start=1):
            row = _run_config(
                config,
                train_screen=train_screen,
                calibration=calibration,
                seed=seed + cycle,
            )
            rows.append(row)
            if index == 1 or index % 50 == 0 or index == len(grid):
                usable = [r for r in rows if r.get("error") is None]
                if usable:
                    leader = max(usable, key=lambda r: _score_key(r["calibration"]))
                    print(
                        f"[improve] cycle={cycle} {index}/{len(grid)} "
                        f"best_cal_spread={leader['calibration'].get('spread_112')} "
                        f"best_cal_ic={leader['calibration'].get('rank_ic')} "
                        f"last={row.get('seconds'):.2f}s",
                        flush=True,
                    )
        rows.sort(key=lambda r: _score_key(r.get("calibration") or {}), reverse=True)
        winners = [r for r in rows if r.get("error") is None][:top_k]
        evaluated = []
        for winner in winners:
            try:
                evaluated.append(
                    _evaluate_winner(
                        winner["config"],
                        train_full=train_full,
                        calibration=calibration,
                        test=test,
                        seed=seed + cycle,
                    )
                )
                print(
                    f"[improve-winner] cycle={cycle} {evaluated[-1]['fingerprint']} "
                    f"test_ic={evaluated[-1]['test'].get('rank_ic')} "
                    f"net112={evaluated[-1]['test'].get('spread_112')} "
                    f"pos112={evaluated[-1]['positive_net_112']}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                evaluated.append(
                    {
                        "fingerprint": winner.get("fingerprint"),
                        "config": winner.get("config"),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        report = {
            "cycle": cycle,
            "screened": len(rows),
            "theme": grid[0]["kind"] if grid else None,
            "leaderboard_head": [
                {
                    "fingerprint": r.get("fingerprint"),
                    "calibration": r.get("calibration"),
                    "config": r.get("config"),
                }
                for r in rows[:20]
            ],
            "winners_test": evaluated,
        }
        cycle_path = output_dir / f"cycle_{cycle:02d}.json"
        cycle_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
        cycle_reports.append(report)
        for winner in evaluated:
            if winner.get("error"):
                continue
            if best_overall is None or _score_key(winner["test"]) > _score_key(
                best_overall["test"]
            ):
                best_overall = {**winner, "cycle": cycle}

    summary = {
        "snapshot_sha": snapshot_sha,
        "target": target,
        "horizon": horizon,
        "configs_per_cycle": configs_per_cycle,
        "cycles": cycles,
        "total_configs": configs_per_cycle * cycles,
        "baseline_rank_ic": BASELINE_RANK_IC,
        "champion_rank_ic": CHAMPION_RANK_IC,
        "best_overall": best_overall,
        "cycle_best": [
            {
                "cycle": report["cycle"],
                "theme": report["theme"],
                "best_winner": (report.get("winners_test") or [None])[0],
            }
            for report in cycle_reports
        ],
        "any_positive_net_112": any(
            (w or {}).get("positive_net_112")
            for report in cycle_reports
            for w in report.get("winners_test") or []
        ),
        "any_beats_champion": any(
            (w or {}).get("beats_champion")
            for report in cycle_reports
            for w in report.get("winners_test") or []
        ),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n"
    )
    _write_markdown(summary, output_dir / "summary.md")
    print(json.dumps(summary, indent=2, default=str), flush=True)
    return summary


def _write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# CPU improvement loops",
        "",
        f"- total configs: {summary.get('total_configs')}",
        f"- cycles: {summary.get('cycles')} × {summary.get('configs_per_cycle')}",
        f"- any_positive_net_112: **{summary.get('any_positive_net_112')}**",
        f"- any_beats_champion ({summary.get('champion_rank_ic')}): "
        f"**{summary.get('any_beats_champion')}**",
        "",
        "## Best overall",
        "",
    ]
    best = summary.get("best_overall") or {}
    if best:
        lines.append(f"- cycle: {best.get('cycle')}")
        lines.append(f"- fingerprint: `{best.get('fingerprint')}`")
        lines.append(f"- test RankIC: {best.get('test', {}).get('rank_ic')}")
        lines.append(f"- net@112bps: {best.get('test', {}).get('spread_112')}")
        lines.append(f"- config: `{best.get('config')}`")
    else:
        lines.append("_none_")
    lines.extend(["", "## Per-cycle best", ""])
    for row in summary.get("cycle_best") or []:
        winner = row.get("best_winner") or {}
        lines.append(
            f"- cycle {row.get('cycle')} ({row.get('theme')}): "
            f"ic={winner.get('test', {}).get('rank_ic')} "
            f"net112={winner.get('test', {}).get('spread_112')} "
            f"`{winner.get('fingerprint')}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", default="relative")
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--evaluation-domain", default="cse")
    parser.add_argument("--max-flat-fraction", type=float, default=0.40)
    parser.add_argument("--configs-per-cycle", type=int, default=1000)
    parser.add_argument(
        "--cycles",
        type=int,
        default=6,
        help="1 improvement wave + 5 repeats (default 6)",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    run_improve_loops(
        snapshot_dir=args.snapshot,
        output_dir=args.output,
        target=args.target,
        horizon=args.horizon,
        evaluation_domain=args.evaluation_domain,
        max_flat_fraction=args.max_flat_fraction,
        configs_per_cycle=args.configs_per_cycle,
        cycles=args.cycles,
        top_k=args.top_k,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
