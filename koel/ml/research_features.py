"""Point-in-time source and data-quality features for distributed research."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from koel.domain import DailyBar
from koel.ml.dataset import Sample

RETURN_LAGS = 20
VOLUME_LAGS = 10
RANGE_LAGS = 10

RESEARCH_FEATURE_NAMES: tuple[str, ...] = (
    "source_is_cse",
    "cse_fraction_20",
    "cse_fraction_60",
    "days_since_cse_start",
    "recent_source_splice",
    "missing_open_fraction_20",
    "missing_hilo_fraction_20",
    "missing_volume_fraction_20",
    "flat_price_streak",
) + tuple(f"return_lag_{lag}" for lag in range(1, RETURN_LAGS + 1)) + tuple(
    f"log_volume_lag_{lag}" for lag in range(1, VOLUME_LAGS + 1)
) + tuple(f"range_lag_{lag}" for lag in range(1, RANGE_LAGS + 1)) + (
    "weekday_sin",
    "weekday_cos",
    "month_sin",
    "month_cos",
)

MARKET_CONTEXT_NAMES: tuple[str, ...] = (
    "market_mean_ret_1d",
    "market_median_ret_1d",
    "market_fraction_up_1d",
    "market_dispersion_1d",
    "market_mean_ret_5d",
)


@dataclass(frozen=True, slots=True)
class ResearchBarMetadata:
    source: str
    features: tuple[float, ...]


def _window_fraction(prefix: list[int], *, end: int, width: int) -> float:
    start = max(0, end - width + 1)
    count = prefix[end + 1] - prefix[start]
    return count / (end - start + 1)


def build_research_bar_metadata(
    series: dict[str, list[DailyBar]],
    *,
    dataset: str,
) -> dict[tuple[str, date], ResearchBarMetadata]:
    """Precompute source/quality features using bars available by each date."""
    if dataset not in {"cse", "hybrid"}:
        raise ValueError("dataset must be 'cse' or 'hybrid'")
    out: dict[tuple[str, date], ResearchBarMetadata] = {}
    for raw_symbol, bars in series.items():
        symbol = raw_symbol.strip().upper()
        ordered = sorted(bars, key=lambda bar: bar.trade_date)
        sources = [
            "cse" if dataset == "cse" or bar.source_period == 5 else "yahoo"
            for bar in ordered
        ]
        cse_prefix = [0]
        missing_open_prefix = [0]
        missing_hilo_prefix = [0]
        missing_volume_prefix = [0]
        first_cse_index: int | None = None
        flat_streak = 0
        returns = [float("nan")]
        log_volumes: list[float] = []
        ranges: list[float] = []
        for index, bar in enumerate(ordered):
            if index > 0 and ordered[index - 1].price > 0:
                returns.append((bar.price / ordered[index - 1].price) - 1.0)
            log_volumes.append(
                math.log1p(bar.volume)
                if bar.volume is not None
                and math.isfinite(bar.volume)
                and bar.volume > 0
                else float("nan")
            )
            ranges.append(
                (bar.high - bar.low) / bar.price
                if bar.high is not None
                and bar.low is not None
                and math.isfinite(bar.high)
                and math.isfinite(bar.low)
                and bar.price > 0
                else float("nan")
            )

        for index, (bar, source) in enumerate(zip(ordered, sources, strict=True)):
            if source == "cse" and first_cse_index is None:
                first_cse_index = index
            cse_prefix.append(cse_prefix[-1] + int(source == "cse"))
            missing_open_prefix.append(
                missing_open_prefix[-1]
                + int(bar.open is None or not math.isfinite(bar.open))
            )
            missing_hilo_prefix.append(
                missing_hilo_prefix[-1]
                + int(
                    bar.high is None
                    or bar.low is None
                    or not math.isfinite(bar.high)
                    or not math.isfinite(bar.low)
                )
            )
            missing_volume_prefix.append(
                missing_volume_prefix[-1]
                + int(
                    bar.volume is None
                    or not math.isfinite(bar.volume)
                    or bar.volume <= 0
                )
            )
            if index > 0 and bar.price == ordered[index - 1].price:
                flat_streak += 1
            else:
                flat_streak = 0

            if first_cse_index is not None and index >= first_cse_index:
                days_since_cse_start = min(
                    3650.0,
                    float(
                        (bar.trade_date - ordered[first_cse_index].trade_date).days
                    ),
                )
                recent_splice = float(index - first_cse_index < 20)
            else:
                days_since_cse_start = -1.0
                recent_splice = 0.0

            return_lags = tuple(
                returns[index - lag + 1] if index - lag + 1 >= 0 else float("nan")
                for lag in range(1, RETURN_LAGS + 1)
            )
            volume_lags = tuple(
                log_volumes[index - lag + 1]
                if index - lag + 1 >= 0
                else float("nan")
                for lag in range(1, VOLUME_LAGS + 1)
            )
            range_lags = tuple(
                ranges[index - lag + 1]
                if index - lag + 1 >= 0
                else float("nan")
                for lag in range(1, RANGE_LAGS + 1)
            )
            weekday_angle = 2 * math.pi * bar.trade_date.weekday() / 7
            month_angle = 2 * math.pi * (bar.trade_date.month - 1) / 12
            features = (
                float(source == "cse"),
                _window_fraction(cse_prefix, end=index, width=20),
                _window_fraction(cse_prefix, end=index, width=60),
                days_since_cse_start,
                recent_splice,
                _window_fraction(missing_open_prefix, end=index, width=20),
                _window_fraction(missing_hilo_prefix, end=index, width=20),
                _window_fraction(missing_volume_prefix, end=index, width=20),
                float(min(flat_streak, 60)),
                *return_lags,
                *volume_lags,
                *range_lags,
                math.sin(weekday_angle),
                math.cos(weekday_angle),
                math.sin(month_angle),
                math.cos(month_angle),
            )
            out[(symbol, bar.trade_date)] = ResearchBarMetadata(
                source=source,
                features=features,
            )
    return out


def enrich_research_quality(
    samples: list[Sample],
    metadata: dict[tuple[str, date], ResearchBarMetadata],
) -> list[Sample]:
    """Append precomputed point-in-time metadata to sample vectors."""
    out: list[Sample] = []
    for sample in samples:
        meta = metadata.get((sample.symbol, sample.as_of))
        if meta is None:
            continue
        out.append(
            Sample(
                symbol=sample.symbol,
                as_of=sample.as_of,
                x=tuple(sample.x) + meta.features,
                y_ret=sample.y_ret,
                y_dir=sample.y_dir,
                horizon=sample.horizon,
                target_date=sample.target_date,
            )
        )
    return out


def sample_domain(
    sample: Sample,
    metadata: dict[tuple[str, date], ResearchBarMetadata],
) -> str | None:
    """Return a domain only when both decision and outcome bars share it."""
    if sample.target_date is None:
        return None
    start = metadata.get((sample.symbol, sample.as_of))
    target = metadata.get((sample.symbol, sample.target_date))
    if start is None or target is None or start.source != target.source:
        return None
    return start.source


def enrich_market_context(samples: list[Sample]) -> list[Sample]:
    """Append same-session market breadth and return context."""
    by_day: dict[date, list[Sample]] = defaultdict(list)
    for sample in samples:
        by_day[sample.as_of].append(sample)
    out: list[Sample] = []
    for day_samples in by_day.values():
        ret_1d = [
            sample.x[0] for sample in day_samples if math.isfinite(sample.x[0])
        ]
        ret_5d = [
            sample.x[1] for sample in day_samples if math.isfinite(sample.x[1])
        ]
        if ret_1d:
            mean_1d = statistics.fmean(ret_1d)
            median_1d = statistics.median(ret_1d)
            fraction_up = sum(value > 0 for value in ret_1d) / len(ret_1d)
            dispersion = statistics.pstdev(ret_1d) if len(ret_1d) > 1 else 0.0
        else:
            mean_1d = median_1d = fraction_up = dispersion = float("nan")
        mean_5d = statistics.fmean(ret_5d) if ret_5d else float("nan")
        context = (mean_1d, median_1d, fraction_up, dispersion, mean_5d)
        for sample in day_samples:
            out.append(
                Sample(
                    symbol=sample.symbol,
                    as_of=sample.as_of,
                    x=tuple(sample.x) + context,
                    y_ret=sample.y_ret,
                    y_dir=sample.y_dir,
                    horizon=sample.horizon,
                    target_date=sample.target_date,
                )
            )
    return out
