"""Feature Pack v1 research helpers (point-in-time, not wired to training).

Pure functions over ascending ``DailyBar`` history ending at ``as_of``.
See ``docs/experiments/FEATURE_PACK_V1_SPEC.md``.
"""

from __future__ import annotations

import math
import statistics
from datetime import date

from koel.domain import DailyBar

FEATURE_PACK_V1_BAR_NAMES: tuple[str, ...] = (
    "fp_adv20",
    "fp_vol20",
)


def _ordered_bars(bars: list[DailyBar]) -> list[DailyBar]:
    return sorted(bars, key=lambda bar: bar.trade_date)


def _bars_through_as_of(bars: list[DailyBar], as_of: date) -> list[DailyBar]:
    return [bar for bar in _ordered_bars(bars) if bar.trade_date <= as_of]


def _daily_returns(prices: list[float]) -> list[float]:
    out: list[float] = []
    for index in range(1, len(prices)):
        prev, cur = prices[index - 1], prices[index]
        if prev == 0 or not math.isfinite(prev) or not math.isfinite(cur):
            continue
        out.append((cur / prev) - 1.0)
    return out


def adv20(bars: list[DailyBar], *, as_of: date | None = None) -> float:
    """20-session average daily volume (share count) ending on ``as_of``."""
    window = _bars_through_as_of(bars, as_of) if as_of is not None else _ordered_bars(bars)
    volumes = [
        bar.volume
        for bar in window[-20:]
        if bar.volume is not None and math.isfinite(bar.volume)
    ]
    if not volumes:
        return float("nan")
    return statistics.fmean(volumes)


def vol20(bars: list[DailyBar], *, as_of: date | None = None) -> float:
    """20-session realized volatility (population stdev of daily returns)."""
    window = _bars_through_as_of(bars, as_of) if as_of is not None else _ordered_bars(bars)
    prices = [bar.price for bar in window if math.isfinite(bar.price)]
    if len(prices) < 6:
        return float("nan")
    chunk = prices[-21:] if len(prices) >= 21 else prices
    returns = _daily_returns(chunk)
    if len(returns) < 5:
        return float("nan")
    tail = returns[-20:] if len(returns) >= 20 else returns
    return statistics.pstdev(tail)
