"""Train horizon regressors and write ``forecast_points`` (flag-gated).

Uses HistGradientBoostingRegressor per horizon (best IC family in the
walk-forward experiment). Retrains from ``daily_bars`` each run — no pickle
registry in v1. Model version tag: ``ml_hgb_ret_v1``.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, timedelta

from koel.domain import DailyBar, ForecastPoint
from koel.logging_setup import get_logger
from koel.ml import sklearn_available
from koel.ml.dataset import build_samples, load_symbol_bars
from koel.ml.features import path_features
from koel.storage import Storage

log = get_logger(__name__)

ML_FORECAST_MODEL_VERSION = "ml_hgb_ret_v1"
DEFAULT_HORIZONS = (1, 2, 3, 4, 5)


@dataclass(frozen=True, slots=True)
class MlForecastResult:
    symbols_targeted: int
    symbols_ok: int
    symbols_skipped: int
    points_written: int
    model_version: str
    horizons: tuple[int, ...]


def _train_horizon_models(
    series: dict[str, list[DailyBar]],
    *,
    horizons: tuple[int, ...],
    min_history: int = 60,
) -> dict[int, object]:
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor

    models: dict[int, object] = {}
    for horizon in horizons:
        samples = build_samples(
            series, horizon=horizon, min_history=min_history
        )
        if len(samples) < 100:
            log.warning(
                "ml_forecast_too_few_samples",
                horizon=horizon,
                n=len(samples),
            )
            continue
        x = np.asarray([s.x for s in samples], dtype=float)
        y = np.asarray([s.y_ret for s in samples], dtype=float)
        reg = HistGradientBoostingRegressor(max_depth=4, max_iter=100)
        reg.fit(x, y)
        models[horizon] = reg
        log.info(
            "ml_forecast_trained",
            horizon=horizon,
            samples=len(samples),
            model_version=ML_FORECAST_MODEL_VERSION,
        )
    return models


def _predict_price_path(
    bars: list[DailyBar],
    models: dict[int, object],
    *,
    horizons: tuple[int, ...],
) -> list[ForecastPoint]:
    import numpy as np

    ordered = sorted(bars, key=lambda b: b.trade_date)
    feats = path_features(ordered)
    if feats is None:
        return []
    last = ordered[-1]
    last_price = last.price
    if not math.isfinite(last_price) or last_price <= 0:
        return []
    last_ts = last.bar_ts
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=UTC)
    x = np.asarray([feats.values], dtype=float)
    out: list[ForecastPoint] = []
    for h in sorted(horizons):
        model = models.get(h)
        if model is None:
            continue
        pred_ret = float(model.predict(x)[0])
        if not math.isfinite(pred_ret):
            continue
        # Cap extreme single-horizon return predictions.
        pred_ret = max(-0.2, min(0.2, pred_ret))
        yhat = last_price * (1.0 + pred_ret)
        if not math.isfinite(yhat) or yhat <= 0:
            continue
        out.append(
            ForecastPoint(
                symbol=feats.symbol,
                as_of=feats.as_of,
                horizon_i=h,
                ts=last_ts + timedelta(days=h),
                yhat=yhat,
                model_version=ML_FORECAST_MODEL_VERSION,
            )
        )
    return out


async def write_ml_forecasts(
    *,
    storage: Storage,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    limit_symbols: int | None = None,
    min_history: int = 60,
) -> MlForecastResult:
    """Train per-horizon HGB regressors and upsert ``forecast_points``."""
    if not sklearn_available():
        log.warning("ml_forecast_sklearn_missing")
        return MlForecastResult(0, 0, 0, 0, ML_FORECAST_MODEL_VERSION, horizons)

    series = await load_symbol_bars(storage, limit_symbols=limit_symbols)
    models = _train_horizon_models(
        series, horizons=horizons, min_history=min_history
    )
    if not models:
        return MlForecastResult(
            len(series), 0, len(series), 0, ML_FORECAST_MODEL_VERSION, horizons
        )

    ok = 0
    skipped = 0
    points_n = 0
    for _symbol, bars in series.items():
        points = _predict_price_path(bars, models, horizons=horizons)
        if not points:
            skipped += 1
            continue
        points_n += await storage.replace_forecast_points(points)
        ok += 1

    result = MlForecastResult(
        symbols_targeted=len(series),
        symbols_ok=ok,
        symbols_skipped=skipped,
        points_written=points_n,
        model_version=ML_FORECAST_MODEL_VERSION,
        horizons=horizons,
    )
    log.info("ml_forecast_done", **asdict(result))
    return result
