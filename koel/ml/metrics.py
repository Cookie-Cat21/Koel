"""RankIC and confidence-gate metrics for ML experiments."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date


def spearman(preds: list[float], actuals: list[float]) -> float | None:
    if len(preds) < 3 or len(preds) != len(actuals):
        return None

    def ranks(xs: list[float]) -> list[float]:
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        result = [0.0] * len(xs)
        start = 0
        while start < len(order):
            end = start + 1
            while end < len(order) and xs[order[end]] == xs[order[start]]:
                end += 1
            average_rank = (start + end - 1) / 2
            for position in range(start, end):
                result[order[position]] = average_rank
            start = end
        return result

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
        total += 1
        pred = 1.0 if sc > 0 else -1.0
        if yd != 0 and ((yd > 0 and pred > 0) or (yd < 0 and pred < 0)):
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


def balanced_direction_accuracy(
    y_dir: list[float],
    scores: list[float],
) -> float | None:
    """Binary balanced accuracy on non-flat realized directions."""
    if len(y_dir) != len(scores) or not y_dir:
        return None
    tp = tn = fp = fn = 0
    for actual, score in zip(y_dir, scores, strict=True):
        if actual == 0 or not math.isfinite(score):
            continue
        predicted_up = score > 0
        if actual > 0 and predicted_up:
            tp += 1
        elif actual > 0:
            fn += 1
        elif predicted_up:
            fp += 1
        else:
            tn += 1
    if tp + fn == 0 or tn + fp == 0:
        return None
    return 0.5 * (tp / (tp + fn) + tn / (tn + fp))


def matthews_direction_correlation(
    y_dir: list[float],
    scores: list[float],
) -> float | None:
    """Binary MCC on non-flat labels; constant prediction returns zero."""
    if len(y_dir) != len(scores) or not y_dir:
        return None
    tp = tn = fp = fn = 0
    for actual, score in zip(y_dir, scores, strict=True):
        if actual == 0 or not math.isfinite(score):
            continue
        predicted_up = score > 0
        if actual > 0 and predicted_up:
            tp += 1
        elif actual > 0:
            fn += 1
        elif predicted_up:
            fp += 1
        else:
            tn += 1
    if tp + fn == 0 or tn + fp == 0:
        return None
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / denominator if denominator > 0 else 0.0


def brier_score(outcomes: list[bool], probabilities: list[float]) -> float | None:
    if len(outcomes) != len(probabilities) or not outcomes:
        return None
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities):
        raise ValueError("probabilities must be finite values in [0, 1]")
    return sum(
        (probability - float(outcome)) ** 2
        for outcome, probability in zip(outcomes, probabilities, strict=True)
    ) / len(outcomes)


def expected_calibration_error(
    outcomes: list[bool],
    probabilities: list[float],
    *,
    bins: int = 10,
) -> float | None:
    """Fixed-width ECE; the final bin includes probability 1."""
    if len(outcomes) != len(probabilities) or not outcomes:
        return None
    if bins < 2:
        raise ValueError("bins must be at least 2")
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities):
        raise ValueError("probabilities must be finite values in [0, 1]")
    total = len(outcomes)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        selected = [
            (outcome, probability)
            for outcome, probability in zip(outcomes, probabilities, strict=True)
            if lower <= probability < upper
            or (index == bins - 1 and probability == 1.0)
        ]
        if not selected:
            continue
        accuracy = sum(float(outcome) for outcome, _ in selected) / len(selected)
        confidence = sum(probability for _, probability in selected) / len(selected)
        error += len(selected) / total * abs(accuracy - confidence)
    return error


@dataclass(frozen=True, slots=True)
class CostAdjustedSpread:
    sessions: int
    mean_gross_return: float
    mean_net_return: float
    compounded_net_return: float
    mean_one_way_turnover: float
    break_even_cost_bps: float | None


def cost_adjusted_top_bottom_spread(
    as_of: list[date],
    symbols: list[str],
    scores: list[float],
    returns: list[float],
    *,
    fraction: float = 0.10,
    cost_bps: float = 112.0,
    min_names: int = 20,
) -> CostAdjustedSpread | None:
    """Equal-weight long/short spread with explicit traded-notional costs."""
    if not (
        len(as_of) == len(symbols) == len(scores) == len(returns)
        and 0 < fraction < 0.5
        and cost_bps >= 0
    ):
        return None
    by_day: dict[date, list[tuple[str, float, float]]] = defaultdict(list)
    for session, symbol, score, realized in zip(
        as_of,
        symbols,
        scores,
        returns,
        strict=True,
    ):
        if math.isfinite(score) and math.isfinite(realized):
            by_day[session].append((symbol, score, realized))

    previous_weights: dict[str, float] = {}
    gross_returns: list[float] = []
    net_returns: list[float] = []
    turnovers: list[float] = []
    total_gross = 0.0
    total_traded = 0.0
    for session in sorted(by_day):
        rows = sorted(by_day[session], key=lambda row: (row[1], row[0]))
        if len(rows) < min_names:
            continue
        leg_size = max(1, math.floor(len(rows) * fraction))
        if rows[leg_size - 1][1] == rows[leg_size][1]:
            continue
        if rows[-leg_size - 1][1] == rows[-leg_size][1]:
            continue
        short_rows = rows[:leg_size]
        long_rows = rows[-leg_size:]
        weights = {
            **{symbol: -1.0 / leg_size for symbol, _score, _ret in short_rows},
            **{symbol: 1.0 / leg_size for symbol, _score, _ret in long_rows},
        }
        realized_by_symbol = {symbol: ret for symbol, _score, ret in rows}
        gross = sum(
            weight * realized_by_symbol[symbol] for symbol, weight in weights.items()
        )
        traded = sum(
            abs(weights.get(symbol, 0.0) - previous_weights.get(symbol, 0.0))
            for symbol in set(weights) | set(previous_weights)
        )
        net = gross - cost_bps / 10_000 * traded
        gross_returns.append(gross)
        net_returns.append(net)
        turnovers.append(traded / 2)
        total_gross += gross
        total_traded += traded
        previous_weights = weights

    if not gross_returns:
        return None
    compounded = math.prod(1.0 + value for value in net_returns) - 1.0
    break_even = (
        10_000 * total_gross / total_traded if total_traded > 0 else None
    )
    return CostAdjustedSpread(
        sessions=len(gross_returns),
        mean_gross_return=sum(gross_returns) / len(gross_returns),
        mean_net_return=sum(net_returns) / len(net_returns),
        compounded_net_return=compounded,
        mean_one_way_turnover=sum(turnovers) / len(turnovers),
        break_even_cost_bps=break_even,
    )
