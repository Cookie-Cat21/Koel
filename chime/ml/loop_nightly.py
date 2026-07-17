"""Loop A — nightly score, scoreboard, drift stubs, gate recalibration."""

from __future__ import annotations

import json
from dataclasses import dataclass  # noqa: I001 — keep json near top
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from chime.logging_setup import get_logger
from chime.ml.outcomes import (
    attach_regime_and_emit_from_forecast_points,
    score_due_outcomes,
)
from chime.ml.registry import get_champion, write_registry_markdown
from chime.storage import Storage

log = get_logger(__name__)

SCOREBOARD = Path("docs/experiments/LIVE_SCOREBOARD.md")
CALIBRATION = Path("data/ml_artifacts/gate_calibration.json")


@dataclass(frozen=True, slots=True)
class NightlyResult:
    emitted: int
    scored: int
    drift_alerts: tuple[str, ...]
    scoreboard_path: str


async def _load_scored_window(storage: Storage, *, days: int = 60) -> list[dict]:
    since = date.today() - timedelta(days=days)
    async with storage._pool.connection() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT issued_at, symbol, y_pred, y_real, hit, confidence, gate, regime_tag
                FROM forecast_outcomes
                WHERE scored = TRUE AND issued_at >= %s
                ORDER BY issued_at DESC
                """,
                (since,),
            )
        ).fetchall()
    return [dict(r) for r in rows]


def _hit_rate(
    rows: list[dict], *, gated: bool = False, gate_thr: float = 0.55
) -> float | None:
    pool = rows
    if gated:
        pool = [r for r in rows if (r.get("confidence") or 0) >= gate_thr]
    usable = [r for r in pool if r.get("hit") is not None]
    if not usable:
        return None
    return sum(1 for r in usable if r["hit"]) / len(usable)


def _recalibrate_gate(rows: list[dict]) -> dict:
    """Simple bin calibration: confidence threshold → empirical hit rate."""
    bins = [0.0, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 1.01]
    out = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        bucket = [
            r
            for r in rows
            if r.get("hit") is not None
            and r.get("confidence") is not None
            and lo <= float(r["confidence"]) < hi
        ]
        if len(bucket) < 20:
            continue
        hit = sum(1 for r in bucket if r["hit"]) / len(bucket)
        out.append({"lo": lo, "hi": hi, "n": len(bucket), "hit_rate": hit})
    # Pick lowest threshold with hit_rate >= 0.65
    thr = 0.55
    for b in out:
        if b["hit_rate"] >= 0.65:
            thr = b["lo"]
            break
    return {"updated_at": datetime.now(UTC).isoformat(), "threshold": thr, "bins": out}


def _drift_alerts(rows: list[dict], champion_oos_hit: float | None) -> list[str]:
    alerts: list[str] = []
    recent = [
        r
        for r in rows
        if r.get("issued_at") and r["issued_at"] >= date.today() - timedelta(days=20)
    ]
    live = _hit_rate(recent)
    if (
        champion_oos_hit is not None
        and live is not None
        and live < 0.5 * float(champion_oos_hit)
        and len(recent) >= 50
    ):
        alerts.append(
            f"ML_DRIFT: live 20d hit={live:.3f} < 0.5× champion OOS hit={champion_oos_hit:.3f}"
        )
    return alerts


async def append_live_scoreboard(storage: Storage, *, alerts: list[str]) -> Path:
    rows = await _load_scored_window(storage, days=60)
    cal = {}
    if CALIBRATION.is_file():
        try:
            cal = json.loads(CALIBRATION.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cal = {}
    thr = float(cal.get("threshold", 0.55))
    hit20 = _hit_rate(
        [
            r
            for r in rows
            if r.get("issued_at") and r["issued_at"] >= date.today() - timedelta(days=20)
        ]
    )
    hit60 = _hit_rate(rows)
    g20 = _hit_rate(
        [
            r
            for r in rows
            if r.get("issued_at") and r["issued_at"] >= date.today() - timedelta(days=20)
        ],
        gated=True,
        gate_thr=thr,
    )
    today = date.today().isoformat()
    h20s = f"{hit20:.4f}" if hit20 is not None else "None"
    h60s = f"{hit60:.4f}" if hit60 is not None else "None"
    g20s = f"{g20:.4f}" if g20 is not None else "None"
    line = (
        f"| {today} | {h20s} | {h60s} | {g20s} | "
        f"{len(rows)} | {'; '.join(alerts) or '-'} |"
    )
    SCOREBOARD.parent.mkdir(parents=True, exist_ok=True)
    header = "\n".join(
        [
            "# Live scoreboard (from forecast_outcomes)",
            "",
            "| date | hit_20d | hit_60d | gated_hit_20d | n_60d | alerts |",
            "|---|---:|---:|---:|---:|---|",
            "",
        ]
    )
    if not SCOREBOARD.exists():
        SCOREBOARD.write_text(header + line + "\n", encoding="utf-8")
        return SCOREBOARD
    lines = SCOREBOARD.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if not ln.startswith(f"| {today} ")]
    # ensure header present
    if not any(ln.startswith("| date |") for ln in kept):
        SCOREBOARD.write_text(header + line + "\n", encoding="utf-8")
        return SCOREBOARD
    # append today's line after last table row / at end
    SCOREBOARD.write_text("\n".join(kept).rstrip() + "\n" + line + "\n", encoding="utf-8")
    return SCOREBOARD


async def run_loop_nightly(storage: Storage) -> NightlyResult:
    emitted = await attach_regime_and_emit_from_forecast_points(storage)
    scored_res = await score_due_outcomes(storage, limit=20_000)
    rows = await _load_scored_window(storage, days=120)
    champ = await get_champion(storage)
    champ_hit = float(champ["oos_hit"]) if champ and champ.get("oos_hit") is not None else None
    alerts = _drift_alerts(rows, champ_hit)
    if alerts and champ:
        async with storage._pool.connection() as conn:
            await conn.execute(
                "UPDATE model_registry SET degraded = TRUE WHERE status = 'champion'"
            )
    cal = _recalibrate_gate(rows)
    CALIBRATION.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION.write_text(json.dumps(cal, indent=2) + "\n", encoding="utf-8")
    path = await append_live_scoreboard(storage, alerts=alerts)
    await write_registry_markdown(storage)
    log.info(
        "loop_nightly_done",
        emitted=emitted,
        scored=scored_res.scored,
        alerts=alerts,
    )
    return NightlyResult(
        emitted=emitted,
        scored=scored_res.scored,
        drift_alerts=tuple(alerts),
        scoreboard_path=str(path),
    )
