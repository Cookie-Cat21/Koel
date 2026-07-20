"""RankIC and confidence-gate metrics for ML experiments."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date


def spearman(preds: list[float], actuals: list[float]) -> float | None:
    if len(preds) < 3 or len(preds) != len(actuals):
        return None

    def ranks(xs: list[float]) -> list[float]:
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        for rank, i in enumerate(order):
            r[i] = float(rank)
        return r

    rp, ra = ranks(preds), ranks(actuals)
    mean_p = sum(rp) / len(rp)
    mean_a = sum(ra) / len(ra)
    num = sum((p - mean_p) * (a - mean_a) for p, a in zip(rp, ra, strict=True))
    den_p = math.sqrt(sum((p - mean_p) ** 2 for p in rp))
    den_a = math.sqrt(sum((a - mean_a) ** 2 for a in ra))
    if den_p == 0 or den_a == 0:
        return None
    return num / (den_p * den_a)


def mean_daily_rank_ic(
    as_of: list[date],
    preds: list[float],
    actuals: list[float],
    *,
    min_names: int = 5,
) -> tuple[float | None, int]:
    """Average Spearman IC within each as_of date. Returns (mean_ic, n_days)."""
    by_day: dict[date, list[tuple[float, float]]] = defaultdict(list)
    for d, p, a in zip(as_of, preds, actuals, strict=True):
        if not math.isfinite(p) or not math.isfinite(a):
            continue
        by_day[d].append((p, a))
    ics: list[float] = []
    for pairs in by_day.values():
        if len(pairs) < min_names:
            continue
        ic = spearman([p for p, _ in pairs], [a for _, a in pairs])
        if ic is not None:
            ics.append(ic)
    if not ics:
        return None, 0
    return sum(ics) / len(ics), len(ics)


def gated_direction_stats(
    y_dir: list[float],
    scores: list[float],
    *,
    threshold: float,
) -> tuple[float | None, int, float]:
    """Hit rate among samples with |score| >= threshold.

    For classifiers, ``scores`` should be P(up)-0.5 or signed confidence in [-1,1].
    Returns (hit_rate, n_gated, coverage).
    """
    if not y_dir or len(y_dir) != len(scores):
        return None, 0, 0.0
    hits = 0
    total = 0
    for yd, sc in zip(y_dir, scores, strict=True):
        if abs(sc) < threshold:
            continue
        if yd == 0:
            continue
        pred = 1.0 if sc > 0 else -1.0
        total += 1
        if (yd > 0 and pred > 0) or (yd < 0 and pred < 0):
            hits += 1
    coverage = total / len(y_dir) if y_dir else 0.0
    hit = hits / total if total else None
    return hit, total, coverage


def sweep_confidence_gates(
    y_dir: list[float],
    scores: list[float],
    *,
    thresholds: tuple[float, ...] = (0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3),
    min_coverage: float = 0.10,
) -> list[dict[str, float | None]]:
    rows: list[dict[str, float | None]] = []
    for thr in thresholds:
        hit, n, cov = gated_direction_stats(y_dir, scores, threshold=thr)
        rows.append(
            {
                "threshold": thr,
                "hit_rate": hit,
                "n_gated": float(n),
                "coverage": cov,
                "meets_coverage": 1.0 if cov >= min_coverage else 0.0,
            }
        )
    return rows
