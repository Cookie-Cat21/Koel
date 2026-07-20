"""YoY prior-period pairing + delta computation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


@dataclass(frozen=True)
class MetricsRow:
    id: int | None
    symbol: str
    kind: str
    fiscal_period_end: date | None
    fiscal_quarter: int | None
    entity: str
    scale: str
    currency: str
    revenue: float | None
    profit: float | None
    eps_basic: float | None
    extract_ok: bool


@dataclass(frozen=True)
class ComparisonResult:
    prior_id: int | None
    match_quality: str
    eps_delta: float | None = None
    eps_delta_pct: float | None = None
    revenue_delta: float | None = None
    revenue_delta_pct: float | None = None
    profit_delta: float | None = None
    profit_delta_pct: float | None = None


_EXACT_DAYS = 20
_APPROX_DAYS = 45


def _finite(v: float | None) -> bool:
    return v is not None and isinstance(v, (int, float)) and math.isfinite(float(v))


def _delta_pct(new: float | None, old: float | None) -> tuple[float | None, float | None]:
    if not (_finite(new) and _finite(old)):
        return None, None
    assert new is not None and old is not None
    delta = float(new) - float(old)
    if abs(float(old)) < 1e-12:
        return delta, None  # undefined %
    return delta, (delta / abs(float(old))) * 100.0


def scale_factor(scale: str) -> float | None:
    return {
        "units": 1.0,
        "thousands": 1_000.0,
        "millions": 1_000_000.0,
    }.get(scale)


def normalize_amount(value: float | None, scale: str) -> float | None:
    if value is None or not _finite(value):
        return None
    factor = scale_factor(scale)
    if factor is None:
        return None
    return float(value) * factor


def resolve_prior(
    current: MetricsRow,
    candidates: list[MetricsRow],
) -> ComparisonResult:
    """Pick best prior-year comparable filing and compute deltas.

    Fail closed to ``missing_prior`` / mismatch qualities — never invent a prior.
    """
    if not current.extract_ok or current.fiscal_period_end is None:
        return ComparisonResult(prior_id=None, match_quality="skipped")
    if current.currency.upper() != "LKR":
        return ComparisonResult(prior_id=None, match_quality="currency_mismatch")

    target = current.fiscal_period_end - timedelta(days=365)
    best: tuple[int, MetricsRow, str] | None = None  # (days_off, row, quality)

    for row in candidates:
        if row.id is None or row.id == current.id:
            continue
        if not row.extract_ok or row.fiscal_period_end is None:
            continue
        if row.symbol != current.symbol or row.kind != current.kind:
            continue
        if row.currency.upper() != current.currency.upper():
            continue
        if (
            current.entity in ("group", "company")
            and row.entity in ("group", "company")
            and row.entity != current.entity
        ):
            continue
        if current.kind == "quarterly" and (
            current.fiscal_quarter is not None
            and row.fiscal_quarter is not None
            and row.fiscal_quarter != current.fiscal_quarter
        ):
            continue
        days_off = abs((row.fiscal_period_end - target).days)
        if days_off > _APPROX_DAYS:
            continue
        quality = "exact_yoy" if days_off <= _EXACT_DAYS else "approx_yoy"
        if best is None or days_off < best[0]:
            best = (days_off, row, quality)

    if best is None:
        return ComparisonResult(prior_id=None, match_quality="missing_prior")

    _, prior, quality = best
    if (
        (scale_factor(current.scale) is None or scale_factor(prior.scale) is None)
        and current.scale != prior.scale
        and current.scale != "unknown"
        and prior.scale != "unknown"
    ):
        return ComparisonResult(
            prior_id=prior.id,
            match_quality="scale_mismatch",
        )

    # Normalize rev/profit when scales differ but both known
    cur_rev = normalize_amount(current.revenue, current.scale) or current.revenue
    pri_rev = normalize_amount(prior.revenue, prior.scale) or prior.revenue
    cur_pat = normalize_amount(current.profit, current.scale) or current.profit
    pri_pat = normalize_amount(prior.profit, prior.scale) or prior.profit

    if (
        current.scale != prior.scale
        and current.scale != "unknown"
        and prior.scale != "unknown"
        and (
            scale_factor(current.scale) is None
            or scale_factor(prior.scale) is None
            or normalize_amount(current.revenue, current.scale) is None
        )
    ):
        return ComparisonResult(prior_id=prior.id, match_quality="scale_mismatch")

    eps_d, eps_p = _delta_pct(current.eps_basic, prior.eps_basic)
    rev_d, rev_p = _delta_pct(cur_rev, pri_rev)
    pat_d, pat_p = _delta_pct(cur_pat, pri_pat)

    return ComparisonResult(
        prior_id=prior.id,
        match_quality=quality,
        eps_delta=eps_d,
        eps_delta_pct=eps_p,
        revenue_delta=rev_d,
        revenue_delta_pct=rev_p,
        profit_delta=pat_d,
        profit_delta_pct=pat_p,
    )


def comparison_to_dict(result: ComparisonResult) -> dict[str, Any]:
    return {
        "prior_filing_metrics_id": result.prior_id,
        "match_quality": result.match_quality,
        "eps_delta": result.eps_delta,
        "eps_delta_pct": result.eps_delta_pct,
        "revenue_delta": result.revenue_delta,
        "revenue_delta_pct": result.revenue_delta_pct,
        "profit_delta": result.profit_delta,
        "profit_delta_pct": result.profit_delta_pct,
    }
