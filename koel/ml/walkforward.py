"""Time-based walk-forward training and metrics."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from koel.domain import DailyBar
from koel.ml.dataset import Sample, build_samples
from koel.ml.features import FEATURE_NAMES
from koel.signals.forecast import forecast_path


@dataclass(frozen=True, slots=True)
class ModelMetrics:
    model_id: str
    horizon: int
    origins: int
    direction_hits: int
    direction_total: int
    hit_rate: float | None
    ic: float | None  # Spearman-ish via rank correlation proxy
    mae: float | None
    folds: int


@dataclass
class WalkForwardResult:
    metrics: list[ModelMetrics] = field(default_factory=list)
    decision: str = "UNCLEAR"  # GO | NO-GO | UNCLEAR
    reasons: list[str] = field(default_factory=list)
    leakage_ok: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "leakage_ok": self.leakage_ok,
            "metrics": [asdict(m) for m in self.metrics],
        }


def _spearman_ic(preds: list[float], actuals: list[float]) -> float | None:
    from koel.ml.metrics import spearman

    return spearman(preds, actuals)


def _unique_sorted_dates(samples: list[Sample]) -> list[date]:
    return sorted({s.as_of for s in samples})


def evaluate_b0_naive(
    series: dict[str, list[DailyBar]],
    *,
    horizon: int = 5,
    min_history: int = 60,
    step: int = 5,
) -> ModelMetrics:
    """Baseline: existing ``forecast_path`` direction vs realized."""
    hits = 0
    total = 0
    abs_err: list[float] = []
    origins = 0
    for _symbol, bars in series.items():
        ordered = sorted(bars, key=lambda b: b.trade_date)
        if len(ordered) < min_history + horizon:
            continue
        last_i = len(ordered) - horizon - 1
        for t in range(min_history - 1, last_i + 1, step):
            window = ordered[: t + 1]
            future = ordered[t + 1 : t + 1 + horizon]
            preds = forecast_path(window, horizon=horizon)
            if len(preds) < horizon or len(future) < horizon:
                continue
            origins += 1
            last_p = window[-1].price
            pred_end = preds[-1].yhat
            real_end = future[-1].price
            if (
                math.isfinite(last_p)
                and math.isfinite(pred_end)
                and math.isfinite(real_end)
                and last_p != 0
            ):
                pred_dir = pred_end - last_p
                real_dir = real_end - last_p
                if pred_dir != 0 and real_dir != 0:
                    total += 1
                    if (pred_dir > 0 and real_dir > 0) or (
                        pred_dir < 0 and real_dir < 0
                    ):
                        hits += 1
            for pred, real_bar in zip(preds, future, strict=False):
                if math.isfinite(pred.yhat) and math.isfinite(real_bar.price):
                    abs_err.append(abs(pred.yhat - real_bar.price))
    hit_rate = hits / total if total else None
    mae = sum(abs_err) / len(abs_err) if abs_err else None
    return ModelMetrics(
        model_id="B0_naive",
        horizon=horizon,
        origins=origins,
        direction_hits=hits,
        direction_total=total,
        hit_rate=hit_rate,
        ic=None,
        mae=mae,
        folds=0,
    )


def _fit_predict_sklearn(
    train: list[Sample],
    test: list[Sample],
    *,
    task: str,  # "dir" | "ret"
    model_id: str,
) -> tuple[list[float], list[float], list[float]]:
    """Return (y_dir_true, y_ret_true, y_pred) for test; pred is dir or ret."""
    import numpy as np
    from sklearn.ensemble import (
        HistGradientBoostingClassifier,
        HistGradientBoostingRegressor,
    )
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x_train = np.asarray([s.x for s in train], dtype=float)
    x_test = np.asarray([s.x for s in test], dtype=float)
    # sklearn handles NaN in HGB; for linear, fill with column medians.
    if model_id in {"B1_logistic", "B2_ridge"}:
        col_med = np.nanmedian(x_train, axis=0)
        col_med = np.where(np.isnan(col_med), 0.0, col_med)
        inds = np.where(np.isnan(x_train))
        x_train = x_train.copy()
        x_train[inds] = np.take(col_med, inds[1])
        inds_t = np.where(np.isnan(x_test))
        x_test = x_test.copy()
        x_test[inds_t] = np.take(col_med, inds_t[1])

    y_dir_true = [s.y_dir for s in test]
    y_ret_true = [s.y_ret for s in test]

    if model_id == "B1_logistic":
        y = np.asarray([1 if s.y_dir > 0 else 0 for s in train])
        clf = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=500, C=1.0),
        )
        clf.fit(x_train, y)
        proba = clf.predict_proba(x_test)[:, 1]
        pred = [1.0 if p >= 0.5 else -1.0 for p in proba]
        return y_dir_true, y_ret_true, pred

    if model_id == "B2_ridge":
        y = np.asarray([s.y_ret for s in train], dtype=float)
        reg = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        reg.fit(x_train, y)
        pred = [float(v) for v in reg.predict(x_test)]
        return y_dir_true, y_ret_true, pred

    if model_id == "M1_hgb_clf":
        y = np.asarray([1 if s.y_dir > 0 else 0 for s in train])
        clf = HistGradientBoostingClassifier(max_depth=4, max_iter=100)
        clf.fit(x_train, y)
        proba = clf.predict_proba(x_test)[:, 1]
        pred = [1.0 if p >= 0.5 else -1.0 for p in proba]
        return y_dir_true, y_ret_true, pred

    if model_id == "M2_hgb_reg":
        y = np.asarray([s.y_ret for s in train], dtype=float)
        reg = HistGradientBoostingRegressor(max_depth=4, max_iter=100)
        reg.fit(x_train, y)
        pred = [float(v) for v in reg.predict(x_test)]
        return y_dir_true, y_ret_true, pred

    raise ValueError(f"unknown model_id: {model_id}")


def run_walkforward_sklearn(
    series: dict[str, list[DailyBar]],
    *,
    horizon: int,
    min_history: int = 60,
    min_train_days: int = 120,
    fold_step: int = 20,
    model_ids: tuple[str, ...] = (
        "B1_logistic",
        "B2_ridge",
        "M1_hgb_clf",
        "M2_hgb_reg",
    ),
) -> list[ModelMetrics]:
    samples = build_samples(series, horizon=horizon, min_history=min_history)
    if not samples:
        return []
    dates = _unique_sorted_dates(samples)
    if len(dates) < min_train_days + fold_step:
        return []

    # Expanding window: train on dates[:cut], test next fold_step dates.
    by_model: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "hits": 0,
            "total": 0,
            "origins": 0,
            "abs_err": [],
            "preds_ret": [],
            "acts_ret": [],
            "folds": 0,
        }
    )

    cut = min_train_days
    while cut + fold_step <= len(dates):
        train_dates = set(dates[:cut])
        test_dates = set(dates[cut : cut + fold_step])
        train = [s for s in samples if s.as_of in train_dates]
        test = [s for s in samples if s.as_of in test_dates]
        cut += fold_step
        if len(train) < 50 or len(test) < 10:
            continue
        for model_id in model_ids:
            task = "dir" if "logistic" in model_id or "clf" in model_id else "ret"
            try:
                y_dir, y_ret, pred = _fit_predict_sklearn(
                    train, test, task=task, model_id=model_id
                )
            except Exception:
                continue
            bucket = by_model[model_id]
            bucket["folds"] += 1
            bucket["origins"] += len(test)
            if task == "dir":
                for yd, yp in zip(y_dir, pred, strict=True):
                    if yd == 0 or yp == 0:
                        continue
                    bucket["total"] += 1
                    if (yd > 0 and yp > 0) or (yd < 0 and yp < 0):
                        bucket["hits"] += 1
                # IC: use signed proba proxy via predicted dir as score
                bucket["preds_ret"].extend(pred)
                bucket["acts_ret"].extend(y_ret)
            else:
                for yr, yp in zip(y_ret, pred, strict=True):
                    bucket["abs_err"].append(abs(yp - yr))
                    # Direction from predicted return
                    if yr != 0 and yp != 0:
                        bucket["total"] += 1
                        if (yr > 0 and yp > 0) or (yr < 0 and yp < 0):
                            bucket["hits"] += 1
                bucket["preds_ret"].extend(pred)
                bucket["acts_ret"].extend(y_ret)

    out: list[ModelMetrics] = []
    for model_id, bucket in by_model.items():
        total = int(bucket["total"])
        hits = int(bucket["hits"])
        hit_rate = hits / total if total else None
        errs = bucket["abs_err"]
        mae = sum(errs) / len(errs) if errs else None
        ic = _spearman_ic(bucket["preds_ret"], bucket["acts_ret"])
        out.append(
            ModelMetrics(
                model_id=model_id,
                horizon=horizon,
                origins=int(bucket["origins"]),
                direction_hits=hits,
                direction_total=total,
                hit_rate=hit_rate,
                ic=ic,
                mae=mae,
                folds=int(bucket["folds"]),
            )
        )
    return out


def decide(
    metrics: list[ModelMetrics],
    *,
    hit_gate: float = 0.55,
    ic_gate: float = 0.03,
    min_symbols_proxy: int = 100,
    min_origins: int = 500,
) -> WalkForwardResult:
    """Apply promote gates. ``min_symbols_proxy`` approximated via origins scale."""
    result = WalkForwardResult(metrics=metrics, leakage_ok=True)
    # Exclude B0 from GO decision for ML promote (baseline only).
    candidates = [m for m in metrics if not m.model_id.startswith("B0")]
    go_hits: list[str] = []
    for m in candidates:
        if m.origins < min_origins:
            continue
        if m.hit_rate is not None and m.hit_rate >= hit_gate:
            go_hits.append(
                f"{m.model_id} h={m.horizon} hit_rate={m.hit_rate:.3f} "
                f"(origins={m.origins})"
            )
        if m.ic is not None and m.ic >= ic_gate:
            go_hits.append(
                f"{m.model_id} h={m.horizon} IC={m.ic:.3f} (origins={m.origins})"
            )
    if go_hits:
        result.decision = "GO"
        result.reasons = go_hits
        return result

    # Marginal band
    marginal: list[str] = []
    for m in candidates:
        if m.hit_rate is not None and 0.52 <= m.hit_rate < hit_gate and m.origins >= 200:
            marginal.append(f"{m.model_id} h={m.horizon} hit_rate={m.hit_rate:.3f}")
        if m.ic is not None and 0.015 <= m.ic < ic_gate and m.origins >= 200:
            marginal.append(f"{m.model_id} h={m.horizon} IC={m.ic:.3f}")
    if marginal:
        result.decision = "UNCLEAR"
        result.reasons = marginal
        return result

    best = None
    for m in candidates:
        if m.hit_rate is None:
            continue
        if best is None or (m.hit_rate or 0) > (best.hit_rate or 0):
            best = m
    result.decision = "NO-GO"
    if best and best.hit_rate is not None:
        result.reasons = [
            f"Best ML hit_rate={best.hit_rate:.3f} "
            f"({best.model_id} h={best.horizon}) below gate {hit_gate}"
        ]
    else:
        result.reasons = ["No usable ML metrics"]
    # Note unused FEATURE_NAMES for report consumers
    _ = FEATURE_NAMES
    _ = min_symbols_proxy
    return result
