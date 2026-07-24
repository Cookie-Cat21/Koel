"""Feature Pack v3 — v2 sector pack + cross-section / momentum append.

Builds on ``enrich_feature_pack_v1(..., sector_map=...)`` (v2 behavior) and
appends additional research columns. See
``docs/experiments/FEATURE_PACK_V3_SPEC.md``.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.feature_pack_v1 import enrich_feature_pack_v1
from koel.ml.feature_pack_v2 import load_sector_map_for_v2
from koel.ml.snapshot import FundamentalEvent

FEATURE_PACK_V3_NAMES: tuple[str, ...] = (
    "fpv3_sector_rank_ret_1d",
    "fpv3_sector_rank_ret_5d",
    "fpv3_adv_cs_z",
    "fpv3_vol20_cs_z",
    "fpv3_ret1d_vol_scaled",
    "fpv3_mom_20d",
    "fpv3_mom_60d",
    "fpv3_amihud_20",
    "fpv3_hl_range_20",
    "fpv3_volume_trend_20",
)


def _ordered_through(bars: list[DailyBar], as_of: date) -> list[DailyBar]:
    return sorted(
        (bar for bar in bars if bar.trade_date <= as_of),
        key=lambda bar: bar.trade_date,
    )


def _window_return(prices: list[float], sessions: int) -> float:
    if len(prices) <= sessions:
        return float("nan")
    start, end = prices[-(sessions + 1)], prices[-1]
    if start == 0 or not math.isfinite(start) or not math.isfinite(end):
        return float("nan")
    return (end / start) - 1.0


def _daily_returns(prices: list[float]) -> list[float]:
    out: list[float] = []
    for index in range(1, len(prices)):
        prev, cur = prices[index - 1], prices[index]
        if prev == 0 or not math.isfinite(prev) or not math.isfinite(cur):
            continue
        out.append((cur / prev) - 1.0)
    return out


def _pstdev(values: list[float]) -> float:
    if len(values) < 2:
        return float("nan")
    return statistics.pstdev(values)


def _z_scores(values: list[float]) -> list[float]:
    finite = [value for value in values if math.isfinite(value)]
    if len(finite) < 2:
        return [float("nan") for _ in values]
    mean = statistics.fmean(finite)
    stdev = statistics.pstdev(finite)
    if stdev == 0 or not math.isfinite(stdev):
        return [float("nan") for _ in values]
    return [
        (value - mean) / stdev if math.isfinite(value) else float("nan") for value in values
    ]


def _percentile_ranks(values: list[float]) -> list[float]:
    indexed = [(index, value) for index, value in enumerate(values) if math.isfinite(value)]
    out = [float("nan")] * len(values)
    if len(indexed) < 2:
        return out
    indexed.sort(key=lambda item: item[1])
    n = len(indexed)
    for rank, (index, _value) in enumerate(indexed):
        out[index] = rank / (n - 1)
    return out


def _bar_extra(bars: list[DailyBar], *, as_of: date) -> tuple[float, ...]:
    window = _ordered_through(bars, as_of)
    prices = [bar.price for bar in window if math.isfinite(bar.price)]
    ret_1d = _window_return(prices, 1)
    ret_5d = _window_return(prices, 5)
    mom_20 = _window_return(prices, 20)
    mom_60 = _window_return(prices, 60)

    returns_20 = _daily_returns(prices[-21:] if len(prices) >= 21 else prices)
    vol20 = _pstdev(returns_20[-20:] if len(returns_20) >= 20 else returns_20)
    ret_vol = (
        ret_1d / vol20
        if math.isfinite(ret_1d) and math.isfinite(vol20) and vol20 > 0
        else float("nan")
    )

    amihud_vals: list[float] = []
    amihud_window = window[-21:]
    for bar_prev, bar in zip(amihud_window[:-1], amihud_window[1:], strict=True):
        if (
            bar_prev.price
            and math.isfinite(bar_prev.price)
            and math.isfinite(bar.price)
            and bar.volume
            and math.isfinite(bar.volume)
            and bar.volume > 0
        ):
            amihud_vals.append(abs((bar.price / bar_prev.price) - 1.0) / bar.volume)
    amihud = statistics.fmean(amihud_vals) if amihud_vals else float("nan")

    ranges: list[float] = []
    for bar in window[-20:]:
        if (
            bar.high is not None
            and bar.low is not None
            and math.isfinite(bar.high)
            and math.isfinite(bar.low)
            and bar.price
            and math.isfinite(bar.price)
            and bar.price > 0
        ):
            ranges.append((bar.high - bar.low) / bar.price)
    hl_range = statistics.fmean(ranges) if ranges else float("nan")

    volumes = [
        bar.volume
        for bar in window[-20:]
        if bar.volume is not None and math.isfinite(bar.volume)
    ]
    adv = statistics.fmean(volumes) if volumes else float("nan")
    if len(volumes) >= 10:
        first = statistics.fmean(volumes[: len(volumes) // 2])
        second = statistics.fmean(volumes[len(volumes) // 2 :])
        volume_trend = (
            (second / first) - 1.0
            if first > 0 and math.isfinite(first) and math.isfinite(second)
            else float("nan")
        )
    else:
        volume_trend = float("nan")

    return (
        ret_1d,
        ret_5d,
        adv,
        vol20,
        ret_vol,
        mom_20,
        mom_60,
        amihud,
        hl_range,
        volume_trend,
    )


def enrich_feature_pack_v3(
    samples: list[Sample],
    series: dict[str, list[DailyBar]],
    fundamentals: dict[str, list[FundamentalEvent]] | None = None,
    *,
    sector_map: dict[str, str] | None = None,
) -> list[Sample]:
    """Append v2 (sector) pack then v3 cross-section / momentum columns."""
    if sector_map is None:
        sector_map = load_sector_map_for_v2() or {}
    base = enrich_feature_pack_v1(
        samples, series, fundamentals, sector_map=sector_map or None
    )
    normalized_sector_map = {
        symbol.strip().upper(): sector for symbol, sector in (sector_map or {}).items()
    }
    series_by_symbol = {symbol.strip().upper(): bars for symbol, bars in series.items()}

    extras: dict[int, tuple[float, ...]] = {}
    by_day: dict[date, list[Sample]] = defaultdict(list)
    for sample in base:
        by_day[sample.as_of].append(sample)
        bars = series_by_symbol.get(sample.symbol.strip().upper(), [])
        extras[id(sample)] = _bar_extra(bars, as_of=sample.as_of)

    out: list[Sample] = []
    for day_samples in by_day.values():
        adv_values = [extras[id(sample)][2] for sample in day_samples]
        vol_values = [extras[id(sample)][3] for sample in day_samples]
        adv_z = _z_scores(adv_values)
        vol_z = _z_scores(vol_values)

        sector_groups: dict[str, list[int]] = defaultdict(list)
        for index, sample in enumerate(day_samples):
            sector = normalized_sector_map.get(sample.symbol.strip().upper())
            if sector:
                sector_groups[sector].append(index)

        rank_1d = [float("nan")] * len(day_samples)
        rank_5d = [float("nan")] * len(day_samples)
        for indexes in sector_groups.values():
            vals_1d = [extras[id(day_samples[i])][0] for i in indexes]
            vals_5d = [extras[id(day_samples[i])][1] for i in indexes]
            ranks_1 = _percentile_ranks(vals_1d)
            ranks_5 = _percentile_ranks(vals_5d)
            for local, sample_index in enumerate(indexes):
                rank_1d[sample_index] = ranks_1[local]
                rank_5d[sample_index] = ranks_5[local]

        # Market-wide ranks when sector missing / singleton.
        market_1d = _percentile_ranks([extras[id(sample)][0] for sample in day_samples])
        market_5d = _percentile_ranks([extras[id(sample)][1] for sample in day_samples])

        for index, sample in enumerate(day_samples):
            (
                _ret_1d,
                _ret_5d,
                _adv,
                _vol20,
                ret_vol,
                mom_20,
                mom_60,
                amihud,
                hl_range,
                volume_trend,
            ) = extras[id(sample)]
            r1 = rank_1d[index] if math.isfinite(rank_1d[index]) else market_1d[index]
            r5 = rank_5d[index] if math.isfinite(rank_5d[index]) else market_5d[index]
            features = (
                r1,
                r5,
                adv_z[index],
                vol_z[index],
                ret_vol,
                mom_20,
                mom_60,
                amihud,
                hl_range,
                volume_trend,
            )
            out.append(
                Sample(
                    symbol=sample.symbol,
                    as_of=sample.as_of,
                    x=tuple(sample.x) + features,
                    y_ret=sample.y_ret,
                    y_dir=sample.y_dir,
                    horizon=sample.horizon,
                    target_date=sample.target_date,
                )
            )
    return out


__all__ = [
    "FEATURE_PACK_V3_NAMES",
    "enrich_feature_pack_v3",
    "load_sector_map_for_v2",
]
