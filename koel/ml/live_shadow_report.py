"""Standards report for prospective live shadow outcomes."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from koel.ml.distributed import wilson_lower_bound
from koel.ml.metrics import (
    balanced_direction_accuracy,
    brier_score,
    cost_adjusted_top_bottom_spread,
    expected_calibration_error,
    matthews_direction_correlation,
    mean_daily_rank_ic,
)
from koel.storage import Storage


@dataclass(frozen=True, slots=True)
class ShadowModelMetrics:
    policy_id: str
    instances: int
    latest_model_version: str
    rows: int
    scored: int
    correct: int
    precision: float | None
    precision_lcb: float | None
    coverage: float | None
    symbols: int
    sessions: int
    max_symbol_share: float
    max_session_share: float
    rank_ic: float | None
    rank_ic_sessions: int
    balanced_accuracy: float | None
    mcc: float | None
    brier: float | None
    ece: float | None
    post_cost_mean_return: float | None
    post_cost_sessions: int
    contract_met: bool


def summarize_shadow_rows(rows: list[dict[str, Any]]) -> list[ShadowModelMetrics]:
    """Summarize rolling immutable instances by fixed algorithm policy."""
    by_policy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        gate = str(row.get("gate") or "")
        if "partial" in gate:
            continue
        by_policy[str(row["model_id"])].append(row)

    out: list[ShadowModelMetrics] = []
    rows_per_policy_session = Counter(
        (str(row["model_id"]), row.get("issued_at"))
        for row in rows
        if "partial" not in str(row.get("gate") or "")
    )
    eligible_by_session: dict[object, int] = {}
    for (_policy_id, session), count in rows_per_policy_session.items():
        eligible_by_session[session] = max(
            eligible_by_session.get(session, 0),
            count,
        )
    for policy_id, model_rows in sorted(by_policy.items()):
        scored = [row for row in model_rows if bool(row.get("scored"))]
        correct = sum(1 for row in scored if row.get("hit") is True)
        precision = correct / len(scored) if scored else None
        lcb = wilson_lower_bound(correct, len(scored)) if scored else None
        symbol_counts = Counter(str(row["symbol"]) for row in scored)
        session_counts = Counter(
            row["issued_at"]
            for row in scored
            if isinstance(row.get("issued_at"), date)
        )
        max_symbol_share = (
            max(symbol_counts.values(), default=0) / len(scored) if scored else 0.0
        )
        max_session_share = (
            max(session_counts.values(), default=0) / len(scored) if scored else 0.0
        )
        metric_rows = [
            row
            for row in scored
            if isinstance(row.get("y_pred"), int | float)
            and isinstance(row.get("y_real"), int | float)
        ]
        sessions_metric = [row["issued_at"] for row in metric_rows]
        predictions = [float(row["y_pred"]) for row in metric_rows]
        realized = [float(row["y_real"]) for row in metric_rows]
        directions = [
            1.0 if value > 0 else -1.0 if value < 0 else 0.0
            for value in realized
        ]
        rank_ic, rank_ic_sessions = mean_daily_rank_ic(
            sessions_metric,
            predictions,
            realized,
            min_names=20,
        ) if metric_rows else (None, 0)
        balanced_accuracy = (
            balanced_direction_accuracy(directions, predictions)
            if metric_rows
            else None
        )
        mcc = (
            matthews_direction_correlation(directions, predictions)
            if metric_rows
            else None
        )
        probability_rows = [
            row
            for row in scored
            if isinstance(row.get("confidence"), int | float)
            and 0 <= float(row["confidence"]) <= 1
        ]
        correctness = [row.get("hit") is True for row in probability_rows]
        correctness_probability = [
            0.5 + 0.5 * float(row["confidence"]) for row in probability_rows
        ]
        brier = brier_score(correctness, correctness_probability)
        ece = expected_calibration_error(correctness, correctness_probability)
        spread = (
            cost_adjusted_top_bottom_spread(
                sessions_metric,
                [str(row["symbol"]) for row in metric_rows],
                predictions,
                realized,
                fraction=0.10,
                cost_bps=112.0,
                min_names=20,
            )
            if metric_rows
            else None
        )
        policy_sessions = {row.get("issued_at") for row in model_rows}
        eligible = sum(eligible_by_session.get(session, 0) for session in policy_sessions)
        coverage = len(model_rows) / eligible if eligible > 0 else None
        contract_met = (
            precision is not None
            and precision >= 0.90
            and lcb is not None
            and lcb >= 0.90
            and len(scored) >= 500
            and len(symbol_counts) >= 80
            and len(session_counts) >= 60
            and coverage is not None
            and coverage >= 0.01
            and max_symbol_share <= 0.05
            and max_session_share <= 0.05
        )
        out.append(
            ShadowModelMetrics(
                policy_id=policy_id,
                instances=len(
                    {str(row["model_version"]) for row in model_rows}
                ),
                latest_model_version=max(
                    str(row["model_version"]) for row in model_rows
                ),
                rows=len(model_rows),
                scored=len(scored),
                correct=correct,
                precision=precision,
                precision_lcb=lcb,
                coverage=coverage,
                symbols=len(symbol_counts),
                sessions=len(session_counts),
                max_symbol_share=max_symbol_share,
                max_session_share=max_session_share,
                rank_ic=rank_ic,
                rank_ic_sessions=rank_ic_sessions,
                balanced_accuracy=balanced_accuracy,
                mcc=mcc,
                brier=brier,
                ece=ece,
                post_cost_mean_return=(
                    spread.mean_net_return if spread is not None else None
                ),
                post_cost_sessions=spread.sessions if spread is not None else 0,
                contract_met=contract_met,
            )
        )
    return out


async def build_live_shadow_report(storage: Storage) -> list[ShadowModelMetrics]:
    async with storage._pool.connection() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT model_id, model_version, symbol, issued_at, gate,
                       scored, hit, y_pred, y_real, confidence
                FROM forecast_outcomes
                WHERE gate LIKE 'shadow_%'
                ORDER BY model_version, issued_at, symbol
                """
            )
        ).fetchall()
    return summarize_shadow_rows([dict(row) for row in rows])


async def _run() -> None:
    database_url = os.environ.get("ML_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("ML_DATABASE_URL (or DATABASE_URL) is required")
    storage = Storage(database_url)
    await storage.open()
    try:
        report = await build_live_shadow_report(storage)
    finally:
        await storage.close()
    print(json.dumps([asdict(item) for item in report], indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Report prospective shadow standards")
    parser.parse_args(argv)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
