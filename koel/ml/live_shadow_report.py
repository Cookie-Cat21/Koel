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
from koel.storage import Storage


@dataclass(frozen=True, slots=True)
class ShadowModelMetrics:
    model_version: str
    rows: int
    scored: int
    correct: int
    precision: float | None
    precision_lcb: float | None
    symbols: int
    sessions: int
    max_symbol_share: float
    max_session_share: float
    contract_met: bool


def summarize_shadow_rows(rows: list[dict[str, Any]]) -> list[ShadowModelMetrics]:
    """Summarize non-partial prospective rows by immutable model version."""
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        gate = str(row.get("gate") or "")
        if "partial" in gate:
            continue
        by_model[str(row["model_version"])].append(row)

    out: list[ShadowModelMetrics] = []
    for model_version, model_rows in sorted(by_model.items()):
        scored = [
            row
            for row in model_rows
            if bool(row.get("scored")) and isinstance(row.get("hit"), bool)
        ]
        correct = sum(1 for row in scored if row["hit"])
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
        contract_met = (
            precision is not None
            and precision >= 0.90
            and lcb is not None
            and lcb >= 0.90
            and len(scored) >= 500
            and len(symbol_counts) >= 80
            and len(session_counts) >= 60
            and max_symbol_share <= 0.05
            and max_session_share <= 0.05
        )
        out.append(
            ShadowModelMetrics(
                model_version=model_version,
                rows=len(model_rows),
                scored=len(scored),
                correct=correct,
                precision=precision,
                precision_lcb=lcb,
                symbols=len(symbol_counts),
                sessions=len(session_counts),
                max_symbol_share=max_symbol_share,
                max_session_share=max_session_share,
                contract_met=contract_met,
            )
        )
    return out


async def build_live_shadow_report(storage: Storage) -> list[ShadowModelMetrics]:
    async with storage._pool.connection() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT model_version, symbol, issued_at, gate, scored, hit
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
