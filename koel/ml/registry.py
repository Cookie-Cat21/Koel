"""Model registry: champion / challenger lifecycle."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)

ARTIFACT_DIR = Path("data/ml_artifacts")
REGISTRY_MD = Path("docs/experiments/MODEL_REGISTRY.md")


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    model_id: str
    algo: str
    status: str
    horizons: tuple[int, ...]
    feature_list: tuple[str, ...]
    oos_hit: float | None = None
    oos_rankic: float | None = None
    oos_gated_hit: float | None = None
    oos_coverage: float | None = None
    artifact_path: str | None = None
    notes: str | None = None
    degraded: bool = False
    train_start: date | None = None
    train_end: date | None = None
    parent_model_id: str | None = None


def feature_set_hash(features: list[str] | tuple[str, ...]) -> str:
    blob = json.dumps(list(features), separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


async def register_model(storage: Storage, entry: RegistryEntry) -> str:
    """Insert or update a registry row. Returns model_id."""
    async with storage._pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO model_registry (
                model_id, algo, feature_set_hash, feature_list,
                train_start, train_end, horizons, oos_rankic, oos_hit,
                oos_gated_hit, oos_coverage, status, degraded,
                artifact_path, notes, parent_model_id
            ) VALUES (
                %s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            ON CONFLICT (model_id) DO UPDATE SET
                oos_rankic = EXCLUDED.oos_rankic,
                oos_hit = EXCLUDED.oos_hit,
                oos_gated_hit = EXCLUDED.oos_gated_hit,
                oos_coverage = EXCLUDED.oos_coverage,
                -- Never demote an existing champion via re-register collision.
                status = CASE
                    WHEN model_registry.status = 'champion'
                         AND EXCLUDED.status = 'challenger'
                    THEN model_registry.status
                    ELSE EXCLUDED.status
                END,
                degraded = EXCLUDED.degraded,
                artifact_path = COALESCE(EXCLUDED.artifact_path, model_registry.artifact_path),
                notes = EXCLUDED.notes
            """,
            (
                entry.model_id,
                entry.algo,
                feature_set_hash(entry.feature_list),
                json.dumps(list(entry.feature_list)),
                entry.train_start,
                entry.train_end,
                list(entry.horizons),
                entry.oos_rankic,
                entry.oos_hit,
                entry.oos_gated_hit,
                entry.oos_coverage,
                entry.status,
                entry.degraded,
                entry.artifact_path,
                entry.notes,
                entry.parent_model_id,
            ),
        )
    log.info("model_registered", model_id=entry.model_id, status=entry.status)
    return entry.model_id


async def get_champion(storage: Storage) -> dict[str, Any] | None:
    async with storage._pool.connection() as conn:
        row = await (
            await conn.execute(
                """
                SELECT * FROM model_registry
                WHERE status = 'champion'
                ORDER BY promoted_at DESC NULLS LAST
                LIMIT 1
                """
            )
        ).fetchone()
    return dict(row) if row else None


async def promote_challenger(
    storage: Storage,
    *,
    challenger_id: str,
    notes: str | None = None,
) -> bool:
    """Promote challenger to champion; retire previous champion."""
    async with storage._pool.connection() as conn, conn.transaction():
        await conn.execute(
            """
            UPDATE model_registry
            SET status = 'retired', retired_at = now()
            WHERE status = 'champion'
            """
        )
        row = await (
            await conn.execute(
                """
                UPDATE model_registry
                SET status = 'champion',
                    promoted_at = now(),
                    degraded = FALSE,
                    notes = COALESCE(%s, notes)
                WHERE model_id = %s AND status IN ('challenger', 'candidate')
                RETURNING model_id
                """,
                (notes, challenger_id),
            )
        ).fetchone()
    ok = row is not None
    if ok:
        await write_registry_markdown(storage)
    log.info("model_promoted", challenger_id=challenger_id, ok=ok)
    return ok


async def rollback_champion(storage: Storage) -> str | None:
    """Roll current champion back to most recent retired parent."""
    async with storage._pool.connection() as conn, conn.transaction():
        champ = await (
            await conn.execute(
                "SELECT model_id, parent_model_id FROM model_registry "
                "WHERE status='champion' LIMIT 1"
            )
        ).fetchone()
        if champ is None:
            return None
        cd = dict(champ)
        parent = cd.get("parent_model_id")
        await conn.execute(
            """
            UPDATE model_registry
            SET status = 'rolled_back', retired_at = now()
            WHERE model_id = %s
            """,
            (cd["model_id"],),
        )
        if parent:
            await conn.execute(
                """
                UPDATE model_registry
                SET status = 'champion', promoted_at = now(), degraded = FALSE
                WHERE model_id = %s
                """,
                (parent,),
            )
    await write_registry_markdown(storage)
    return parent if isinstance(parent, str) else None


async def list_registry(storage: Storage, *, limit: int = 50) -> list[dict[str, Any]]:
    async with storage._pool.connection() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT model_id, algo, status, horizons, oos_hit, oos_rankic,
                       oos_gated_hit, oos_coverage, degraded, promoted_at, created_at
                FROM model_registry
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (max(1, min(limit, 200)),),
            )
        ).fetchall()
    return [dict(r) for r in rows]


async def write_registry_markdown(storage: Storage) -> Path:
    rows = await list_registry(storage, limit=100)
    lines = [
        "# Model registry",
        "",
        f"**Updated (UTC):** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "| model_id | status | algo | oos_hit | oos_gated_hit | coverage | degraded |",
        "|---|---|---|---:|---:|---:|:---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('model_id')} | {r.get('status')} | {r.get('algo')} | "
            f"{r.get('oos_hit')} | {r.get('oos_gated_hit')} | {r.get('oos_coverage')} | "
            f"{r.get('degraded')} |"
        )
    lines.extend(["", "Research only — not financial advice.", ""])
    REGISTRY_MD.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_MD.write_text("\n".join(lines), encoding="utf-8")
    return REGISTRY_MD


def artifact_dir_for(model_id: str) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACT_DIR / model_id
