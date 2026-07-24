"""Feature Pack v1 research helpers.

Pure functions over ascending ``DailyBar`` history ending at ``as_of`` and a
sample enricher that appends deterministic research columns.
See ``docs/experiments/FEATURE_PACK_V1_SPEC.md``.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.snapshot import FundamentalEvent

FEATURE_PACK_V1_NAMES: tuple[str, ...] = (
    "fp_adv20",
    "fp_adv20_log",
    "fp_zero_volume_streak",
    "fp_no_trade_flag",
    "fp_volume_spike",
    "fp_vol20",
    "fp_vol60",
    "fp_vol_regime",
    "fp_vol_regime_z",
    "fp_ret_1d",
    "fp_rel_ret_1d",
    "fp_rel_ret_5d",
    "fp_rel_ret_1d_market",
    "fp_rel_ret_5d_market",
    "fp_use_sector",
    "fp_days_since_filing",
    "fp_disclosure_proximity",
    "fp_pre_filing_window",
    "fp_post_filing_window",
    "fp_cliff_quarantine",
)

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


def _window_return(prices: list[float], sessions: int) -> float:
    if len(prices) <= sessions:
        return float("nan")
    start, end = prices[-(sessions + 1)], prices[-1]
    if start == 0 or not math.isfinite(start) or not math.isfinite(end):
        return float("nan")
    return (end / start) - 1.0


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


def _vol60(window: list[DailyBar]) -> float:
    prices = [bar.price for bar in window if math.isfinite(bar.price)]
    if len(prices) < 6:
        return float("nan")
    chunk = prices[-61:] if len(prices) >= 61 else prices
    returns = _daily_returns(chunk)
    if len(returns) < 5:
        return float("nan")
    tail = returns[-60:] if len(returns) >= 60 else returns
    return statistics.pstdev(tail)


def _vol_regime(window: list[DailyBar]) -> float:
    prices = [bar.price for bar in window if math.isfinite(bar.price)]
    if len(prices) < 21:
        return float("nan")
    returns = [abs(value) for value in _daily_returns(prices[-21:])]
    if len(returns) < 20:
        return float("nan")
    recent = returns[-5:]
    prior = returns[-20:-5]
    prior_mean = statistics.fmean(prior)
    if prior_mean <= 0:
        return float("nan")
    return statistics.fmean(recent) / prior_mean


def _zero_volume_streak(window: list[DailyBar]) -> float:
    streak = 0
    for bar in reversed(window):
        if bar.volume is None or not math.isfinite(bar.volume) or bar.volume == 0:
            streak += 1
            continue
        break
    return float(streak)


def _finite_median(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return statistics.median(finite) if finite else float("nan")


def load_sector_map_from_json(path: str | Path) -> dict[str, str]:
    """Load ``symbol -> sector`` labels from a JSON object file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("sector map JSON must be an object")
    return {
        str(symbol).strip().upper(): str(sector)
        for symbol, sector in payload.items()
        if str(symbol).strip() and str(sector).strip()
    }


def _sector_medians_for_day(
    day_samples: list[Sample],
    base_rows: dict[int, tuple[float, ...]],
    sector_map: dict[str, str],
) -> dict[str, tuple[float, float]]:
    by_sector: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for sample in day_samples:
        sector = sector_map.get(sample.symbol.strip().upper())
        if not sector:
            continue
        ret_1d, ret_5d = base_rows[id(sample)][8], base_rows[id(sample)][9]
        by_sector[sector].append((ret_1d, ret_5d))
    medians: dict[str, tuple[float, float]] = {}
    for sector, pairs in by_sector.items():
        ret_1d_values = [ret_1d for ret_1d, _ in pairs if math.isfinite(ret_1d)]
        ret_5d_values = [ret_5d for _, ret_5d in pairs if math.isfinite(ret_5d)]
        medians[sector] = (
            _finite_median(ret_1d_values),
            _finite_median(ret_5d_values),
        )
    return medians


def _z_scores(values: list[float]) -> list[float]:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return [float("nan") for _value in values]
    mean = statistics.fmean(finite)
    stdev = statistics.pstdev(finite) if len(finite) > 1 else 0.0
    out: list[float] = []
    for value in values:
        if not math.isfinite(value):
            out.append(float("nan"))
        elif stdev > 0:
            out.append((value - mean) / stdev)
        else:
            out.append(0.0)
    return out


def _filing_features(
    *,
    symbol: str,
    as_of: date,
    fundamentals: dict[str, list[FundamentalEvent]],
) -> tuple[float, float, float, float, float]:
    events = sorted(
        fundamentals.get(symbol, []),
        key=lambda event: event.published_at,
    )
    visible = [event for event in events if event.published_at.date() < as_of]
    if visible:
        latest_date = visible[-1].published_at.date()
        days_since = min(3650.0, float((as_of - latest_date).days))
    else:
        days_since = 4000.0
    pre_window = any(
        0 < (event.published_at.date() - as_of).days <= 5 for event in events
    )
    post_window = any(
        0 <= (as_of - event.published_at.date()).days <= 5 for event in visible
    )
    proximity = pre_window or post_window
    return (
        days_since,
        float(proximity),
        float(pre_window),
        float(post_window),
        0.0,
    )


def _bar_features(
    bars: list[DailyBar],
    *,
    as_of: date,
) -> tuple[float, float, float, float, float, float, float, float, float, float]:
    window = _bars_through_as_of(bars, as_of)
    prices = [bar.price for bar in window if math.isfinite(bar.price)]
    adv = adv20(window)
    adv_log = math.log1p(adv) if math.isfinite(adv) and adv > 0 else float("nan")
    zero_streak = _zero_volume_streak(window)
    last_volume = window[-1].volume if window else None
    volume_spike = (
        last_volume / adv
        if last_volume is not None
        and math.isfinite(last_volume)
        and math.isfinite(adv)
        and adv > 0
        else float("nan")
    )
    ret_1d = _window_return(prices, 1)
    ret_5d = _window_return(prices, 5)
    return (
        adv,
        adv_log,
        zero_streak,
        float(zero_streak >= 3),
        volume_spike,
        vol20(window),
        _vol60(window),
        _vol_regime(window),
        ret_1d,
        ret_5d,
    )


def enrich_feature_pack_v1(
    samples: list[Sample],
    series: dict[str, list[DailyBar]],
    fundamentals: dict[str, list[FundamentalEvent]] | None = None,
    *,
    sector_map: dict[str, str] | None = None,
) -> list[Sample]:
    """Append Feature Pack v1 columns in ``FEATURE_PACK_V1_NAMES`` order."""
    fundamentals = fundamentals or {}
    normalized_sector_map = (
        {symbol.strip().upper(): sector for symbol, sector in sector_map.items()}
        if sector_map
        else None
    )
    series_by_symbol = {symbol.strip().upper(): bars for symbol, bars in series.items()}
    fundamentals_by_symbol = {
        symbol.strip().upper(): events for symbol, events in fundamentals.items()
    }

    base_rows: dict[int, tuple[float, ...]] = {}
    by_day: dict[date, list[Sample]] = defaultdict(list)
    for sample in samples:
        by_day[sample.as_of].append(sample)
        bars = series_by_symbol.get(sample.symbol.strip().upper(), [])
        base_rows[id(sample)] = _bar_features(bars, as_of=sample.as_of)

    out: list[Sample] = []
    for day_samples in by_day.values():
        ret_1d_values = [base_rows[id(sample)][8] for sample in day_samples]
        ret_5d_values = [base_rows[id(sample)][9] for sample in day_samples]
        vol_regime_values = [base_rows[id(sample)][7] for sample in day_samples]
        median_1d = _finite_median(ret_1d_values)
        median_5d = _finite_median(ret_5d_values)
        z_values = _z_scores(vol_regime_values)
        sector_medians = (
            _sector_medians_for_day(day_samples, base_rows, normalized_sector_map)
            if normalized_sector_map
            else {}
        )

        for sample, vol_regime_z in zip(day_samples, z_values, strict=True):
            (
                adv,
                adv_log,
                zero_streak,
                no_trade_flag,
                volume_spike,
                realized_vol20,
                realized_vol60,
                vol_regime,
                ret_1d,
                ret_5d,
            ) = base_rows[id(sample)]
            rel_1d_market = (
                ret_1d - median_1d
                if math.isfinite(ret_1d) and math.isfinite(median_1d)
                else float("nan")
            )
            rel_5d_market = (
                ret_5d - median_5d
                if math.isfinite(ret_5d) and math.isfinite(median_5d)
                else float("nan")
            )
            sector = (
                normalized_sector_map.get(sample.symbol.strip().upper())
                if normalized_sector_map
                else None
            )
            use_sector = 1.0 if sector else 0.0
            if sector and sector in sector_medians:
                sector_median_1d, sector_median_5d = sector_medians[sector]
                rel_1d = (
                    ret_1d - sector_median_1d
                    if math.isfinite(ret_1d) and math.isfinite(sector_median_1d)
                    else float("nan")
                )
                rel_5d = (
                    ret_5d - sector_median_5d
                    if math.isfinite(ret_5d) and math.isfinite(sector_median_5d)
                    else float("nan")
                )
            else:
                rel_1d = rel_1d_market
                rel_5d = rel_5d_market
            filing = _filing_features(
                symbol=sample.symbol.strip().upper(),
                as_of=sample.as_of,
                fundamentals=fundamentals_by_symbol,
            )
            features = (
                adv,
                adv_log,
                zero_streak,
                no_trade_flag,
                volume_spike,
                realized_vol20,
                realized_vol60,
                vol_regime,
                vol_regime_z,
                ret_1d,
                rel_1d,
                rel_5d,
                rel_1d_market,
                rel_5d_market,
                use_sector,
                *filing,
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
