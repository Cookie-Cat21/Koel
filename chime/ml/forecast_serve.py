"""Unified forecast serve: HPE-first, optional always-on fallback with confidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, timedelta

from chime.domain import ForecastPoint
from chime.logging_setup import get_logger
from chime.ml import sklearn_available
from chime.ml.always_on import (
    enrich_samples_with_financial_filings,
    enrich_samples_with_sector_rs,
    enrich_samples_with_yoy,
    load_financial_filing_dates,
    load_yoy_events,
)
from chime.ml.confidence import confidence_band, score_to_confidence
from chime.ml.dataset import Sample, build_samples, load_symbol_bars
from chime.ml.diagnose import load_sector_map
from chime.ml.features import path_features
from chime.ml.harden import _demean_by_day
from chime.ml.hpe import run_hpe_forecast
from chime.ml.iterate import _enrich_cross_section, _predict_lmt_bagged
from chime.storage import Storage

log = get_logger(__name__)

ALWAYS_ON_VERSION = "ml_always_on_fin_v1"
GATED_VERSION = "ml_gated_c55_v1"
GATED_P90_VERSION = "ml_gated_p90_v2"
DEFAULT_GATE_THR = 0.55
# Fallback if allowlist missing: thr=0.84 → hit≈0.905 @ n=42 (cov≈0.24%).
P90_GATE_THR = 0.84


def _load_gate_threshold(*, p90: bool = False) -> float:
    if p90:
        from chime.ml.symbol_gate import load_symbol_gate

        gate = load_symbol_gate()
        if gate is not None:
            return gate.conf_thr
        return P90_GATE_THR
    from pathlib import Path
    import json

    path = Path("data/ml_artifacts/gate_calibration.json")
    if not path.is_file():
        return DEFAULT_GATE_THR
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_GATE_THR
    thr = data.get("threshold")
    if isinstance(thr, int | float) and 0.0 <= float(thr) <= 1.0:
        return float(thr)
    return DEFAULT_GATE_THR


@dataclass(frozen=True, slots=True)
class UnifiedForecastResult:
    hpe_emits: int
    fallback_emits: int
    points_written: int
    mode: str


async def run_unified_forecast(
    *,
    storage: Storage,
    mode: str = "hpe_with_fallback",
    cse=None,
) -> UnifiedForecastResult:
    """Write forecasts with confidence.

    Modes:
    - ``hpe_only``: only High-Precision Emitter
    - ``hpe_with_fallback``: HPE then always-on for symbols without HPE emit
    - ``always_on``: always-on stack only
    - ``gated``: always-on but only emit when confidence ≥ calibrated threshold
      (B-005 KEEP — ~72% hit @ ~11% coverage at thr=0.55 on WF ledger)
    - ``gated_p90``: symbol-reliability allowlist × conf gate targeting ≥90%
      precision (B-013; fallback thr=0.84 if allowlist missing)
    """
    if not sklearn_available():
        return UnifiedForecastResult(0, 0, 0, mode)

    hpe_emits = 0
    points = 0
    hpe_symbols: set[str] = set()
    gate_thr = _load_gate_threshold(p90=(mode == "gated_p90"))
    reliable: set[str] | None = None
    if mode == "gated_p90":
        from chime.ml.symbol_gate import load_symbol_gate

        sg = load_symbol_gate()
        if sg is not None and sg.symbols:
            reliable = set(sg.symbols)

    if mode in {"hpe_only", "hpe_with_fallback"}:
        hpe = await run_hpe_forecast(storage=storage, force=True)
        hpe_emits = hpe.emits
        points += hpe.points_written
        # Discover which symbols got HPE points today
        async with storage._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT DISTINCT symbol FROM forecast_points
                    WHERE model_version = %s AND as_of = CURRENT_DATE
                    """,
                    ("ml_hpe_p90_v1",),
                )
            ).fetchall()
        for row in rows:
            d = dict(row)
            sym = d.get("symbol")
            if isinstance(sym, str):
                hpe_symbols.add(sym.strip().upper())

    fallback_emits = 0
    if mode in {"hpe_with_fallback", "always_on", "gated", "gated_p90"}:
        from datetime import date
        from pathlib import Path
        import json

        series = await load_symbol_bars(storage)
        train = _enrich_cross_section(
            _demean_by_day(build_samples(series, horizon=1, min_history=60))
        )
        # Latest feature rows + enrichments
        latest: list[Sample] = []
        for _sym, bars in series.items():
            ordered = sorted(bars, key=lambda b: b.trade_date)
            if len(ordered) < 60:
                continue
            feats = path_features(ordered)
            if feats is None:
                continue
            latest.append(
                Sample(
                    symbol=feats.symbol,
                    as_of=feats.as_of,
                    x=feats.values,
                    y_ret=0.0,
                    y_dir=1.0,
                    horizon=1,
                )
            )
        latest = _enrich_cross_section(latest)
        sectors = await load_sector_map(storage)
        train = enrich_samples_with_sector_rs(train, sectors)
        latest = enrich_samples_with_sector_rs(latest, sectors)

        cache = Path("data/financial_filings_cache.json")
        if cache.is_file():
            raw = json.loads(cache.read_text(encoding="utf-8"))
            filings = [(str(a), date.fromisoformat(str(b)), str(c)) for a, b, c in raw]
        elif cse is not None:
            filings = await load_financial_filing_dates(
                cse, sorted(series.keys()), sleep_seconds=0.0, limit=None
            )
        else:
            filings = []
        if filings:
            train = enrich_samples_with_financial_filings(train, filings)
            latest = enrich_samples_with_financial_filings(latest, filings)
        yoy = await load_yoy_events(storage)
        if yoy:
            train = enrich_samples_with_yoy(train, yoy)
            latest = enrich_samples_with_yoy(latest, yoy)

        if len(train) >= 100 and latest:
            scores = _predict_lmt_bagged(train, latest)
            for sample, score in zip(latest, scores, strict=True):
                if mode == "hpe_with_fallback" and sample.symbol in hpe_symbols:
                    continue
                conf = score_to_confidence(score)
                if mode in {"gated", "gated_p90"} and conf < gate_thr:
                    continue
                if (
                    mode == "gated_p90"
                    and reliable is not None
                    and sample.symbol not in reliable
                ):
                    continue
                if mode == "gated_p90":
                    gate_name = "gated_p90"
                    version = GATED_P90_VERSION
                elif mode == "gated":
                    gate_name = "gated_c55"
                    version = GATED_VERSION
                else:
                    gate_name = "always_on"
                    version = ALWAYS_ON_VERSION
                band = confidence_band(conf, gate=gate_name)
                if band == "none" and mode not in {"gated", "gated_p90"}:
                    continue
                if mode in {"gated", "gated_p90"}:
                    band = "high" if conf >= 0.65 else "medium"
                bars = series.get(sample.symbol) or []
                if not bars:
                    continue
                last = sorted(bars, key=lambda b: b.trade_date)[-1]
                last_px = last.price
                if not math.isfinite(last_px) or last_px <= 0:
                    continue
                direction = 1.0 if score > 0 else -1.0
                mag = min(0.06, abs(score) * 0.2)
                last_ts = last.bar_ts
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=UTC)
                fps = []
                if mode == "gated_p90":
                    reasons = [
                        f"Reliability×confidence gate (conf≥{gate_thr:.2f})",
                        "WF ledger ~90% hit on allowlisted symbols (NFA)",
                        f"|score|={abs(score):.3f}",
                    ]
                elif mode == "gated":
                    reasons = [
                        f"Confidence-gated research estimate (thr≥{gate_thr:.2f})",
                        "WF ledger ~72% hit @ ~11% coverage (NFA)",
                        f"|score|={abs(score):.3f}",
                    ]
                else:
                    reasons = [
                        "Always-on research estimate (historical hit ~60%)",
                        f"|score|={abs(score):.3f}",
                    ]
                for h in (1, 2, 3, 5):
                    yhat = last_px * (1.0 + direction * mag * (h / 5.0))
                    if not math.isfinite(yhat) or yhat <= 0:
                        continue
                    fps.append(
                        ForecastPoint(
                            symbol=sample.symbol,
                            as_of=sample.as_of,
                            horizon_i=h,
                            ts=last_ts + timedelta(days=h),
                            yhat=yhat,
                            model_version=version,
                            confidence=conf,
                            confidence_band=band,
                            gate=gate_name,
                            reasons=reasons,
                        )
                    )
                if fps:
                    fallback_emits += 1
                    points += await storage.replace_forecast_points(fps)

    # Feed the self-learning ledger (shadow + gated emits).
    try:
        from chime.ml.outcomes import attach_regime_and_emit_from_forecast_points

        n_out = await attach_regime_and_emit_from_forecast_points(storage)
        log.info("forecast_outcomes_emitted", n=n_out)
    except Exception as exc:
        log.warning("forecast_outcomes_emit_failed", error=str(exc)[:200])

    log.info(
        "unified_forecast_done",
        mode=mode,
        hpe_emits=hpe_emits,
        fallback_emits=fallback_emits,
        points=points,
    )
    return UnifiedForecastResult(
        hpe_emits=hpe_emits,
        fallback_emits=fallback_emits,
        points_written=points,
        mode=mode,
    )
