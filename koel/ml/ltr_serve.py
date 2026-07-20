"""Production serve for LTR ranking + dual-target vol sizing.

Trains XGB ``rank:pairwise`` (HGB clf fallback) and HGB abs-return vol,
emits confidence-gated ``forecast_points``, and can challenge the registry.

Research estimates only — not financial advice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from koel.domain import ForecastPoint
from koel.logging_setup import get_logger
from koel.ml import sklearn_available
from koel.ml.always_on import (
    enrich_samples_with_financial_filings,
    enrich_samples_with_sector_rs,
    enrich_samples_with_yoy,
    load_yoy_events,
)
from koel.ml.confidence import score_to_confidence
from koel.ml.dataset import Sample, build_samples, load_symbol_bars
from koel.ml.diagnose import load_sector_map
from koel.ml.features import FEATURE_NAMES, path_features
from koel.ml.harden import _demean_by_day, _purge_train
from koel.ml.iterate import _enrich_cross_section
from koel.ml.ltr_dual import (
    _enrich_liq_sentiment,
    _lightgbm_available,
    _predict_hgb_clf,
    _predict_hgb_reg,
    _predict_lgb_rank,
    _predict_xgb_rank,
    _xgboost_available,
)
from koel.ml.metrics import mean_daily_rank_ic
from koel.ml.registry import (
    RegistryEntry,
    get_champion,
    promote_challenger,
    register_model,
    write_registry_markdown,
)
from koel.ml.walkforward import _unique_sorted_dates
from koel.storage import Storage

log = get_logger(__name__)

LTR_GATED_VERSION = "ml_ltr_xgb_pw_v1"
LTR_GATE_NAME = "gated_ltr"
DEFAULT_GATE_THR = 0.55
IDX_TURN_PCT_EXTRA = len(FEATURE_NAMES) + 3  # after CS(+3) + liq t_pct


@dataclass(frozen=True, slots=True)
class LtrOosMetrics:
    mean_rank_ic: float | None
    gated_hit: float | None
    gated_coverage: float | None
    pooled_hit: float | None
    vol_rank_ic: float | None
    folds: int
    origins: int
    ranker: str


@dataclass
class LtrShipResult:
    challenger_id: str
    promoted: bool
    emits: int
    points_written: int
    metrics: LtrOosMetrics | None
    champion_gated_hit: float | None
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "challenger_id": self.challenger_id,
            "promoted": self.promoted,
            "emits": self.emits,
            "points_written": self.points_written,
            "champion_gated_hit": self.champion_gated_hit,
            "reasons": list(self.reasons),
            "metrics": None
            if self.metrics is None
            else {
                "mean_rank_ic": self.metrics.mean_rank_ic,
                "gated_hit": self.metrics.gated_hit,
                "gated_coverage": self.metrics.gated_coverage,
                "pooled_hit": self.metrics.pooled_hit,
                "vol_rank_ic": self.metrics.vol_rank_ic,
                "folds": self.metrics.folds,
                "origins": self.metrics.origins,
                "ranker": self.metrics.ranker,
            },
        }


def _choose_ranker() -> str:
    if _xgboost_available():
        return "xgb_pairwise"
    if _lightgbm_available():
        return "lgb_lambdarank"
    return "hgb_clf"


def predict_rank_scores(train: list[Sample], test: list[Sample], *, ranker: str) -> list[float]:
    if ranker == "xgb_pairwise":
        return _predict_xgb_rank(train, test, objective="rank:pairwise")
    if ranker == "lgb_lambdarank":
        return _predict_lgb_rank(train, test)
    return _predict_hgb_clf(train, test)


def predict_vol_scores(train: list[Sample], test: list[Sample]) -> list[float]:
    return _predict_hgb_reg(train, test, y_fn=lambda s: abs(s.y_ret))


async def build_ltr_panels(
    storage: Storage,
    *,
    cse=None,
) -> tuple[dict[str, list], list[Sample], list[Sample], str]:
    """Return (series, train_samples, latest_samples, ranker_id)."""
    import json

    series = await load_symbol_bars(storage)
    train = _enrich_liq_sentiment(
        _enrich_cross_section(
            _demean_by_day(build_samples(series, horizon=1, min_history=60))
        )
    )
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
    latest = _enrich_liq_sentiment(_enrich_cross_section(latest))

    sectors = await load_sector_map(storage)
    train = enrich_samples_with_sector_rs(train, sectors)
    latest = enrich_samples_with_sector_rs(latest, sectors)

    cache = Path("data/financial_filings_cache.json")
    filings: list[tuple[str, date, str]] = []
    if cache.is_file():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        filings = [(str(a), date.fromisoformat(str(b)), str(c)) for a, b, c in raw]
    if filings:
        train = enrich_samples_with_financial_filings(train, filings)
        latest = enrich_samples_with_financial_filings(latest, filings)

    yoy = await load_yoy_events(storage)
    if yoy:
        train = enrich_samples_with_yoy(train, yoy)
        latest = enrich_samples_with_yoy(latest, yoy)

    return series, train, latest, _choose_ranker()


def evaluate_ltr_oos(
    samples: list[Sample],
    *,
    ranker: str,
    gate_thr: float = DEFAULT_GATE_THR,
    min_train_days: int = 80,
    fold_step: int = 10,
    embargo: int = 2,
) -> LtrOosMetrics:
    """Purged walk-forward RankIC + gated direction hit for registry challenge."""
    dates = _unique_sorted_dates(samples)
    as_of: list[date] = []
    preds: list[float] = []
    actuals: list[float] = []
    y_dirs: list[float] = []
    vol_as: list[date] = []
    vol_p: list[float] = []
    vol_a: list[float] = []
    folds = 0
    origins = 0
    gated_hits = 0
    gated_n = 0
    pool_hits = 0
    pool_n = 0

    cut = min_train_days
    while cut + fold_step <= len(dates):
        test_dates = set(dates[cut : cut + fold_step])
        train = _purge_train(
            samples, dates=dates, cut=cut, horizon=1, embargo=embargo
        )
        test = [s for s in samples if s.as_of in test_dates]
        cut += fold_step
        if len(train) < 80 or len(test) < 15:
            continue
        try:
            scores = predict_rank_scores(train, test, ranker=ranker)
            vols = predict_vol_scores(train, test)
        except Exception as exc:
            log.warning("ltr_oos_fold_failed", error=str(exc)[:120])
            continue
        folds += 1
        origins += len(test)
        for s, sc, vv in zip(test, scores, vols, strict=True):
            if not math.isfinite(sc):
                continue
            as_of.append(s.as_of)
            preds.append(sc)
            actuals.append(s.y_ret)
            y_dirs.append(s.y_dir)
            conf = score_to_confidence(sc)
            pred_d = 1.0 if sc > 0 else -1.0
            hit = (s.y_dir > 0 and pred_d > 0) or (s.y_dir < 0 and pred_d < 0)
            if s.y_dir != 0:
                pool_n += 1
                if hit:
                    pool_hits += 1
            if conf >= gate_thr and s.y_dir != 0:
                gated_n += 1
                if hit:
                    gated_hits += 1
            if math.isfinite(vv):
                vol_as.append(s.as_of)
                vol_p.append(vv)
                vol_a.append(abs(s.y_ret))

    rank_ic, _days = mean_daily_rank_ic(as_of, preds, actuals)
    vol_ic, _ = mean_daily_rank_ic(vol_as, vol_p, vol_a)
    return LtrOosMetrics(
        mean_rank_ic=rank_ic,
        gated_hit=(gated_hits / gated_n) if gated_n else None,
        gated_coverage=(gated_n / origins) if origins else None,
        pooled_hit=(pool_hits / pool_n) if pool_n else None,
        vol_rank_ic=vol_ic,
        folds=folds,
        origins=origins,
        ranker=ranker,
    )


def _turnover_pct(sample: Sample) -> float | None:
    if len(sample.x) <= IDX_TURN_PCT_EXTRA:
        return None
    v = sample.x[IDX_TURN_PCT_EXTRA]
    return float(v) if math.isfinite(v) else None


def _vol_magnitude(vol_pred: float) -> float:
    """Map predicted |return| to a capped path magnitude."""
    if not math.isfinite(vol_pred) or vol_pred <= 0:
        return 0.015
    return max(0.01, min(0.08, float(vol_pred)))


def _effective_gate_thr(sample: Sample, *, base: float) -> float:
    """Slightly looser gate for low-turnover names (stronger RankIC regime)."""
    t = _turnover_pct(sample)
    if t is not None and t < 1.0 / 3.0:
        return max(0.45, base - 0.05)
    return base


async def write_ltr_gated_forecasts(
    *,
    storage: Storage,
    series: dict[str, list],
    train: list[Sample],
    latest: list[Sample],
    ranker: str,
    gate_thr: float = DEFAULT_GATE_THR,
    skip_symbols: set[str] | None = None,
    model_version: str = LTR_GATED_VERSION,
    gate_name: str = LTR_GATE_NAME,
) -> tuple[int, int]:
    """Train on full history panel; emit gated LTR+vol forecast points.

    Returns (emits, points_written).
    """
    if len(train) < 100 or not latest:
        return 0, 0
    try:
        scores = predict_rank_scores(train, latest, ranker=ranker)
        vols = predict_vol_scores(train, latest)
    except Exception as exc:
        log.warning("ltr_serve_predict_failed", error=str(exc)[:160])
        return 0, 0

    # Cross-section rank percentile for reasons
    finite = [(i, s) for i, s in enumerate(scores) if math.isfinite(s)]
    ordered = sorted(finite, key=lambda t: t[1])
    n = len(ordered)
    rank_pct = {
        i: (j / (n - 1) if n > 1 else 0.5) for j, (i, _) in enumerate(ordered)
    }

    skip = skip_symbols or set()
    emits = 0
    points = 0
    for idx, sample in enumerate(latest):
        if sample.symbol in skip:
            continue
        score = scores[idx]
        if not math.isfinite(score):
            continue
        conf = score_to_confidence(score)
        thr = _effective_gate_thr(sample, base=gate_thr)
        if conf < thr:
            continue
        bars = series.get(sample.symbol) or []
        if not bars:
            continue
        last = sorted(bars, key=lambda b: b.trade_date)[-1]
        last_px = last.price
        if not math.isfinite(last_px) or last_px <= 0:
            continue
        vol_pred = vols[idx] if idx < len(vols) else float("nan")
        mag = _vol_magnitude(vol_pred)
        direction = 1.0 if score > 0 else -1.0
        band = "high" if conf >= 0.65 else "medium"
        rp = rank_pct.get(idx)
        t_pct = _turnover_pct(sample)
        reasons = [
            f"LTR cross-section rank ({ranker}; conf≥{thr:.2f})",
            "Research estimate — not financial advice",
            f"|score|={abs(score):.3f}",
        ]
        if rp is not None:
            reasons.append(f"CS rank percentile={rp:.2f}")
        if math.isfinite(vol_pred):
            reasons.append(f"Vol sizing |ŷ|={vol_pred:.4f} → mag={mag:.3f}")
        if t_pct is not None and t_pct < 1.0 / 3.0:
            reasons.append("Low-turnover regime (stronger historical RankIC)")

        last_ts = last.bar_ts
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=UTC)
        fps: list[ForecastPoint] = []
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
                    model_version=model_version,
                    confidence=conf,
                    confidence_band=band,
                    gate=gate_name,
                    reasons=reasons,
                )
            )
        if fps:
            emits += 1
            points += await storage.replace_forecast_points(fps)
    return emits, points


def _passes_ltr_promotion(
    *,
    metrics: LtrOosMetrics,
    champion_gated_hit: float | None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if metrics.mean_rank_ic is None or metrics.mean_rank_ic < 0.03:
        reasons.append(
            f"RankIC {metrics.mean_rank_ic} < 0.03 — no ranking edge"
        )
        return False, reasons
    if metrics.gated_hit is None:
        reasons.append("no gated hit from OOS walk-forward")
        return False, reasons
    if champion_gated_hit is None:
        reasons.append("no champion — promote as first LTR champion")
        return True, reasons
    # Prefer beating champion gated hit (legacy direction metric).
    if metrics.gated_hit + 1e-12 >= champion_gated_hit + 0.005:
        reasons.append(
            f"gated hit {metrics.gated_hit:.4f} ≥ "
            f"champion {champion_gated_hit:.4f}+0.005"
        )
        return True, reasons
    # Product shift (GO_LTR+VOL): promote when ranking + vol clear research
    # gates and selective direction stays above coin-flip @ conf≥0.55.
    vol_ok = metrics.vol_rank_ic is not None and metrics.vol_rank_ic >= 0.05
    rank_ok = metrics.mean_rank_ic >= 0.25
    if rank_ok and vol_ok and metrics.gated_hit >= 0.55:
        reasons.append(
            f"GO_LTR+VOL ship promote: RankIC={metrics.mean_rank_ic:.3f} "
            f"volIC={metrics.vol_rank_ic:.3f} gated_hit={metrics.gated_hit:.4f} "
            f"(legacy champion gated={champion_gated_hit:.4f})"
        )
        return True, reasons
    reasons.append(
        f"gated hit {metrics.gated_hit:.4f} < champion "
        f"{champion_gated_hit:.4f}+0.005 (RankIC={metrics.mean_rank_ic:.3f})"
    )
    return False, reasons


async def ship_ltr_serve(
    storage: Storage,
    *,
    cse=None,
    gate_thr: float = DEFAULT_GATE_THR,
    force_promote: bool = False,
    write_forecasts: bool = True,
) -> LtrShipResult:
    """Evaluate LTR OOS, register challenger, optionally promote, write emits."""
    if not sklearn_available():
        return LtrShipResult(
            challenger_id="",
            promoted=False,
            emits=0,
            points_written=0,
            metrics=None,
            champion_gated_hit=None,
            reasons=["sklearn missing"],
        )

    series, train, latest, ranker = await build_ltr_panels(storage, cse=cse)
    metrics = evaluate_ltr_oos(train, ranker=ranker, gate_thr=gate_thr)
    champ = await get_champion(storage)
    champ_hit = None
    if champ and champ.get("oos_gated_hit") is not None:
        champ_hit = float(champ["oos_gated_hit"])
    parent = champ["model_id"] if champ else None

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    challenger_id = f"challenger_ltr_gated_{stamp}"
    await register_model(
        storage,
        RegistryEntry(
            model_id=challenger_id,
            algo=f"{ranker}+hgb_vol_gated_ltr",
            status="challenger",
            horizons=(1, 2, 3, 5),
            feature_list=(
                "path",
                "cs",
                "liq_turnover",
                "sector_rs",
                "financials",
                "yoy",
                "ltr_rank",
                "vol_abs",
            ),
            oos_hit=metrics.pooled_hit,
            oos_rankic=metrics.mean_rank_ic,
            oos_gated_hit=metrics.gated_hit,
            oos_coverage=metrics.gated_coverage,
            train_end=date.today(),
            parent_model_id=parent,
            notes=(
                f"LTR+vol ship; vol_rank_ic={metrics.vol_rank_ic}; "
                f"folds={metrics.folds}"
            ),
        ),
    )

    ok, reasons = _passes_ltr_promotion(
        metrics=metrics, champion_gated_hit=champ_hit
    )
    if force_promote:
        ok = True
        reasons = list(reasons) + ["force_promote"]

    promoted = False
    if ok:
        promoted = await promote_challenger(
            storage, challenger_id=challenger_id, notes="; ".join(reasons)
        )

    emits = 0
    points = 0
    if write_forecasts:
        emits, points = await write_ltr_gated_forecasts(
            storage=storage,
            series=series,
            train=train,
            latest=latest,
            ranker=ranker,
            gate_thr=gate_thr,
        )
        try:
            from koel.ml.outcomes import attach_regime_and_emit_from_forecast_points

            n_out = await attach_regime_and_emit_from_forecast_points(storage)
            log.info("ltr_forecast_outcomes_emitted", n=n_out)
        except Exception as exc:
            log.warning("ltr_outcomes_failed", error=str(exc)[:160])

    await write_registry_markdown(storage)

    # Persist ship report
    out = Path("docs/experiments")
    out.mkdir(parents=True, exist_ok=True)
    result = LtrShipResult(
        challenger_id=challenger_id,
        promoted=promoted,
        emits=emits,
        points_written=points,
        metrics=metrics,
        champion_gated_hit=champ_hit,
        reasons=reasons,
    )
    report = out / f"ml_ltr_ship_{stamp}.md"
    report.write_text(
        "\n".join(
            [
                f"# LTR+vol ship ({stamp})",
                "",
                f"**Promoted:** `{promoted}`",
                f"**Challenger:** `{challenger_id}`",
                f"**Ranker:** `{ranker}`",
                "",
                f"- RankIC: {metrics.mean_rank_ic}",
                f"- Gated hit @ {gate_thr}: {metrics.gated_hit} "
                f"(cov={metrics.gated_coverage})",
                f"- Vol RankIC: {metrics.vol_rank_ic}",
                f"- Champion gated hit: {champ_hit}",
                f"- Emits: {emits} · points: {points}",
                "",
                "## Reasons",
                "",
                *[f"- {r}" for r in reasons],
                "",
                "Research only — not financial advice.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    log.info(
        "ltr_ship_done",
        promoted=promoted,
        challenger_id=challenger_id,
        emits=emits,
        gated_hit=metrics.gated_hit,
        rank_ic=metrics.mean_rank_ic,
    )
    return result


__all__ = [
    "LTR_GATED_VERSION",
    "LTR_GATE_NAME",
    "LtrShipResult",
    "build_ltr_panels",
    "evaluate_ltr_oos",
    "ship_ltr_serve",
    "write_ltr_gated_forecasts",
    "predict_rank_scores",
    "predict_vol_scores",
]
