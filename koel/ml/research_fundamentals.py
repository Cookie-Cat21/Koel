"""Publication-time-safe filing features for distributed ML research."""

from __future__ import annotations

import math
from collections import defaultdict

from koel.ml.dataset import Sample
from koel.ml.snapshot import FundamentalEvent

FUNDAMENTAL_FEATURE_NAMES: tuple[str, ...] = (
    "has_filing",
    "days_since_filing",
    "filings_90d",
    "filings_365d",
    "latest_is_quarterly",
    "days_since_fiscal_period",
    "log_revenue",
    "log_profit",
    "signed_log_eps",
    "eps_yoy_clipped",
    "revenue_yoy_clipped",
    "profit_yoy_clipped",
    "has_usable_yoy",
)


def _signed_log(value: float | None) -> float:
    if value is None or not math.isfinite(value):
        return float("nan")
    return math.copysign(math.log1p(abs(value)), value)


def _clipped_percent(value: float | None) -> float:
    if value is None or not math.isfinite(value):
        return float("nan")
    return max(-10.0, min(10.0, value / 100.0))


def enrich_fundamentals(
    samples: list[Sample],
    fundamentals: dict[str, list[FundamentalEvent]],
) -> list[Sample]:
    """Append only filings published before each sample's decision date."""
    by_symbol: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        by_symbol[sample.symbol].append(sample)

    out: list[Sample] = []
    for symbol, symbol_samples in by_symbol.items():
        ordered_samples = sorted(symbol_samples, key=lambda sample: sample.as_of)
        events = sorted(
            fundamentals.get(symbol, []),
            key=lambda event: event.published_at,
        )
        available: list[FundamentalEvent] = []
        event_index = 0
        for sample in ordered_samples:
            while (
                event_index < len(events)
                and events[event_index].published_at.date() < sample.as_of
            ):
                available.append(events[event_index])
                event_index += 1
            if available:
                latest = available[-1]
                latest_date = latest.published_at.date()
                filings_90 = sum(
                    1
                    for event in available
                    if 0 <= (sample.as_of - event.published_at.date()).days <= 90
                )
                filings_365 = sum(
                    1
                    for event in available
                    if 0 <= (sample.as_of - event.published_at.date()).days <= 365
                )
                fiscal_age = (
                    min(3650.0, float((sample.as_of - latest.fiscal_period_end).days))
                    if latest.fiscal_period_end is not None
                    else float("nan")
                )
                has_yoy = latest.match_quality in {"exact_yoy", "approx_yoy"}
                features = (
                    1.0,
                    min(3650.0, float((sample.as_of - latest_date).days)),
                    float(filings_90),
                    float(filings_365),
                    float(latest.kind == "quarterly"),
                    fiscal_age,
                    _signed_log(latest.revenue),
                    _signed_log(latest.profit),
                    _signed_log(latest.eps_basic),
                    _clipped_percent(latest.eps_delta_pct),
                    _clipped_percent(latest.revenue_delta_pct),
                    _clipped_percent(latest.profit_delta_pct),
                    float(has_yoy),
                )
            else:
                features = (
                    0.0,
                    4000.0,
                    0.0,
                    0.0,
                    0.0,
                    float("nan"),
                    float("nan"),
                    float("nan"),
                    float("nan"),
                    float("nan"),
                    float("nan"),
                    float("nan"),
                    0.0,
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
    return sorted(out, key=lambda sample: (sample.as_of, sample.symbol))
