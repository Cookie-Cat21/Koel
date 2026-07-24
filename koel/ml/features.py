"""Path feature vectors for ML experiments (leakage-safe: bars ≤ as_of only)."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date

from koel.domain import DailyBar

FEATURE_NAMES: tuple[str, ...] = (
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "vol_20d",
    "liquidity_20d",
    "vol_spike",
    "range_20d",
    "vol_regime",
    "turnover_20d",
    "long_gaps_40",
    "max_gap_days",
    "log_price",
    "dist_20d_high",
    "dist_20d_low",
)


@dataclass(frozen=True, slots=True)
class FeatureRow:
    symbol: str
    as_of: date
    values: tuple[float, ...]  # aligned with FEATURE_NAMES; NaN allowed


def _window_return(prices: list[float], n: int) -> float:
    if len(prices) <= n:
        return float("nan")
    start, end = prices[-(n + 1)], prices[-1]
    if start == 0 or not math.isfinite(start) or not math.isfinite(end):
        return float("nan")
    return (end / start) - 1.0


def _returns(prices: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(prices)):
        prev, cur = prices[i - 1], prices[i]
        if prev == 0 or not math.isfinite(prev) or not math.isfinite(cur):
            continue
        out.append((cur / prev) - 1.0)
    return out


def path_features(bars: list[DailyBar]) -> FeatureRow | None:
    """Compute features from ascending bars ending at the last bar (as_of)."""
    if not bars:
        return None
    ordered = sorted(bars, key=lambda b: b.trade_date)
    prices = [b.price for b in ordered if math.isfinite(b.price)]
    if len(prices) < 5:
        return None

    ret_1 = _window_return(prices, 1)
    ret_5 = _window_return(prices, 5)
    ret_20 = _window_return(prices, 20)
    ret_60 = _window_return(prices, 60)
    rets_20 = _returns(prices[-21:]) if len(prices) >= 21 else _returns(prices)
    vol_20 = (
        statistics.pstdev(rets_20) if len(rets_20) >= 5 else float("nan")
    )

    vols = [
        b.volume
        for b in ordered[-20:]
        if b.volume is not None and math.isfinite(b.volume)
    ]
    liq = statistics.fmean(vols) if vols else float("nan")

    last_vol = ordered[-1].volume
    if (
        last_vol is not None
        and math.isfinite(last_vol)
        and math.isfinite(liq)
        and liq > 0
    ):
        vol_spike = last_vol / liq
    else:
        vol_spike = float("nan")

    ranges: list[float] = []
    for b in ordered[-20:]:
        if (
            b.high is not None
            and b.low is not None
            and math.isfinite(b.high)
            and math.isfinite(b.low)
            and math.isfinite(b.price)
            and b.price > 0
            and b.high >= b.low
        ):
            ranges.append((b.high - b.low) / b.price)
    range_20 = statistics.fmean(ranges) if ranges else float("nan")

    vol_series = [
        b.volume
        for b in ordered
        if b.volume is not None and math.isfinite(b.volume) and b.volume > 0
    ]
    if len(vol_series) >= 20:
        recent = statistics.fmean(vol_series[-5:])
        prior = statistics.fmean(vol_series[-20:-5])
        vol_regime = recent / prior if prior > 0 else float("nan")
    else:
        vol_regime = float("nan")

    turnovers = [
        b.volume * b.price
        for b in ordered[-20:]
        if b.volume is not None
        and math.isfinite(b.volume)
        and b.volume > 0
        and math.isfinite(b.price)
        and b.price > 0
    ]
    turnover_20 = statistics.fmean(turnovers) if turnovers else float("nan")

    gap_days: list[int] = []
    recent = ordered[-40:]
    for i in range(1, len(recent)):
        delta = (recent[i].trade_date - recent[i - 1].trade_date).days
        if delta > 1:
            gap_days.append(delta)
    long_gaps = float(sum(1 for g in gap_days if g >= 5))
    max_gap = float(max(gap_days) if gap_days else 0)
    log_price = math.log(prices[-1]) if prices[-1] > 0 else float("nan")

    chunk_20 = ordered[-20:]
    highs = [
        b.high
        for b in chunk_20
        if b.high is not None and math.isfinite(b.high)
    ]
    lows = [
        b.low for b in chunk_20 if b.low is not None and math.isfinite(b.low)
    ]
    last_px = prices[-1]
    if highs and last_px > 0 and math.isfinite(last_px):
        dist_20d_high = (max(highs) - last_px) / last_px
    else:
        dist_20d_high = float("nan")
    if lows and last_px > 0 and math.isfinite(last_px):
        dist_20d_low = (last_px - min(lows)) / last_px
    else:
        dist_20d_low = float("nan")

    values = (
        ret_1,
        ret_5,
        ret_20,
        ret_60,
        vol_20,
        liq,
        vol_spike,
        range_20,
        vol_regime,
        turnover_20,
        long_gaps,
        max_gap,
        log_price,
        dist_20d_high,
        dist_20d_low,
    )
    return FeatureRow(
        symbol=ordered[-1].symbol.strip().upper(),
        as_of=ordered[-1].trade_date,
        values=values,
    )


def labels_at(
    prices: list[float],
    *,
    index: int,
    horizon: int,
    include_flat: bool = False,
    skip: int = 0,
) -> tuple[float, float] | None:
    """Return horizon (return, direction); flat is optional and encoded as 0.

    ``skip`` shifts the label window forward by that many sessions after the
    feature ``as_of`` index (execution lag / skip-day labels). Features stay at
    ``index``; the return is measured from ``index+skip`` to ``index+skip+horizon``.
    """
    if horizon < 1 or skip < 0 or index < 0:
        return None
    start = index + skip
    end = start + horizon
    if end >= len(prices):
        return None
    p0, p1 = prices[start], prices[end]
    if p0 == 0 or not math.isfinite(p0) or not math.isfinite(p1):
        return None
    ret = (p1 / p0) - 1.0
    if not math.isfinite(ret):
        return None
    if ret == 0:
        return (0.0, 0.0) if include_flat else None
    direction = 1.0 if ret > 0 else -1.0
    return ret, direction
