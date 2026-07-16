"""High-Precision Emitter serve path (``ml_hpe_p90_v1``).

Flag-gated writer: only symbols that clear a locked multi-stream gate get
``forecast_points``. Research estimates — not financial advice.

OOS proof: ``docs/experiments/ml_precision90_20260716T154908Z.md`` (~90.3%
precision, 435 emits, stress_pass).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from chime.domain import ForecastPoint
from chime.logging_setup import get_logger
from chime.ml import sklearn_available
from chime.ml.dataset import Sample, build_samples, load_symbol_bars
from chime.ml.features import FEATURE_NAMES, path_features
from chime.ml.harden import _demean_by_day
from chime.ml.iterate import _enrich_cross_section, _predict_lmt_bagged
from chime.storage import Storage

log = get_logger(__name__)

CONFIG_PATH = Path(__file__).with_name("hpe_p90_v1.json")
MODEL_VERSION = "ml_hpe_p90_v1"


@dataclass(frozen=True, slots=True)
class HpeServeResult:
    symbols_scanned: int
    emits: int
    points_written: int
    model_version: str


def load_hpe_config(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or CONFIG_PATH).read_text(encoding="utf-8"))


def _gate_features(sample: Sample, stream: dict[str, Any]) -> bool:
    try:
        ri = FEATURE_NAMES.index("range_20d")
        vi = FEATURE_NAMES.index("vol_20d")
    except ValueError:
        return False
    if ri >= len(sample.x) or vi >= len(sample.x):
        return False
    rng, vol = float(sample.x[ri]), float(sample.x[vi])
    r_cut = float(stream["range_cut"])
    v_cut = float(stream["vol_cut"])
    mode = stream.get("mode", "range")
    if not math.isfinite(rng) or rng < r_cut:
        return False
    if mode == "range_vol" and (not math.isfinite(vol) or vol < v_cut):
        return False
    return True


def _latest_feature_rows(series: dict) -> list[Sample]:
    rows: list[Sample] = []
    for _symbol, bars in series.items():
        ordered = sorted(bars, key=lambda b: b.trade_date)
        if len(ordered) < 60:
            continue
        feats = path_features(ordered)
        if feats is None:
            continue
        rows.append(
            Sample(
                symbol=feats.symbol,
                as_of=feats.as_of,
                x=feats.values,
                y_ret=0.0,
                y_dir=1.0,
                horizon=1,
            )
        )
    return _enrich_cross_section(rows)


async def run_hpe_forecast(
    *,
    storage: Storage,
    force: bool = False,
    config_path: Path | None = None,
) -> HpeServeResult:
    """Train LMT-bagged clf on panel history; emit gated forecast points."""
    _ = force
    if not sklearn_available():
        log.warning("hpe_sklearn_missing")
        return HpeServeResult(0, 0, 0, MODEL_VERSION)

    cfg = load_hpe_config(config_path)
    series = await load_symbol_bars(storage)
    if not series:
        return HpeServeResult(0, 0, 0, MODEL_VERSION)

    train = _enrich_cross_section(
        _demean_by_day(build_samples(series, horizon=1, min_history=60))
    )
    latest = _latest_feature_rows(series)
    if len(train) < 100 or not latest:
        log.warning("hpe_insufficient_data", train=len(train), latest=len(latest))
        return HpeServeResult(len(series), 0, 0, MODEL_VERSION)

    try:
        scores = _predict_lmt_bagged(train, latest)
    except Exception as exc:
        log.warning("hpe_predict_failed", error=str(exc))
        return HpeServeResult(len(series), 0, 0, MODEL_VERSION)

    streams = cfg.get("streams") or {}
    emits = 0
    points_written = 0

    for sample, score in zip(latest, scores, strict=True):
        fired: list[int] = []
        for stream in streams.values():
            if abs(score) < float(stream["score_thr"]):
                continue
            if not _gate_features(sample, stream):
                continue
            fired.append(int(stream["horizon"]))
        if not fired:
            continue
        emits += 1
        bars = series.get(sample.symbol) or []
        if not bars:
            continue
        last = sorted(bars, key=lambda b: b.trade_date)[-1]
        last_px = last.price
        if not math.isfinite(last_px) or last_px <= 0:
            continue
        direction = 1.0 if score > 0 else -1.0
        mag = min(0.08, abs(score) * 0.25)
        as_of = sample.as_of
        last_ts = last.bar_ts
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=UTC)
        fps: list[ForecastPoint] = []
        for h in sorted(set(fired)):
            yhat = last_px * (1.0 + direction * mag * (h / max(fired)))
            if not math.isfinite(yhat) or yhat <= 0:
                continue
            fps.append(
                ForecastPoint(
                    symbol=sample.symbol,
                    as_of=as_of,
                    horizon_i=h,
                    ts=last_ts + timedelta(days=h),
                    yhat=yhat,
                    model_version=MODEL_VERSION,
                )
            )
        if fps:
            points_written += await storage.replace_forecast_points(fps)

    log.info(
        "hpe_serve_done",
        scanned=len(series),
        emits=emits,
        points=points_written,
        model=MODEL_VERSION,
    )
    return HpeServeResult(
        symbols_scanned=len(series),
        emits=emits,
        points_written=points_written,
        model_version=MODEL_VERSION,
    )
