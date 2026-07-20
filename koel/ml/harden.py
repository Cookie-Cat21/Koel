"""Hardened ML eval: purge/embargo, RankIC, panel demean, confidence gates."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from koel.logging_setup import get_logger
from koel.ml import sklearn_available
from koel.ml.dataset import Sample, build_samples, load_symbol_bars
from koel.ml.metrics import (
    mean_daily_rank_ic,
    spearman,
    sweep_confidence_gates,
)
from koel.ml.walkforward import (
    _fit_predict_sklearn,
    _unique_sorted_dates,
    evaluate_b0_naive,
)
from koel.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HardenedMetrics:
    model_id: str
    horizon: int
    origins: int
    direction_hits: int
    direction_total: int
    hit_rate: float | None
    pooled_ic: float | None
    mean_rank_ic: float | None
    rank_ic_days: int
    folds: int
    fold_hit_rates: tuple[float, ...]
    gated_best_hit: float | None
    gated_best_thr: float | None
    gated_best_coverage: float | None
    purged: bool


@dataclass
class HardenResult:
    decision: str
    reasons: list[str] = field(default_factory=list)
    metrics: list[HardenedMetrics] = field(default_factory=list)
    gate_tables: dict[str, list[dict[str, float | None]]] = field(default_factory=dict)
    cse_symbols: int = 0
    bars: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "cse_symbols": self.cse_symbols,
            "bars": self.bars,
            "metrics": [asdict(m) for m in self.metrics],
            "gate_tables": self.gate_tables,
        }


def _purge_train(
    samples: list[Sample],
    *,
    dates: list[date],
    cut: int,
    horizon: int,
    embargo: int,
) -> list[Sample]:
    """Train = dates before cut, minus a purge/embargo buffer.

    Drop the last ``max(horizon, embargo)`` sessions before the test cut so
    label windows that would overlap the test period never enter training.
    """
    end_exclusive = cut - max(horizon, embargo)
    if end_exclusive <= 0:
        return []
    train_dates = set(dates[:end_exclusive])
    return [s for s in samples if s.as_of in train_dates]


def _demean_by_day(samples: list[Sample]) -> list[Sample]:
    """Cross-sectional demean of y_ret within each as_of (panel target)."""
    by_day: dict[date, list[Sample]] = defaultdict(list)
    for s in samples:
        by_day[s.as_of].append(s)
    out: list[Sample] = []
    for day_samples in by_day.values():
        rets = [s.y_ret for s in day_samples]
        mean_r = sum(rets) / len(rets)
        for s in day_samples:
            demeaned = s.y_ret - mean_r
            direction = 1.0 if demeaned > 0 else -1.0 if demeaned < 0 else 0.0
            if direction == 0.0:
                continue
            out.append(
                Sample(
                    symbol=s.symbol,
                    as_of=s.as_of,
                    x=s.x,
                    y_ret=demeaned,
                    y_dir=direction,
                    horizon=s.horizon,
                )
            )
    return out


def _fit_predict_with_scores(
    train: list[Sample],
    test: list[Sample],
    *,
    model_id: str,
) -> tuple[list[float], list[float], list[float], list[float], list[date]]:
    """Return y_dir, y_ret, pred_score (signed), pred_ret_or_dir, as_of list."""
    import numpy as np
    from sklearn.ensemble import (
        HistGradientBoostingClassifier,
        HistGradientBoostingRegressor,
    )
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x_train = np.asarray([s.x for s in train], dtype=float).copy()
    x_test = np.asarray([s.x for s in test], dtype=float).copy()
    as_ofs = [s.as_of for s in test]
    y_dir = [s.y_dir for s in test]
    y_ret = [s.y_ret for s in test]

    if model_id in {"B1_logistic", "B2_ridge"}:
        col_med = np.nanmedian(x_train, axis=0)
        col_med = np.where(np.isnan(col_med), 0.0, col_med)
        for arr in (x_train, x_test):
            inds = np.where(np.isnan(arr))
            arr[inds] = np.take(col_med, inds[1])

    if model_id == "B1_logistic":
        y = np.asarray([1 if s.y_dir > 0 else 0 for s in train])
        clf = make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=500, C=1.0)
        )
        clf.fit(x_train, y)
        proba = clf.predict_proba(x_test)[:, 1]
        scores = [float(p - 0.5) for p in proba]  # signed confidence
        pred = [1.0 if s > 0 else -1.0 for s in scores]
        return y_dir, y_ret, scores, pred, as_ofs

    if model_id == "M1_hgb_clf":
        y = np.asarray([1 if s.y_dir > 0 else 0 for s in train])
        clf = HistGradientBoostingClassifier(max_depth=4, max_iter=100)
        clf.fit(x_train, y)
        proba = clf.predict_proba(x_test)[:, 1]
        scores = [float(p - 0.5) for p in proba]
        pred = [1.0 if s > 0 else -1.0 for s in scores]
        return y_dir, y_ret, scores, pred, as_ofs

    if model_id == "B2_ridge":
        y = np.asarray([s.y_ret for s in train], dtype=float)
        reg = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        reg.fit(x_train, y)
        pred_ret = [float(v) for v in reg.predict(x_test)]
        return y_dir, y_ret, pred_ret, pred_ret, as_ofs

    if model_id == "M2_hgb_reg":
        y = np.asarray([s.y_ret for s in train], dtype=float)
        reg = HistGradientBoostingRegressor(max_depth=4, max_iter=100)
        reg.fit(x_train, y)
        pred_ret = [float(v) for v in reg.predict(x_test)]
        return y_dir, y_ret, pred_ret, pred_ret, as_ofs

    # Fallback to shared helper
    yd, yr, pred = _fit_predict_sklearn(
        train, test, task="dir", model_id=model_id
    )
    return yd, yr, pred, pred, as_ofs


def run_purged_walkforward(
    series: dict,
    *,
    horizon: int,
    min_history: int = 60,
    min_train_days: int = 100,
    fold_step: int = 10,
    embargo: int = 2,
    panel: bool = False,
    model_ids: tuple[str, ...] = (
        "B1_logistic",
        "M1_hgb_clf",
        "M2_hgb_reg",
    ),
) -> tuple[list[HardenedMetrics], dict[str, list[dict[str, float | None]]]]:
    samples = build_samples(series, horizon=horizon, min_history=min_history)
    if panel:
        samples = _demean_by_day(samples)
    if not samples:
        return [], {}

    dates = _unique_sorted_dates(samples)
    if len(dates) < min_train_days + fold_step:
        return [], {}

    acc: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "hits": 0,
            "total": 0,
            "origins": 0,
            "folds": 0,
            "fold_hits": [],
            "y_dir": [],
            "scores": [],
            "y_ret": [],
            "as_of": [],
            "pred_for_ic": [],
        }
    )

    cut = min_train_days
    while cut + fold_step <= len(dates):
        test_dates = set(dates[cut : cut + fold_step])
        train = _purge_train(
            samples,
            dates=dates,
            cut=cut,
            horizon=horizon,
            embargo=embargo,
        )
        test = [s for s in samples if s.as_of in test_dates]
        cut += fold_step
        if len(train) < 50 or len(test) < 10:
            continue
        for model_id in model_ids:
            try:
                y_dir, y_ret, scores, pred, as_ofs = _fit_predict_with_scores(
                    train, test, model_id=model_id
                )
            except Exception as exc:
                log.warning(
                    "purged_fold_failed",
                    model_id=model_id,
                    horizon=horizon,
                    error=str(exc),
                )
                continue
            b = acc[model_id]
            b["folds"] += 1
            b["origins"] += len(test)
            fold_h = 0
            fold_t = 0
            for yd, sc in zip(y_dir, scores, strict=True):
                if yd == 0 or sc == 0:
                    continue
                pred_d = 1.0 if sc > 0 else -1.0
                fold_t += 1
                b["total"] += 1
                if (yd > 0 and pred_d > 0) or (yd < 0 and pred_d < 0):
                    fold_h += 1
                    b["hits"] += 1
            if fold_t:
                b["fold_hits"].append(fold_h / fold_t)
            b["y_dir"].extend(y_dir)
            b["scores"].extend(scores)
            b["y_ret"].extend(y_ret)
            b["as_of"].extend(as_ofs)
            b["pred_for_ic"].extend(scores)

    metrics: list[HardenedMetrics] = []
    gate_tables: dict[str, list[dict[str, float | None]]] = {}
    for model_id, b in acc.items():
        total = int(b["total"])
        hits = int(b["hits"])
        hit_rate = hits / total if total else None
        pooled_ic = spearman(b["pred_for_ic"], b["y_ret"])
        rank_ic, rank_days = mean_daily_rank_ic(
            b["as_of"], b["pred_for_ic"], b["y_ret"]
        )
        gates = sweep_confidence_gates(b["y_dir"], b["scores"])
        mode = "panel" if panel else "purged"
        gate_tables[f"{model_id}::{mode}_h{horizon}"] = gates
        # Best gated hit with coverage >= 10%
        best_hit = None
        best_thr = None
        best_cov = None
        for row in gates:
            if not row["meets_coverage"]:
                continue
            hr = row["hit_rate"]
            if hr is None:
                continue
            if best_hit is None or hr > best_hit:
                best_hit = hr
                best_thr = row["threshold"]
                best_cov = row["coverage"]
        metrics.append(
            HardenedMetrics(
                model_id=model_id + ("::panel" if panel else "::purged"),
                horizon=horizon,
                origins=int(b["origins"]),
                direction_hits=hits,
                direction_total=total,
                hit_rate=hit_rate,
                pooled_ic=pooled_ic,
                mean_rank_ic=rank_ic,
                rank_ic_days=rank_days,
                folds=int(b["folds"]),
                fold_hit_rates=tuple(b["fold_hits"]),
                gated_best_hit=best_hit,
                gated_best_thr=best_thr,
                gated_best_coverage=best_cov,
                purged=True,
            )
        )
    return metrics, gate_tables


def decide_hardened(metrics: list[HardenedMetrics]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    go = False
    for m in metrics:
        folds_ok = 0
        if m.fold_hit_rates:
            folds_ok = sum(1 for h in m.fold_hit_rates if h >= 0.52)
        need = max(1, (2 * len(m.fold_hit_rates) + 2) // 3) if m.fold_hit_rates else 0
        if (
            m.hit_rate is not None
            and m.hit_rate >= 0.55
            and m.folds >= 2
            and folds_ok >= need
        ):
            go = True
            reasons.append(
                f"{m.model_id} h={m.horizon} purged_hit={m.hit_rate:.3f} "
                f"folds_ge_0.52={folds_ok}/{len(m.fold_hit_rates)}"
            )
        if m.mean_rank_ic is not None and m.mean_rank_ic >= 0.03 and m.rank_ic_days >= 20:
            go = True
            reasons.append(
                f"{m.model_id} h={m.horizon} RankIC={m.mean_rank_ic:.3f} "
                f"(days={m.rank_ic_days})"
            )
        if (
            m.gated_best_hit is not None
            and m.gated_best_hit >= 0.65
            and m.gated_best_coverage is not None
            and m.gated_best_coverage >= 0.10
        ):
            go = True
            reasons.append(
                f"{m.model_id} h={m.horizon} gated_hit={m.gated_best_hit:.3f} "
                f"@thr={m.gated_best_thr} cov={m.gated_best_coverage:.2f}"
            )
    if go:
        return "GO", reasons
    # Check collapse
    best = None
    for m in metrics:
        if m.hit_rate is None:
            continue
        if best is None or m.hit_rate > (best.hit_rate or 0):
            best = m
    if best and best.hit_rate is not None and best.hit_rate < 0.53:
        return "NO-GO", [
            f"Best purged hit_rate={best.hit_rate:.3f} "
            f"({best.model_id}) — signal weak under honesty check"
        ]
    return "UNCLEAR", reasons or ["No metric cleared hardened gates"]


def render_harden_markdown(result: HardenResult) -> str:
    lines = [
        "# Hardened ML eval (purge · RankIC · confidence gate)",
        "",
        f"**Generated (UTC):** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**CSE universe:** {result.cse_symbols} symbols · {result.bars} bars",
        f"**Decision:** **{result.decision}**",
        "",
        "## Reasons",
        "",
    ]
    for r in result.reasons:
        lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Model | H | Origins | Hit | RankIC | Folds | Fold hits | "
            "Best gated hit | Thr | Cov |",
            "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|",
        ]
    )
    for m in result.metrics:
        hr = f"{m.hit_rate:.3f}" if m.hit_rate is not None else "—"
        ric = f"{m.mean_rank_ic:.3f}" if m.mean_rank_ic is not None else "—"
        folds = ",".join(f"{x:.2f}" for x in m.fold_hit_rates) or "—"
        gh = f"{m.gated_best_hit:.3f}" if m.gated_best_hit is not None else "—"
        gt = f"{m.gated_best_thr}" if m.gated_best_thr is not None else "—"
        gc = (
            f"{m.gated_best_coverage:.2f}"
            if m.gated_best_coverage is not None
            else "—"
        )
        lines.append(
            f"| {m.model_id} | {m.horizon} | {m.origins} | {hr} | {ric} | "
            f"{m.folds} | {folds} | {gh} | {gt} | {gc} |"
        )
    lines.extend(
        [
            "",
            "## Gates",
            "",
            "- Purged hit ≥ 0.55 with ≥2/3 folds ≥ 0.52",
            "- Or mean RankIC ≥ 0.03 (≥20 days)",
            "- Or gated hit ≥ 0.65 at coverage ≥ 10%",
            "",
            "## Notes",
            "",
            "- Purge removes train rows in the last ``horizon`` sessions before test",
            "- Embargo further shrinks the train edge by 2 sessions",
            "- Panel mode demeans returns within each day (cross-section)",
            "- Confidence scores: P(up)−0.5 for classifiers; predicted return for regs",
            "",
            "Research only — not financial advice.",
            "",
        ]
    )
    # Gate tables
    if result.gate_tables:
        lines.extend(["## Confidence gate sweeps", ""])
        for key, rows in sorted(result.gate_tables.items()):
            lines.append(f"### {key}")
            lines.append("")
            lines.append("| Thr | Hit rate | N | Coverage |")
            lines.append("|---:|---:|---:|---:|")
            for row in rows:
                hr = (
                    f"{row['hit_rate']:.3f}"
                    if row["hit_rate"] is not None
                    else "—"
                )
                lines.append(
                    f"| {row['threshold']} | {hr} | {int(row['n_gated'] or 0)} | "
                    f"{row['coverage']:.2f} |"
                )
            lines.append("")
    return "\n".join(lines)


async def run_harden_experiment(
    *,
    storage: Storage,
    horizons: tuple[int, ...] = (1, 5),
    limit_symbols: int | None = None,
    out_dir: Path = Path("docs/experiments"),
) -> HardenResult:
    if not sklearn_available():
        return HardenResult(
            decision="UNCLEAR",
            reasons=["sklearn not installed"],
        )
    series = await load_symbol_bars(storage, limit_symbols=limit_symbols)
    bars = sum(len(v) for v in series.values())
    all_metrics: list[HardenedMetrics] = []
    all_gates: dict[str, list[dict[str, float | None]]] = {}

    # Baseline naive (unpurged, for reference)
    for h in horizons:
        if h == 5:
            b0 = evaluate_b0_naive(series, horizon=h, min_history=60)
            all_metrics.append(
                HardenedMetrics(
                    model_id="B0_naive",
                    horizon=h,
                    origins=b0.origins,
                    direction_hits=b0.direction_hits,
                    direction_total=b0.direction_total,
                    hit_rate=b0.hit_rate,
                    pooled_ic=None,
                    mean_rank_ic=None,
                    rank_ic_days=0,
                    folds=0,
                    fold_hit_rates=(),
                    gated_best_hit=None,
                    gated_best_thr=None,
                    gated_best_coverage=None,
                    purged=False,
                )
            )

    for panel in (False, True):
        for h in horizons:
            metrics, gates = run_purged_walkforward(
                series,
                horizon=h,
                panel=panel,
                fold_step=10,
                min_train_days=100,
                embargo=2,
            )
            all_metrics.extend(metrics)
            all_gates.update(gates)

    decision, reasons = decide_hardened(all_metrics)
    result = HardenResult(
        decision=decision,
        reasons=reasons,
        metrics=all_metrics,
        gate_tables=all_gates,
        cse_symbols=len(series),
        bars=bars,
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_md = out_dir / f"ml_hardened_{stamp}.md"
    out_json = out_md.with_suffix(".json")
    out_md.write_text(render_harden_markdown(result), encoding="utf-8")
    out_json.write_text(json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8")
    log.info(
        "ml_harden_done",
        decision=decision,
        report=str(out_md),
        metrics=len(all_metrics),
    )
    return result
