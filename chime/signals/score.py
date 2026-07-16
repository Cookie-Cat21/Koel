"""Transparent research scores (path_v0 / path_v1).

Higher score ≠ buy. Components are explainable factors from ``daily_bars``
plus optional filing YoY / sector-peer relative strength. Reasons must pass
buy/sell guardrails.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date

from chime.domain import DailyBar
from chime.scenarios.guardrails import (
    GuardrailViolation,
    assert_safe_scenario_output,
)

MODEL_VERSION = "path_v2"
MODEL_VERSION_V1 = "path_v1"
MODEL_VERSION_V0 = "path_v0"


@dataclass(frozen=True, slots=True)
class ExtraFactors:
    """Optional non-path inputs for ``path_v2`` (all fail-closed / optional)."""

    eps_yoy_pct: float | None = None
    rev_yoy_pct: float | None = None
    profit_yoy_pct: float | None = None
    sector_peer_ret_20d: float | None = None
    disclosure_count_30d: int | None = None
    # Share of recent disclosures in financial-ish categories (0–1).
    financial_disclosure_share: float | None = None
    # Latest ASPI change in percent points (e.g. 0.14 = +0.14%).
    aspi_change_pct: float | None = None


@dataclass(frozen=True, slots=True)
class ScoreResult:
    symbol: str
    as_of: date
    score: float
    components: dict[str, float | None]
    reasons: list[str]
    bar_count: int
    model_version: str = MODEL_VERSION


def _returns(prices: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        cur = prices[i]
        if prev == 0 or not math.isfinite(prev) or not math.isfinite(cur):
            continue
        out.append((cur / prev) - 1.0)
    return out


def _window_return(prices: list[float], n: int) -> float | None:
    if len(prices) <= n:
        return None
    start = prices[-(n + 1)]
    end = prices[-1]
    if start == 0 or not math.isfinite(start) or not math.isfinite(end):
        return None
    return (end / start) - 1.0


def _safe_reason(text: str) -> str | None:
    try:
        return assert_safe_scenario_output(text)
    except GuardrailViolation:
        return None


def _finite_opt(value: float | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def score_symbol_path(
    bars: list[DailyBar],
    *,
    extra: ExtraFactors | None = None,
    model_version: str = MODEL_VERSION,
) -> ScoreResult | None:
    """Score one symbol from ascending daily bars. ``None`` if < 5 bars."""
    if not bars:
        return None
    ordered = sorted(bars, key=lambda b: b.trade_date)
    symbol = ordered[-1].symbol
    as_of = ordered[-1].trade_date
    prices = [b.price for b in ordered if math.isfinite(b.price)]
    if len(prices) < 5:
        return None

    ret_5 = _window_return(prices, 5)
    ret_20 = _window_return(prices, 20)
    ret_60 = _window_return(prices, 60)
    rets_20 = _returns(prices[-21:]) if len(prices) >= 21 else _returns(prices)
    vol_20 = statistics.pstdev(rets_20) if len(rets_20) >= 5 else None

    vols = [
        b.volume
        for b in ordered[-20:]
        if b.volume is not None and math.isfinite(b.volume)
    ]
    liq = statistics.fmean(vols) if vols else None

    last_vol = ordered[-1].volume
    vol_spike: float | None = None
    if (
        last_vol is not None
        and math.isfinite(last_vol)
        and liq is not None
        and liq > 0
    ):
        vol_spike = last_vol / liq

    # F-004: average intraday range (high-low)/price over last 20 bars.
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
    range_20 = statistics.fmean(ranges) if ranges else None

    # F-012: volume regime — recent 5d avg / prior 15d avg.
    vol_series = [
        b.volume
        for b in ordered
        if b.volume is not None and math.isfinite(b.volume) and b.volume > 0
    ]
    vol_regime: float | None = None
    if len(vol_series) >= 20:
        recent = statistics.fmean(vol_series[-5:])
        prior = statistics.fmean(vol_series[-20:-5])
        if prior > 0:
            vol_regime = recent / prior

    # Proxy turnover (volume * price) log tilt — F-012 companion.
    turnovers = [
        b.volume * b.price
        for b in ordered[-20:]
        if b.volume is not None
        and math.isfinite(b.volume)
        and b.volume > 0
        and math.isfinite(b.price)
        and b.price > 0
    ]
    turnover_20 = statistics.fmean(turnovers) if turnovers else None

    ret_1 = _window_return(prices, 1)

    mom = 0.0
    mom_w = 0.0
    if ret_5 is not None:
        mom += ret_5 * 40.0
        mom_w += 1.0
    if ret_20 is not None:
        mom += ret_20 * 35.0
        mom_w += 1.0
    if ret_60 is not None:
        mom += ret_60 * 25.0
        mom_w += 1.0
    mom_term = mom if mom_w else 0.0

    vol_penalty = 0.0
    if vol_20 is not None:
        vol_penalty = min(40.0, vol_20 * 400.0)

    liq_term = 0.0
    if liq is not None and liq > 0:
        liq_term = min(15.0, math.log10(liq + 1.0) * 3.0)

    vol_spike_term = 0.0
    if vol_spike is not None and vol_spike > 1.5:
        # Mild activity tilt — capped; not a tip.
        vol_spike_term = min(8.0, (vol_spike - 1.5) * 2.0)

    # Wide range = riskier — small penalty (F-004).
    range_penalty = 0.0
    if range_20 is not None:
        range_penalty = min(10.0, range_20 * 80.0)

    vol_regime_term = 0.0
    if vol_regime is not None and vol_regime > 1.2:
        vol_regime_term = min(6.0, (vol_regime - 1.2) * 4.0)

    turnover_term = 0.0
    if turnover_20 is not None and turnover_20 > 0:
        turnover_term = min(8.0, math.log10(turnover_20 + 1.0) * 1.2)

    extras = extra or ExtraFactors()
    eps_yoy = _finite_opt(extras.eps_yoy_pct)
    rev_yoy = _finite_opt(extras.rev_yoy_pct)
    profit_yoy = _finite_opt(extras.profit_yoy_pct)
    peer_ret = _finite_opt(extras.sector_peer_ret_20d)
    fin_share = _finite_opt(extras.financial_disclosure_share)
    aspi_pct = _finite_opt(extras.aspi_change_pct)
    disc_30 = extras.disclosure_count_30d
    if isinstance(disc_30, bool) or not isinstance(disc_30, int) or disc_30 < 0:
        disc_30 = None

    # Filing YoY: percentages are already in % points from extract (e.g. 12.5).
    filing_term = 0.0
    if eps_yoy is not None:
        filing_term += max(-12.0, min(12.0, eps_yoy / 10.0))
    if rev_yoy is not None:
        filing_term += max(-8.0, min(8.0, rev_yoy / 15.0))
    if profit_yoy is not None:
        filing_term += max(-8.0, min(8.0, profit_yoy / 15.0))

    rs_term = 0.0
    rs_gap: float | None = None
    if ret_20 is not None and peer_ret is not None:
        rs_gap = ret_20 - peer_ret
        rs_term = max(-15.0, min(15.0, rs_gap * 80.0))

    disc_term = 0.0
    if disc_30 is not None and disc_30 > 0:
        disc_term = min(5.0, float(disc_30) * 0.5)

    # F-042: financial filing intensity (more financial disclosures → mild tilt).
    fin_disc_term = 0.0
    if fin_share is not None and fin_share > 0:
        fin_disc_term = min(6.0, fin_share * 8.0)

    # F-022: same-session path vs latest ASPI change (percent points).
    aspi_rs_term = 0.0
    aspi_gap: float | None = None
    if ret_1 is not None and aspi_pct is not None:
        # ret_1 is fraction; aspi_pct is percent points (0.14 ≈ 0.14%).
        aspi_gap = (ret_1 * 100.0) - aspi_pct
        aspi_rs_term = max(-8.0, min(8.0, aspi_gap * 2.0))

    raw = (
        mom_term
        - vol_penalty
        + liq_term
        + vol_spike_term
        + filing_term
        + rs_term
        + disc_term
        - range_penalty
        + vol_regime_term
        + turnover_term
        + fin_disc_term
        + aspi_rs_term
    )
    score = max(-100.0, min(100.0, raw))

    components: dict[str, float | None] = {
        "ret_1d": ret_1,
        "ret_5d": ret_5,
        "ret_20d": ret_20,
        "ret_60d": ret_60,
        "vol_20d": vol_20,
        "liquidity_20d": liq,
        "vol_spike": vol_spike,
        "range_20d": range_20,
        "vol_regime": vol_regime,
        "turnover_20d": turnover_20,
        "mom_term": mom_term,
        "vol_penalty": vol_penalty,
        "liq_term": liq_term,
        "vol_spike_term": vol_spike_term,
        "range_penalty": range_penalty,
        "vol_regime_term": vol_regime_term,
        "turnover_term": turnover_term,
        "eps_yoy_pct": eps_yoy,
        "rev_yoy_pct": rev_yoy,
        "profit_yoy_pct": profit_yoy,
        "filing_term": filing_term,
        "sector_peer_ret_20d": peer_ret,
        "rs_gap_20d": rs_gap,
        "rs_term": rs_term,
        "disclosure_count_30d": float(disc_30) if disc_30 is not None else None,
        "disc_term": disc_term,
        "financial_disclosure_share": fin_share,
        "fin_disc_term": fin_disc_term,
        "aspi_change_pct": aspi_pct,
        "aspi_gap_1d": aspi_gap,
        "aspi_rs_term": aspi_rs_term,
    }

    reasons: list[str] = []
    if ret_20 is not None:
        pct = ret_20 * 100.0
        direction = "up" if pct >= 0 else "down"
        r = _safe_reason(f"20-session path {direction} {abs(pct):.1f}%")
        if r:
            reasons.append(r)
    if ret_5 is not None and (ret_20 is None or abs(ret_5 - ret_20) > 0.01):
        pct = ret_5 * 100.0
        direction = "up" if pct >= 0 else "down"
        r = _safe_reason(f"5-session path {direction} {abs(pct):.1f}%")
        if r:
            reasons.append(r)
    if vol_20 is not None:
        r = _safe_reason(f"20-session daily volatility {vol_20 * 100.0:.2f}%")
        if r:
            reasons.append(r)
    if vol_spike is not None and vol_spike > 1.5:
        r = _safe_reason(f"Latest volume {vol_spike:.1f}× 20-session average")
        if r:
            reasons.append(r)
    if liq is not None and liq > 0:
        r = _safe_reason(f"Avg 20-session volume {liq:,.0f} shares")
        if r:
            reasons.append(r)
    if eps_yoy is not None:
        direction = "up" if eps_yoy >= 0 else "down"
        r = _safe_reason(f"Latest filing EPS YoY {direction} {abs(eps_yoy):.1f}%")
        if r:
            reasons.append(r)
    if rev_yoy is not None and (eps_yoy is None or abs(rev_yoy) > abs(eps_yoy)):
        direction = "up" if rev_yoy >= 0 else "down"
        r = _safe_reason(f"Latest filing revenue YoY {direction} {abs(rev_yoy):.1f}%")
        if r:
            reasons.append(r)
    if rs_gap is not None:
        direction = "ahead of" if rs_gap >= 0 else "behind"
        r = _safe_reason(
            f"20-session path {direction} sector peers by {abs(rs_gap) * 100.0:.1f} pts"
        )
        if r:
            reasons.append(r)
    if disc_30 is not None and disc_30 > 0:
        r = _safe_reason(f"{disc_30} disclosure(s) in last 30 days")
        if r:
            reasons.append(r)
    if range_20 is not None and range_20 > 0.03:
        r = _safe_reason(f"Avg 20-session range {range_20 * 100.0:.1f}% of price")
        if r:
            reasons.append(r)
    if vol_regime is not None and vol_regime > 1.2:
        r = _safe_reason(f"Recent volume {vol_regime:.1f}× prior 15-session avg")
        if r:
            reasons.append(r)
    if fin_share is not None and fin_share >= 0.4:
        r = _safe_reason(
            f"Financial-category disclosures {fin_share * 100.0:.0f}% of last 30d"
        )
        if r:
            reasons.append(r)
    if aspi_gap is not None and abs(aspi_gap) >= 0.5:
        direction = "ahead of" if aspi_gap >= 0 else "behind"
        r = _safe_reason(
            f"Latest session {direction} ASPI by {abs(aspi_gap):.2f} pts"
        )
        if r:
            reasons.append(r)
    if len(prices) < 60:
        r = _safe_reason(
            f"Limited history ({len(prices)} daily bars; max CSE path ~1y)"
        )
        if r:
            reasons.append(r)
    if not reasons:
        r = _safe_reason("Path factors available; research score only — not advice")
        if r:
            reasons.append(r)

    version = model_version.strip() if isinstance(model_version, str) else MODEL_VERSION
    if not version:
        version = MODEL_VERSION

    return ScoreResult(
        symbol=symbol,
        as_of=as_of,
        score=score,
        components=components,
        reasons=reasons,
        bar_count=len(prices),
        model_version=version,
    )
