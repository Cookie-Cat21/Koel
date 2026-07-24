"""Point-in-time training sample weights for ML research runs."""

from __future__ import annotations

import math
from bisect import bisect_right

from koel.domain import DailyBar
from koel.ml.dataset import Sample

MIN_SAMPLE_WEIGHT = 0.25
MAX_SAMPLE_WEIGHT = 4.0


def adv20_sample_weights(
    samples: list[Sample],
    series: dict[str, list[DailyBar]],
) -> list[float]:
    """Return ADV20 log-volume weights aligned to ``samples``.

    For each sample, ADV is the mean finite non-negative volume over the last
    up-to-20 bars for that symbol with ``trade_date <= sample.as_of``. Missing
    symbol history or missing volumes stay neutral at 1.0.
    """
    prepared = {
        symbol: sorted(bars, key=lambda bar: bar.trade_date)
        for symbol, bars in series.items()
    }
    dates = {
        symbol: [bar.trade_date for bar in bars]
        for symbol, bars in prepared.items()
    }

    log_advs: list[float | None] = []
    for sample in samples:
        bars = prepared.get(sample.symbol)
        symbol_dates = dates.get(sample.symbol)
        if not bars or not symbol_dates:
            log_advs.append(None)
            continue
        end = bisect_right(symbol_dates, sample.as_of)
        if end <= 0:
            log_advs.append(None)
            continue
        window = bars[max(0, end - 20) : end]
        volumes = [
            float(bar.volume)
            for bar in window
            if bar.volume is not None
            and math.isfinite(float(bar.volume))
            and float(bar.volume) >= 0.0
        ]
        if not volumes:
            log_advs.append(None)
            continue
        adv = sum(volumes) / len(volumes)
        log_advs.append(math.log1p(adv) if math.isfinite(adv) else None)

    observed = [value for value in log_advs if value is not None and math.isfinite(value)]
    mean_log_adv = sum(observed) / len(observed) if observed else 0.0
    if mean_log_adv <= 0.0:
        return [1.0] * len(samples)

    weights: list[float] = []
    for value in log_advs:
        if value is None or not math.isfinite(value):
            weights.append(1.0)
            continue
        raw = value / mean_log_adv
        weights.append(max(MIN_SAMPLE_WEIGHT, min(MAX_SAMPLE_WEIGHT, raw)))
    return weights
