"""Point-in-time ML universe filters for training sample construction."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.research_features import RESEARCH_FEATURE_NAMES, ResearchBarMetadata


@dataclass(frozen=True, slots=True)
class FilterManifest:
    name: str
    min_adv20: float
    max_flat_fraction_60: float
    min_cse_sessions_60: int
    version: str


LIQ_FILTER_V1 = FilterManifest(
    name="liq_v1",
    min_adv20=1000.0,
    max_flat_fraction_60=0.40,
    min_cse_sessions_60=20,
    version="v1",
)

LIQ_FILTER_V2 = FilterManifest(
    name="liq_v2",
    min_adv20=100.0,
    max_flat_fraction_60=0.50,
    min_cse_sessions_60=10,
    version="v2",
)

LIQ_FILTER_V3 = FilterManifest(
    name="liq_v3",
    min_adv20=0.0,
    max_flat_fraction_60=0.40,
    min_cse_sessions_60=5,
    version="v3",
)

# Soft ADV-only gate: no CSE-session floor (v1–v3 collapsed hybrid history via
# CSE/flat constraints). Keeps Yahoo pretrain depth while dropping illiquid
# names at decision time.
LIQ_FILTER_V4 = FilterManifest(
    name="liq_v4",
    min_adv20=500.0,
    max_flat_fraction_60=1.0,
    min_cse_sessions_60=0,
    version="v4",
)

_CSE_FRACTION_60_INDEX = RESEARCH_FEATURE_NAMES.index("cse_fraction_60")


def passes_liq_filter_v1(
    symbol: str,
    bars_up_to_as_of: list[DailyBar],
    *,
    metadata_row: ResearchBarMetadata | None = None,
) -> bool:
    """Return whether ``symbol`` passes LIQ_FILTER_V1 using visible bars only."""
    return _passes_filter(
        symbol,
        bars_up_to_as_of,
        metadata_row=metadata_row,
        manifest=LIQ_FILTER_V1,
    )


def passes_liq_filter_v2(
    symbol: str,
    bars_up_to_as_of: list[DailyBar],
    *,
    metadata_row: ResearchBarMetadata | None = None,
) -> bool:
    """Return whether ``symbol`` passes LIQ_FILTER_V2 using visible bars only."""
    return _passes_filter(
        symbol,
        bars_up_to_as_of,
        metadata_row=metadata_row,
        manifest=LIQ_FILTER_V2,
    )


def passes_liq_filter_v3(
    symbol: str,
    bars_up_to_as_of: list[DailyBar],
    *,
    metadata_row: ResearchBarMetadata | None = None,
) -> bool:
    """Return whether ``symbol`` passes LIQ_FILTER_V3 using visible bars only."""
    return _passes_filter(
        symbol,
        bars_up_to_as_of,
        metadata_row=metadata_row,
        manifest=LIQ_FILTER_V3,
    )


def passes_liq_filter_v4(
    symbol: str,
    bars_up_to_as_of: list[DailyBar],
    *,
    metadata_row: ResearchBarMetadata | None = None,
) -> bool:
    """Return whether ``symbol`` passes LIQ_FILTER_V4 using visible bars only."""
    return _passes_filter(
        symbol,
        bars_up_to_as_of,
        metadata_row=metadata_row,
        manifest=LIQ_FILTER_V4,
    )


def filter_samples(
    samples: list[Sample],
    series: dict[str, list[DailyBar]],
    metadata: dict[tuple[str, date], ResearchBarMetadata],
    manifest: FilterManifest,
) -> list[Sample]:
    """Keep samples whose symbol passes ``manifest`` at the sample's ``as_of``."""
    series_by_symbol = {
        raw_symbol.strip().upper(): sorted(bars, key=lambda bar: bar.trade_date)
        for raw_symbol, bars in series.items()
    }
    out: list[Sample] = []
    for sample in samples:
        symbol = sample.symbol.strip().upper()
        visible_bars = [
            bar
            for bar in series_by_symbol.get(symbol, [])
            if bar.trade_date <= sample.as_of
        ]
        if _passes_filter(
            symbol,
            visible_bars,
            metadata_row=metadata.get((symbol, sample.as_of)),
            manifest=manifest,
        ):
            out.append(sample)
    return out


def _passes_filter(
    symbol: str,
    bars_up_to_as_of: list[DailyBar],
    *,
    metadata_row: ResearchBarMetadata | None,
    manifest: FilterManifest,
) -> bool:
    ordered = _visible_symbol_bars(symbol, bars_up_to_as_of)
    if not ordered:
        return False
    if manifest.min_adv20 > 0:
        adv = _adv20(ordered)
        if not math.isfinite(adv) or adv < manifest.min_adv20:
            return False
    flat_fraction = _flat_fraction_60(ordered, metadata_row=metadata_row)
    if (
        not math.isfinite(flat_fraction)
        or flat_fraction > manifest.max_flat_fraction_60
    ):
        return False
    cse_sessions = _cse_sessions_60(ordered, metadata_row=metadata_row)
    return cse_sessions >= manifest.min_cse_sessions_60


def _visible_symbol_bars(symbol: str, bars: list[DailyBar]) -> list[DailyBar]:
    wanted = symbol.strip().upper()
    return sorted(
        (bar for bar in bars if bar.symbol.strip().upper() == wanted),
        key=lambda bar: bar.trade_date,
    )


def _adv20(ordered: list[DailyBar]) -> float:
    volumes = [
        bar.volume
        for bar in ordered[-20:]
        if bar.volume is not None and math.isfinite(bar.volume)
    ]
    if not volumes:
        return float("nan")
    return statistics.fmean(volumes)


def _flat_fraction_60(
    ordered: list[DailyBar],
    *,
    metadata_row: ResearchBarMetadata | None,
) -> float:
    if metadata_row is not None and math.isfinite(metadata_row.flat_fraction_60):
        return metadata_row.flat_fraction_60
    if not ordered:
        return float("nan")
    width = min(60, len(ordered))
    start = len(ordered) - width
    flat = sum(
        1
        for index in range(start, len(ordered))
        if index > 0 and ordered[index].price == ordered[index - 1].price
    )
    return flat / width


def _cse_sessions_60(
    ordered: list[DailyBar],
    *,
    metadata_row: ResearchBarMetadata | None,
) -> int:
    width = min(60, len(ordered))
    recent = ordered[-width:]
    from_bars = sum(1 for bar in recent if bar.source_period == 5)
    from_metadata = _metadata_cse_session_count(width, metadata_row)
    return max(from_bars, from_metadata)


def _metadata_cse_session_count(
    width: int,
    metadata_row: ResearchBarMetadata | None,
) -> int:
    if metadata_row is None or len(metadata_row.features) <= _CSE_FRACTION_60_INDEX:
        return 0
    fraction = metadata_row.features[_CSE_FRACTION_60_INDEX]
    if not math.isfinite(fraction):
        return 0
    bounded = max(0.0, min(1.0, fraction))
    return int(round(bounded * width))
