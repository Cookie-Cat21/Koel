"""Learn-to-rank + dual-target (direction vs volatility) research harness.

Judges by mean daily RankIC and top/bottom quintile spread — not hit rate.
Also runs label-horizon and liquidity×turnover regime probes.

Research only — not financial advice. Flag-gated via CLI ``ml-ltr-dual``.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from koel.logging_setup import get_logger
from koel.ml import sklearn_available
from koel.ml.dataset import Sample, build_samples, load_symbol_bars
from koel.ml.features import FEATURE_NAMES
from koel.ml.harden import _demean_by_day, _purge_train
from koel.ml.iterate import _enrich_cross_section
from koel.ml.metrics import mean_daily_rank_ic, spearman
from koel.ml.walkforward import _unique_sorted_dates
from koel.storage import Storage

log = get_logger(__name__)

IDX_TURN = FEATURE_NAMES.index("turnover_20d")
IDX_VOL = FEATURE_NAMES.index("vol_20d")
IDX_SPIKE = FEATURE_NAMES.index("vol_spike")
IDX_LIQ = FEATURE_NAMES.index("liquidity_20d")


@dataclass(frozen=True, slots=True)
class RankMetrics:
    model_id: str
    target: str  # ret | abs_ret | dir
    horizon: int
    origins: int
    folds: int
    mean_rank_ic: float | None
    rank_ic_days: int
    pooled_ic: float | None
    top_bottom_spread: float | None  # mean daily top20% − bottom20% realized ret
    hit_rate: float | None  # optional; not the promote metric
    big_move_precision: float | None  # for vol target: P(actual top-q | pred top-q)
    notes: str = ""


@dataclass
class LtrDualResult:
    decision: str
    reasons: list[str] = field(default_factory=list)
    cse_symbols: int = 0
    bars: int = 0
    metrics: list[RankMetrics] = field(default_factory=list)
    label_probe: list[dict[str, Any]] = field(default_factory=list)
    liq_regime: list[dict[str, Any]] = field(default_factory=list)
    accrual: dict[str, Any] = field(default_factory=dict)
    notice_yoy: dict[str, Any] = field(default_factory=dict)
    macros: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "cse_symbols": self.cse_symbols,
            "bars": self.bars,
            "metrics": [asdict(m) for m in self.metrics],
            "label_probe": list(self.label_probe),
            "liq_regime": list(self.liq_regime),
            "accrual": dict(self.accrual),
            "notice_yoy": dict(self.notice_yoy),
            "macros": dict(self.macros),
        }


def _xgboost_available() -> bool:
    try:
        import xgboost  # noqa: F401
    except ImportError:
        return False
    return True


def _lightgbm_available() -> bool:
    try:
        import lightgbm  # noqa: F401
    except ImportError:
        return False
    return True


def _fill_nan(x_train: Any, x_test: Any) -> tuple[Any, Any]:
    import numpy as np

    col_med = np.nanmedian(x_train, axis=0)
    col_med = np.where(np.isnan(col_med), 0.0, col_med)
    for arr in (x_train, x_test):
        inds = np.where(np.isnan(arr))
        arr[inds] = np.take(col_med, inds[1])
    return x_train, x_test


def _drop_constant_cols(x_train: Any, x_test: Any) -> tuple[Any, Any]:
    """Drop columns with <2 distinct finite values (breaks HGB binning)."""
    import numpy as np

    keep: list[int] = []
    for j in range(x_train.shape[1]):
        col = x_train[:, j]
        finite = col[np.isfinite(col)]
        if finite.size == 0:
            continue
        if np.unique(finite).size >= 2:
            keep.append(j)
    if not keep:
        # Degenerate — keep first column as zeros so estimators can run.
        z_tr = np.zeros((x_train.shape[0], 1), dtype=float)
        z_te = np.zeros((x_test.shape[0], 1), dtype=float)
        return z_tr, z_te
    return x_train[:, keep], x_test[:, keep]


def _group_sizes(samples: list[Sample]) -> list[int]:
    """Contiguous group sizes assuming samples sorted by as_of then symbol."""
    if not samples:
        return []
    sizes: list[int] = []
    cur = samples[0].as_of
    n = 0
    for s in samples:
        if s.as_of != cur:
            sizes.append(n)
            cur = s.as_of
            n = 0
        n += 1
    sizes.append(n)
    return sizes


def _sort_by_day(samples: list[Sample]) -> list[Sample]:
    return sorted(samples, key=lambda s: (s.as_of, s.symbol))


def _relevance_from_returns(day_samples: list[Sample], *, buckets: int = 5) -> list[float]:
    """Map within-day return rank to integer relevance 0..buckets-1."""
    ordered = sorted(range(len(day_samples)), key=lambda i: day_samples[i].y_ret)
    n = len(ordered)
    rel = [0.0] * n
    if n < 2:
        return rel
    for rank, i in enumerate(ordered):
        # Higher return → higher relevance
        frac = rank / (n - 1)
        rel[i] = float(min(buckets - 1, int(frac * buckets)))
    return rel


def _top_bottom_spread(
    as_of: list[date],
    preds: list[float],
    actuals: list[float],
    *,
    frac: float = 0.2,
    min_names: int = 10,
) -> float | None:
    by_day: dict[date, list[tuple[float, float]]] = defaultdict(list)
    for d, p, a in zip(as_of, preds, actuals, strict=True):
        if math.isfinite(p) and math.isfinite(a):
            by_day[d].append((p, a))
    spreads: list[float] = []
    for pairs in by_day.values():
        if len(pairs) < min_names:
            continue
        ordered = sorted(pairs, key=lambda t: t[0])
        k = max(1, int(len(ordered) * frac))
        bottom = ordered[:k]
        top = ordered[-k:]
        spreads.append(
            sum(a for _, a in top) / len(top) - sum(a for _, a in bottom) / len(bottom)
        )
    if not spreads:
        return None
    return sum(spreads) / len(spreads)


def _big_move_precision(
    as_of: list[date],
    preds: list[float],
    actuals: list[float],
    *,
    frac: float = 0.25,
    min_names: int = 10,
) -> float | None:
    """Share of predicted top-frac abs-move names that are also actual top-frac."""
    by_day: dict[date, list[tuple[float, float]]] = defaultdict(list)
    for d, p, a in zip(as_of, preds, actuals, strict=True):
        if math.isfinite(p) and math.isfinite(a):
            by_day[d].append((p, a))
    hits = 0
    total = 0
    for pairs in by_day.values():
        if len(pairs) < min_names:
            continue
        k = max(1, int(len(pairs) * frac))
        pred_top = {i for i, _ in sorted(enumerate(pairs), key=lambda t: t[1][0])[-k:]}
        act_top = {i for i, _ in sorted(enumerate(pairs), key=lambda t: t[1][1])[-k:]}
        total += len(pred_top)
        hits += len(pred_top & act_top)
    if total == 0:
        return None
    return hits / total


def _direction_hit(y_dir: list[float], scores: list[float]) -> float | None:
    hits = 0
    total = 0
    for yd, sc in zip(y_dir, scores, strict=True):
        if yd == 0 or sc == 0 or not math.isfinite(sc):
            continue
        pred = 1.0 if sc > 0 else -1.0
        total += 1
        if (yd > 0 and pred > 0) or (yd < 0 and pred < 0):
            hits += 1
    return hits / total if total else None


def _predict_hgb_reg(train: list[Sample], test: list[Sample], *, y_fn: Callable) -> list[float]:
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor

    x_train = np.asarray([s.x for s in train], dtype=float).copy()
    x_test = np.asarray([s.x for s in test], dtype=float).copy()
    x_train, x_test = _fill_nan(x_train, x_test)
    x_train, x_test = _drop_constant_cols(x_train, x_test)
    y = np.asarray([y_fn(s) for s in train], dtype=float)
    reg = HistGradientBoostingRegressor(max_depth=4, max_iter=120, learning_rate=0.08)
    reg.fit(x_train, y)
    return [float(v) for v in reg.predict(x_test)]


def _predict_hgb_clf(train: list[Sample], test: list[Sample]) -> list[float]:
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier

    x_train = np.asarray([s.x for s in train], dtype=float).copy()
    x_test = np.asarray([s.x for s in test], dtype=float).copy()
    x_train, x_test = _fill_nan(x_train, x_test)
    x_train, x_test = _drop_constant_cols(x_train, x_test)
    y = np.asarray([1 if s.y_dir > 0 else 0 for s in train])
    clf = HistGradientBoostingClassifier(max_depth=4, max_iter=100, learning_rate=0.08)
    clf.fit(x_train, y)
    proba = clf.predict_proba(x_test)[:, 1]
    return [float(p - 0.5) for p in proba]


def _predict_xgb_rank(train: list[Sample], test: list[Sample], *, objective: str) -> list[float]:
    import numpy as np
    import xgboost as xgb

    train_s = _sort_by_day(train)
    test_s = _sort_by_day(test)
    # Drop days with < 3 names (ranking needs a group)
    def filter_days(rows: list[Sample]) -> list[Sample]:
        by: dict[date, list[Sample]] = defaultdict(list)
        for s in rows:
            by[s.as_of].append(s)
        out: list[Sample] = []
        for day in sorted(by):
            if len(by[day]) >= 3:
                out.extend(sorted(by[day], key=lambda s: s.symbol))
        return out

    train_s = filter_days(train_s)
    test_s = filter_days(test_s)
    if len(train_s) < 50 or len(test_s) < 10:
        raise ValueError("insufficient ranking groups")

    x_train = np.asarray([s.x for s in train_s], dtype=float).copy()
    x_test = np.asarray([s.x for s in test_s], dtype=float).copy()
    x_train, x_test = _fill_nan(x_train, x_test)

    y_list: list[float] = []
    by_tr: dict[date, list[Sample]] = defaultdict(list)
    for s in train_s:
        by_tr[s.as_of].append(s)
    for day in sorted(by_tr):
        day_s = by_tr[day]
        y_list.extend(_relevance_from_returns(day_s))
    y = np.asarray(y_list, dtype=float)
    group_train = _group_sizes(train_s)
    group_test = _group_sizes(test_s)

    dtrain = xgb.DMatrix(x_train, label=y)
    dtrain.set_group(group_train)
    dtest = xgb.DMatrix(x_test)
    dtest.set_group(group_test)
    params = {
        "objective": objective,
        "eval_metric": "ndcg",
        "max_depth": 4,
        "eta": 0.08,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 20,
        "verbosity": 0,
    }
    booster = xgb.train(params, dtrain, num_boost_round=80)
    pred_by_key = {
        (s.symbol, s.as_of): float(p)
        for s, p in zip(test_s, booster.predict(dtest), strict=True)
    }
    # Align to original test order
    out: list[float] = []
    for s in test:
        out.append(pred_by_key.get((s.symbol, s.as_of), float("nan")))
    return out


def _predict_lgb_rank(train: list[Sample], test: list[Sample]) -> list[float]:
    import lightgbm as lgb
    import numpy as np

    train_s = _sort_by_day(train)
    test_s = _sort_by_day(test)

    def filter_days(rows: list[Sample]) -> list[Sample]:
        by: dict[date, list[Sample]] = defaultdict(list)
        for s in rows:
            by[s.as_of].append(s)
        out: list[Sample] = []
        for day in sorted(by):
            if len(by[day]) >= 3:
                out.extend(sorted(by[day], key=lambda s: s.symbol))
        return out

    train_s = filter_days(train_s)
    test_s = filter_days(test_s)
    if len(train_s) < 50 or len(test_s) < 10:
        raise ValueError("insufficient ranking groups")

    x_train = np.asarray([s.x for s in train_s], dtype=float).copy()
    x_test = np.asarray([s.x for s in test_s], dtype=float).copy()
    x_train, x_test = _fill_nan(x_train, x_test)

    y_list: list[float] = []
    by_tr: dict[date, list[Sample]] = defaultdict(list)
    for s in train_s:
        by_tr[s.as_of].append(s)
    for day in sorted(by_tr):
        y_list.extend(_relevance_from_returns(by_tr[day]))
    y = np.asarray(y_list, dtype=float)
    group_train = _group_sizes(train_s)

    dtrain = lgb.Dataset(x_train, label=y, group=group_train)
    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [5, 10],
        "learning_rate": 0.08,
        "num_leaves": 31,
        "min_data_in_leaf": 40,
        "verbosity": -1,
        "label_gain": list(range(5)),
    }
    booster = lgb.train(params, dtrain, num_boost_round=80)
    pred_by_key = {
        (s.symbol, s.as_of): float(p)
        for s, p in zip(test_s, booster.predict(x_test), strict=True)
    }
    return [pred_by_key.get((s.symbol, s.as_of), float("nan")) for s in test]


def _enrich_liq_sentiment(samples: list[Sample]) -> list[Sample]:
    """Append CS turnover percentile, illiquidity proxy, and turnover×vol interactions."""
    by_day: dict[date, list[Sample]] = defaultdict(list)
    for s in samples:
        by_day[s.as_of].append(s)
    out: list[Sample] = []
    for day_samples in by_day.values():
        turns = [
            (s.symbol, s.x[IDX_TURN])
            for s in day_samples
            if math.isfinite(s.x[IDX_TURN])
        ]
        ordered = sorted(turns, key=lambda t: t[1])
        n = len(ordered)
        pct = {
            sym: (i / (n - 1) if n > 1 else 0.5)
            for i, (sym, _) in enumerate(ordered)
        }
        for s in day_samples:
            t_pct = pct.get(s.symbol, float("nan"))
            vol = s.x[IDX_VOL]
            spike = s.x[IDX_SPIKE]
            liq = s.x[IDX_LIQ]
            # Amihud-ish: |ret_1d| / liquidity (liquidity already in features as volume)
            ret1 = s.x[FEATURE_NAMES.index("ret_1d")]
            illiq = (
                abs(ret1) / liq
                if math.isfinite(ret1) and math.isfinite(liq) and liq > 0
                else float("nan")
            )
            turn_x_vol = (
                t_pct * vol
                if math.isfinite(t_pct) and math.isfinite(vol)
                else float("nan")
            )
            turn_x_spike = (
                t_pct * spike
                if math.isfinite(t_pct) and math.isfinite(spike)
                else float("nan")
            )
            out.append(
                Sample(
                    symbol=s.symbol,
                    as_of=s.as_of,
                    x=tuple(s.x) + (t_pct, illiq, turn_x_vol, turn_x_spike),
                    y_ret=s.y_ret,
                    y_dir=s.y_dir,
                    horizon=s.horizon,
                )
            )
    return out


def _filter_large_move(samples: list[Sample], *, min_abs: float | None = None) -> list[Sample]:
    """Keep samples with |y_ret| ≥ day-median |y_ret| (or absolute floor)."""
    by_day: dict[date, list[Sample]] = defaultdict(list)
    for s in samples:
        by_day[s.as_of].append(s)
    out: list[Sample] = []
    for day_samples in by_day.values():
        abs_rets = sorted(abs(s.y_ret) for s in day_samples)
        if not abs_rets:
            continue
        med = abs_rets[len(abs_rets) // 2]
        thr = med if min_abs is None else max(med, min_abs)
        for s in day_samples:
            if abs(s.y_ret) >= thr:
                out.append(s)
    return out


def run_rank_walkforward(
    samples: list[Sample],
    *,
    model_id: str,
    target: str,
    horizon: int,
    min_train_days: int = 80,
    fold_step: int = 10,
    embargo: int = 2,
) -> RankMetrics:
    dates = _unique_sorted_dates(samples)
    if len(dates) < min_train_days + fold_step:
        return RankMetrics(
            model_id=model_id,
            target=target,
            horizon=horizon,
            origins=0,
            folds=0,
            mean_rank_ic=None,
            rank_ic_days=0,
            pooled_ic=None,
            top_bottom_spread=None,
            hit_rate=None,
            big_move_precision=None,
            notes="insufficient dates",
        )

    def y_fn(s: Sample) -> float:
        if target == "abs_ret":
            return abs(s.y_ret)
        return s.y_ret

    all_as_of: list[date] = []
    all_pred: list[float] = []
    all_actual: list[float] = []
    all_y_dir: list[float] = []
    folds = 0
    origins = 0
    notes_parts: list[str] = []

    cut = min_train_days
    while cut + fold_step <= len(dates):
        test_dates = set(dates[cut : cut + fold_step])
        train = _purge_train(
            samples, dates=dates, cut=cut, horizon=horizon, embargo=embargo
        )
        test = [s for s in samples if s.as_of in test_dates]
        cut += fold_step
        if len(train) < 80 or len(test) < 15:
            continue
        try:
            if model_id == "hgb_reg":
                preds = _predict_hgb_reg(train, test, y_fn=y_fn)
            elif model_id == "hgb_clf" and target == "ret":
                preds = _predict_hgb_clf(train, test)
            elif model_id == "xgb_pairwise" and target == "ret":
                preds = _predict_xgb_rank(train, test, objective="rank:pairwise")
            elif model_id == "xgb_ndcg" and target == "ret":
                preds = _predict_xgb_rank(train, test, objective="rank:ndcg")
            elif model_id == "lgb_lambdarank" and target == "ret":
                preds = _predict_lgb_rank(train, test)
            elif model_id == "hgb_vol" and target == "abs_ret":
                preds = _predict_hgb_reg(train, test, y_fn=y_fn)
            else:
                notes_parts.append(f"skip {model_id}/{target}")
                continue
        except Exception as exc:
            log.warning(
                "ltr_fold_failed",
                model_id=model_id,
                target=target,
                horizon=horizon,
                error=str(exc),
            )
            notes_parts.append(str(exc)[:80])
            continue
        folds += 1
        origins += len(test)
        for s, p in zip(test, preds, strict=True):
            if not math.isfinite(p):
                continue
            all_as_of.append(s.as_of)
            all_pred.append(p)
            all_actual.append(y_fn(s) if target == "abs_ret" else s.y_ret)
            all_y_dir.append(s.y_dir)

    if not all_pred:
        return RankMetrics(
            model_id=model_id,
            target=target,
            horizon=horizon,
            origins=origins,
            folds=folds,
            mean_rank_ic=None,
            rank_ic_days=0,
            pooled_ic=None,
            top_bottom_spread=None,
            hit_rate=None,
            big_move_precision=None,
            notes="; ".join(notes_parts) or "no preds",
        )

    rank_ic, rank_days = mean_daily_rank_ic(all_as_of, all_pred, all_actual)
    pooled = spearman(all_pred, all_actual)
    spread = _top_bottom_spread(all_as_of, all_pred, all_actual)
    hit = _direction_hit(all_y_dir, all_pred) if target == "ret" else None
    bmp = (
        _big_move_precision(all_as_of, all_pred, all_actual)
        if target == "abs_ret"
        else None
    )
    return RankMetrics(
        model_id=model_id,
        target=target,
        horizon=horizon,
        origins=origins,
        folds=folds,
        mean_rank_ic=rank_ic,
        rank_ic_days=rank_days,
        pooled_ic=pooled,
        top_bottom_spread=spread,
        hit_rate=hit,
        big_move_precision=bmp,
        notes="; ".join(notes_parts),
    )


def _label_horizon_probe(
    series: dict, *, horizons: tuple[int, ...] = (1, 2, 5, 10)
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for h in horizons:
        samples = _enrich_liq_sentiment(
            _enrich_cross_section(_demean_by_day(build_samples(series, horizon=h)))
        )
        full = run_rank_walkforward(
            samples, model_id="hgb_reg", target="ret", horizon=h
        )
        lmt_samples = _filter_large_move(samples)
        lmt = run_rank_walkforward(
            lmt_samples, model_id="hgb_reg", target="ret", horizon=h
        )
        # Train on large-move only, eval on full panel (same dates via walkforward on full)
        # Approximate: report LMT-only RankIC separately.
        rows.append(
            {
                "horizon": h,
                "full_rank_ic": full.mean_rank_ic,
                "full_spread": full.top_bottom_spread,
                "full_hit": full.hit_rate,
                "lmt_rank_ic": lmt.mean_rank_ic,
                "lmt_spread": lmt.top_bottom_spread,
                "lmt_hit": lmt.hit_rate,
                "lmt_origins": lmt.origins,
                "full_origins": full.origins,
            }
        )
    return rows


def _liq_regime_probe(samples: list[Sample]) -> list[dict[str, Any]]:
    """Split OOS by turnover CS tercile; compare HGB vs LTR RankIC within regime."""
    # Tag each sample with turnover CS percentile (last feature of enrich)
    # After enrich_liq_sentiment, index -4 is t_pct
    if not samples or len(samples[0].x) < len(FEATURE_NAMES) + 4:
        return [{"error": "liq features missing"}]

    t_idx = len(FEATURE_NAMES)  # first extra from _enrich_liq_sentiment when after CS
    # samples already have CS (3) + liq (4) extras → t_pct at len(FEATURE_NAMES)+3
    # Order: path | cs_ret1,cs_ret5,cs_vol | t_pct,illiq,turn_x_vol,turn_x_spike
    t_idx = len(FEATURE_NAMES) + 3

    def regime_of(s: Sample) -> str:
        t = s.x[t_idx] if len(s.x) > t_idx else float("nan")
        if not math.isfinite(t):
            return "unknown"
        if t < 1 / 3:
            return "low_turnover"
        if t < 2 / 3:
            return "mid_turnover"
        return "high_turnover"

    rows: list[dict[str, Any]] = []
    for model_id in ("hgb_reg", "lgb_lambdarank"):
        if model_id == "lgb_lambdarank" and not _lightgbm_available():
            continue
        # Walk once, then bucket OOS by regime
        dates = _unique_sorted_dates(samples)
        min_train_days = 80
        fold_step = 10
        by_reg: dict[str, dict[str, list]] = defaultdict(
            lambda: {"as_of": [], "pred": [], "actual": []}
        )
        cut = min_train_days
        while cut + fold_step <= len(dates):
            test_dates = set(dates[cut : cut + fold_step])
            train = _purge_train(
                samples, dates=dates, cut=cut, horizon=1, embargo=2
            )
            test = [s for s in samples if s.as_of in test_dates]
            cut += fold_step
            if len(train) < 80 or len(test) < 15:
                continue
            try:
                if model_id == "hgb_reg":
                    preds = _predict_hgb_reg(train, test, y_fn=lambda s: s.y_ret)
                else:
                    preds = _predict_lgb_rank(train, test)
            except Exception:
                continue
            for s, p in zip(test, preds, strict=True):
                if not math.isfinite(p):
                    continue
                reg = regime_of(s)
                by_reg[reg]["as_of"].append(s.as_of)
                by_reg[reg]["pred"].append(p)
                by_reg[reg]["actual"].append(s.y_ret)
        for reg, b in sorted(by_reg.items()):
            ric, days = mean_daily_rank_ic(b["as_of"], b["pred"], b["actual"])
            spread = _top_bottom_spread(b["as_of"], b["pred"], b["actual"], min_names=5)
            rows.append(
                {
                    "model_id": model_id,
                    "regime": reg,
                    "n": len(b["pred"]),
                    "rank_ic": ric,
                    "rank_ic_days": days,
                    "top_bottom_spread": spread,
                }
            )
    return rows


async def _accrual_status(storage: Storage) -> dict[str, Any]:
    mkt = await storage.list_market_daily_summary()
    async with storage._pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT count(*) AS n,
                       count(DISTINCT symbol) AS syms,
                       min(ts) AS first_ts,
                       max(ts) AS last_ts
                FROM order_book_snapshots
                """
        )
        ob = dict(await cur.fetchone())
    return {
        "market_daily_summary_rows": len(mkt),
        "market_daily_summary_ready_for_b002": len(mkt) >= 60,
        "order_book_snapshots": ob.get("n"),
        "order_book_symbols": ob.get("syms"),
        "order_book_first_ts": str(ob.get("first_ts")) if ob.get("first_ts") else None,
        "order_book_last_ts": str(ob.get("last_ts")) if ob.get("last_ts") else None,
        "b001_status": "OPEN_ACCRUING" if (ob.get("n") or 0) > 0 else "OPEN_EMPTY",
        "b002_status": "OPEN" if len(mkt) >= 60 else "BLOCKED_ACCRUING",
        "b011_note": (
            "poller/ml-loop-nightly upserts dailyMarketSummery; "
            "API still ~2 live sessions"
        ),
    }


async def _notice_yoy_status(storage: Storage) -> dict[str, Any]:
    async with storage._pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT notice_type,
                       count(*) AS n,
                       count(symbol) AS with_sym
                FROM market_notices
                GROUP BY 1
                """
        )
        notices = [dict(r) for r in await cur.fetchall()]
        await cur.execute("SELECT count(*) AS n FROM filing_comparisons")
        yoy_n = int((await cur.fetchone())["n"])
        await cur.execute("SELECT count(*) AS n FROM filing_metrics")
        metrics_n = int((await cur.fetchone())["n"])
    buy_in = next((r for r in notices if r["notice_type"] == "buy_in"), None)
    return {
        "notices_by_type": notices,
        "buy_in_resolved": (buy_in or {}).get("with_sym", 0),
        "buy_in_total": (buy_in or {}).get("n", 0),
        "buy_in_blocker": (
            "CSE buy-in board rows expose company='TRADING AND MARKET SURVEILLANCE' "
            "with no symbol/issuer field — PDF/detail scrape needed; exact name match "
            "cannot resolve"
        ),
        "filing_comparisons": yoy_n,
        "filing_metrics": metrics_n,
        "yoy_status": "UNDERPOWERED" if yoy_n < 100 else "USABLE",
    }


def _decide(
    metrics: list[RankMetrics], label_probe: list[dict[str, Any]]
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    best_ltr = None
    best_base = None
    best_clf = None
    best_vol = None
    for m in metrics:
        if m.mean_rank_ic is None:
            continue
        is_ltr = (
            m.model_id in {"xgb_pairwise", "xgb_ndcg", "lgb_lambdarank"}
            and m.target == "ret"
        )
        if is_ltr and (
            best_ltr is None or m.mean_rank_ic > (best_ltr.mean_rank_ic or -1)
        ):
            best_ltr = m
        if m.model_id == "hgb_reg" and m.target == "ret" and m.horizon == 1:
            best_base = m
        if m.model_id == "hgb_clf" and m.target == "ret" and m.horizon == 1:
            best_clf = m
        if m.target == "abs_ret" and (
            best_vol is None or (m.mean_rank_ic > (best_vol.mean_rank_ic or -1))
        ):
            best_vol = m

    decision = "UNCLEAR"
    ltr_ic = best_ltr.mean_rank_ic if best_ltr else None
    base_ic = best_base.mean_rank_ic if best_base else None
    if best_ltr and best_base and ltr_ic is not None and base_ic is not None:
        delta = ltr_ic - base_ic
        clf_note = ""
        if best_clf and best_clf.mean_rank_ic is not None:
            clf_note = f"; hgb_clf RankIC={best_clf.mean_rank_ic:.4f}"
        reasons.append(
            f"LTR best {best_ltr.model_id} RankIC={ltr_ic:.4f} "
            f"spread={best_ltr.top_bottom_spread}; "
            f"HGB reg RankIC={base_ic:.4f} (Δ={delta:+.4f}){clf_note}"
        )
        if delta >= 0.01 and ltr_ic >= 0.03:
            decision = "GO_LTR"
        elif ltr_ic >= 0.03:
            decision = "KEEP_PARTIAL_LTR"
        else:
            decision = "NO-GO_LTR"
    elif best_ltr:
        reasons.append(
            f"LTR {best_ltr.model_id} RankIC={best_ltr.mean_rank_ic} "
            f"(no baseline compare)"
        )

    if best_vol and best_vol.mean_rank_ic is not None:
        reasons.append(
            f"Vol target best RankIC={best_vol.mean_rank_ic:.4f} "
            f"big_move_P={best_vol.big_move_precision} "
            f"model={best_vol.model_id}"
        )
        if best_vol.mean_rank_ic >= 0.05:
            if decision.startswith("NO-GO") or decision == "UNCLEAR":
                decision = "GO_VOL"
            else:
                decision = decision + "+VOL"
        else:
            reasons.append(
                "Vol RankIC below 0.05 — useful only as weak sizing prior"
            )

    # Label probe: prefer horizon with best RankIC
    best_h = None
    for row in label_probe:
        ric = row.get("full_rank_ic")
        if ric is None:
            continue
        if best_h is None or ric > best_h["full_rank_ic"]:
            best_h = row
    if best_h:
        reasons.append(
            f"Best label horizon h={best_h['horizon']} "
            f"RankIC={best_h['full_rank_ic']:.4f} "
            f"LMT RankIC={best_h.get('lmt_rank_ic')}"
        )
    return decision, reasons


def _write_report(result: LtrDualResult, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    md_path = out_dir / f"ml_ltr_dual_{ts}.md"
    json_path = out_dir / f"ml_ltr_dual_{ts}.json"
    json_path.write_text(json.dumps(result.as_dict(), indent=2, default=str), encoding="utf-8")

    lines = [
        f"# Learn-to-rank + dual-target probe ({ts})",
        "",
        f"**Decision:** `{result.decision}`",
        "",
        f"Symbols={result.cse_symbols} bars={result.bars}",
        "",
        "## Reasons",
        "",
    ]
    for r in result.reasons:
        lines.append(f"- {r}")
    lines += ["", "## Rank metrics (primary: RankIC + top/bottom spread)", ""]
    lines.append(
        "| Model | Target | H | RankIC | Days | Spread | Hit | BigMoveP | Origins |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for m in result.metrics:
        lines.append(
            f"| {m.model_id} | {m.target} | {m.horizon} | "
            f"{m.mean_rank_ic if m.mean_rank_ic is not None else '—'} | "
            f"{m.rank_ic_days} | "
            f"{m.top_bottom_spread if m.top_bottom_spread is not None else '—'} | "
            f"{m.hit_rate if m.hit_rate is not None else '—'} | "
            f"{m.big_move_precision if m.big_move_precision is not None else '—'} | "
            f"{m.origins} |"
        )
    lines += ["", "## Label horizon + large-move probe", ""]
    lines.append("| H | Full RankIC | Full spread | LMT RankIC | LMT hit |")
    lines.append("|---:|---:|---:|---:|---:|")
    for row in result.label_probe:
        lines.append(
            f"| {row.get('horizon')} | {row.get('full_rank_ic')} | "
            f"{row.get('full_spread')} | {row.get('lmt_rank_ic')} | "
            f"{row.get('lmt_hit')} |"
        )
    lines += ["", "## Liquidity × turnover regimes", ""]
    lines.append("| Model | Regime | N | RankIC | Spread |")
    lines.append("|---|---|---:|---:|---:|")
    for row in result.liq_regime:
        if "error" in row:
            lines.append(f"| — | error | — | {row['error']} | — |")
            continue
        lines.append(
            f"| {row.get('model_id')} | {row.get('regime')} | {row.get('n')} | "
            f"{row.get('rank_ic')} | {row.get('top_bottom_spread')} |"
        )
    lines += [
        "",
        "## Accrual / notices / macros",
        "",
        "```json",
        json.dumps(
            {
                "accrual": result.accrual,
                "notice_yoy": result.notice_yoy,
                "macros": result.macros,
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "Research only — not financial advice.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    # Also refresh a stable summary pointer
    summary = out_dir / "ML_LTR_DUAL_SUMMARY.md"
    summary.write_text(
        "\n".join(
            [
                "# ML LTR + dual-target summary",
                "",
                f"Latest run: `{md_path.name}`",
                "",
                f"**Decision:** `{result.decision}`",
                "",
                *[f"- {r}" for r in result.reasons],
                "",
                "Promote gate for ranking: mean RankIC ≥ 0.03 and "
                "LTR Δ vs HGB reg ≥ +0.01 → GO_LTR.",
                "",
                "Research only — not financial advice.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return md_path, json_path


async def run_ltr_dual_experiment(
    storage: Storage,
    *,
    limit_symbols: int | None = None,
    out_dir: Path | None = None,
) -> LtrDualResult:
    if not sklearn_available():
        return LtrDualResult(
            decision="BLOCKED",
            reasons=["scikit-learn/numpy not installed (pip install -e '.[ml]')"],
        )

    series = await load_symbol_bars(storage, limit_symbols=limit_symbols)
    n_bars = sum(len(v) for v in series.values())
    result = LtrDualResult(decision="UNCLEAR", cse_symbols=len(series), bars=n_bars)
    result.accrual = await _accrual_status(storage)
    result.notice_yoy = await _notice_yoy_status(storage)
    result.macros = {
        "status": "DEFERRED",
        "ref": "docs/THIRD_PARTY_DATA.md",
        "note": (
            "ASPI/index-level macros + news sentiment (ICARC-style) not wired; "
            "weak for per-name next-day; candidate regime gate only after ToS checklist"
        ),
    }

    if len(series) < 20:
        result.decision = "BLOCKED"
        result.reasons.append("need ≥20 symbols with daily_bars (run path-backfill)")
        if out_dir:
            _write_report(result, out_dir)
        return result

    # Core panel h=1 with CS + liq×sentiment features
    base = _enrich_liq_sentiment(
        _enrich_cross_section(_demean_by_day(build_samples(series, horizon=1)))
    )

    model_specs: list[tuple[str, str]] = [
        ("hgb_reg", "ret"),
        ("hgb_clf", "ret"),
        ("hgb_vol", "abs_ret"),
    ]
    if _xgboost_available():
        model_specs.extend([("xgb_pairwise", "ret"), ("xgb_ndcg", "ret")])
    else:
        result.reasons.append("xgboost missing — skipped xgb LTR")
    if _lightgbm_available():
        model_specs.append(("lgb_lambdarank", "ret"))
    else:
        result.reasons.append("lightgbm missing — skipped lgb LTR")

    for model_id, target in model_specs:
        m = run_rank_walkforward(
            base, model_id=model_id, target=target, horizon=1
        )
        result.metrics.append(m)
        log.info(
            "ltr_metric",
            model_id=model_id,
            target=target,
            rank_ic=m.mean_rank_ic,
            spread=m.top_bottom_spread,
        )

    # Also vol on h=5 abs return
    samples_h5 = _enrich_liq_sentiment(
        _enrich_cross_section(_demean_by_day(build_samples(series, horizon=5)))
    )
    result.metrics.append(
        run_rank_walkforward(
            samples_h5, model_id="hgb_vol", target="abs_ret", horizon=5
        )
    )
    result.metrics.append(
        run_rank_walkforward(
            samples_h5, model_id="hgb_reg", target="ret", horizon=5
        )
    )
    if _lightgbm_available():
        result.metrics.append(
            run_rank_walkforward(
                samples_h5, model_id="lgb_lambdarank", target="ret", horizon=5
            )
        )

    result.label_probe = _label_horizon_probe(series)
    result.liq_regime = _liq_regime_probe(base)

    decision, reasons = _decide(result.metrics, result.label_probe)
    result.decision = decision
    result.reasons = reasons + result.reasons

    # Accrual / notice notes into reasons
    result.reasons.append(
        f"Accrual: market_summary={result.accrual.get('market_daily_summary_rows')} "
        f"order_book_n={result.accrual.get('order_book_snapshots')} "
        f"({result.accrual.get('b002_status')})"
    )
    result.reasons.append(
        f"Notices: buy_in resolved "
        f"{result.notice_yoy.get('buy_in_resolved')}/"
        f"{result.notice_yoy.get('buy_in_total')}; "
        f"YoY comparisons={result.notice_yoy.get('filing_comparisons')} "
        f"({result.notice_yoy.get('yoy_status')})"
    )
    result.reasons.append(f"Macros: {result.macros.get('status')}")

    if out_dir is not None:
        md, js = _write_report(result, out_dir)
        log.info("ltr_dual_report", md=str(md), json=str(js))
    return result
