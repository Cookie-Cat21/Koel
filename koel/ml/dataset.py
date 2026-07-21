"""Build leakage-safe sample rows from ``daily_bars``."""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date

from koel.domain import DailyBar
from koel.ml.features import FEATURE_NAMES, labels_at, path_features
from koel.storage import Storage

FEATURE_LOOKBACK_BARS = 61


@dataclass(frozen=True, slots=True)
class Sample:
    symbol: str
    as_of: date
    x: tuple[float, ...]
    y_ret: float
    y_dir: float
    horizon: int


async def load_symbol_bars(
    storage: Storage,
    *,
    limit_symbols: int | None = None,
    hybrid: bool = False,
) -> dict[str, list[DailyBar]]:
    """Load CSE ``daily_bars``, or spliced ``hybrid_daily_bars`` when ``hybrid``.

    Hybrid = Yahoo (pre-CSE coverage) + CSE recent truth. Research/ML only —
    dash product spine stays CSE ``daily_bars``.
    """
    if hybrid:
        symbols = await storage.list_symbols_with_hybrid_daily_bars()
        loader = storage.list_hybrid_daily_bars
    else:
        symbols = await storage.list_symbols_with_daily_bars()
        loader = storage.list_daily_bars
    if (
        limit_symbols is not None
        and isinstance(limit_symbols, int)
        and not isinstance(limit_symbols, bool)
        and limit_symbols > 0
    ):
        symbols = symbols[:limit_symbols]
    out: dict[str, list[DailyBar]] = {}
    for symbol in symbols:
        # Index synthetic row (aspi-backfill) is not an equity — skip in ML panels.
        if symbol.strip().upper() == "ASPI":
            continue
        bars = await loader(symbol)
        if bars:
            out[symbol] = sorted(bars, key=lambda b: b.trade_date)
    return out


def build_samples(
    series: dict[str, list[DailyBar]],
    *,
    horizon: int,
    min_history: int = 60,
    max_abs_return: float | None = None,
) -> list[Sample]:
    """Build samples without copying each symbol's full history per row.

    When ``max_abs_return`` is set, samples whose feature or label window crosses
    an unresolved price cliff are quarantined. Raw bars remain untouched.
    """
    if max_abs_return is not None and max_abs_return <= 0:
        raise ValueError("max_abs_return must be positive")

    samples: list[Sample] = []
    for symbol, bars in series.items():
        ordered = sorted(bars, key=lambda b: b.trade_date)
        prices = [b.price for b in ordered]
        if len(prices) < min_history + horizon:
            continue
        positive_volume_indices = [
            index
            for index, bar in enumerate(ordered)
            if bar.volume is not None
            and math.isfinite(bar.volume)
            and bar.volume > 0
        ]
        bad_prefix: list[int] | None = None
        if max_abs_return is not None:
            bad_prefix = [0]
            for i, price in enumerate(prices):
                bad = False
                if i > 0:
                    previous = prices[i - 1]
                    if previous == 0:
                        bad = True
                    else:
                        move = (price / previous) - 1.0
                        bad = not math.isfinite(move) or abs(move) > max_abs_return
                bad_prefix.append(bad_prefix[-1] + int(bad))
        for i in range(min_history - 1, len(prices) - horizon):
            window_start = max(0, i - (FEATURE_LOOKBACK_BARS - 1))
            volume_end = bisect_right(positive_volume_indices, i)
            if volume_end >= 20:
                window_start = min(
                    window_start,
                    positive_volume_indices[volume_end - 20],
                )
            if bad_prefix is not None:
                first_transition = max(1, window_start + 1)
                last_transition = i + horizon
                if (
                    bad_prefix[last_transition + 1] - bad_prefix[first_transition]
                    > 0
                ):
                    continue
            window = ordered[window_start : i + 1]
            feats = path_features(window)
            if feats is None:
                continue
            lab = labels_at(prices, index=i, horizon=horizon)
            if lab is None:
                continue
            y_ret, y_dir = lab
            samples.append(
                Sample(
                    symbol=symbol,
                    as_of=feats.as_of,
                    x=feats.values,
                    y_ret=y_ret,
                    y_dir=y_dir,
                    horizon=horizon,
                )
            )
    return samples


def feature_names() -> tuple[str, ...]:
    return FEATURE_NAMES
