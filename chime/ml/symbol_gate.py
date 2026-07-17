"""Symbol reliability allowlist for selective ≥90% emits (B-013)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from chime.logging_setup import get_logger
from chime.storage import Storage

log = get_logger(__name__)

ALLOWLIST_PATH = Path("data/ml_artifacts/reliable_symbols.json")
# Temporal holdout (last 20% issued_at) 2026-07-17:
# sym_hit≥0.61 & conf≥0.71 → hit=0.90 @ n=60. Prefer over in-sample thr.
DEFAULT_SYM_HIT_THR = 0.61
DEFAULT_CONF_THR = 0.71
DEFAULT_MIN_ROWS = 20


@dataclass(frozen=True, slots=True)
class SymbolGateConfig:
    symbols: tuple[str, ...]
    sym_hit_thr: float
    conf_thr: float
    min_rows: int
    n_scored: int
    updated_at: str


async def rebuild_symbol_allowlist(
    storage: Storage,
    *,
    model_version: str = "wf_fin_sector_h1",
    sym_hit_thr: float = DEFAULT_SYM_HIT_THR,
    conf_thr: float = DEFAULT_CONF_THR,
    min_rows: int = DEFAULT_MIN_ROWS,
    path: Path = ALLOWLIST_PATH,
) -> SymbolGateConfig:
    """Compute symbols with historical OOS hit ≥ thr from forecast_outcomes."""
    async with storage._pool.connection() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT symbol,
                       COUNT(*) AS n,
                       AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END) AS hit
                FROM forecast_outcomes
                WHERE model_version = %s
                  AND scored = TRUE
                  AND hit IS NOT NULL
                GROUP BY symbol
                HAVING COUNT(*) >= %s
                """,
                (model_version, min_rows),
            )
        ).fetchall()
    good: list[str] = []
    for row in rows:
        d = dict(row)
        hit = d.get("hit")
        sym = str(d.get("symbol") or "").strip().upper()
        if not sym or hit is None:
            continue
        if float(hit) >= sym_hit_thr:
            good.append(sym)
    good.sort()
    cfg = SymbolGateConfig(
        symbols=tuple(good),
        sym_hit_thr=sym_hit_thr,
        conf_thr=conf_thr,
        min_rows=min_rows,
        n_scored=len(rows),
        updated_at=datetime.now(UTC).isoformat(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "symbols": list(cfg.symbols),
                "sym_hit_thr": cfg.sym_hit_thr,
                "conf_thr": cfg.conf_thr,
                "min_rows": cfg.min_rows,
                "n_scored_symbols": cfg.n_scored,
                "updated_at": cfg.updated_at,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    log.info(
        "symbol_allowlist_rebuilt",
        n_symbols=len(cfg.symbols),
        sym_hit_thr=sym_hit_thr,
        conf_thr=conf_thr,
        path=str(path),
    )
    return cfg


def load_symbol_gate(path: Path = ALLOWLIST_PATH) -> SymbolGateConfig | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    syms = data.get("symbols") or []
    if not isinstance(syms, list):
        return None
    clean = tuple(
        sorted(
            {
                str(s).strip().upper()
                for s in syms
                if isinstance(s, str) and s.strip()
            }
        )
    )
    return SymbolGateConfig(
        symbols=clean,
        sym_hit_thr=float(data.get("sym_hit_thr", DEFAULT_SYM_HIT_THR)),
        conf_thr=float(data.get("conf_thr", DEFAULT_CONF_THR)),
        min_rows=int(data.get("min_rows", DEFAULT_MIN_ROWS)),
        n_scored=int(data.get("n_scored_symbols", 0)),
        updated_at=str(data.get("updated_at", "")),
    )
