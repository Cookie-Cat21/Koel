"""CSE Market Appetite meter — daily composite score from breadth / intensity.

Not financial advice. Scores are research diagnostics (0–100), never tips.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)

WEIGHT_BREADTH = 0.40
WEIGHT_INTENSITY = 0.25
WEIGHT_INDEX = 0.20
WEIGHT_PARTICIPATION = 0.15

INTENSITY_MOVE_PCT = 2.0
INDEX_CLAMP_PCT = 3.0
PARTICIPATION_Z_CLAMP = 2.0

VALID_SOURCES = frozenset({"cse", "hybrid_research"})


@dataclass(frozen=True, slots=True)
class AppetiteDayResult:
    trade_date: date
    score: float
    band: str
    components: dict[str, float]
    source: str
    universe_n: int
    advancers: int
    decliners: int
    unchanged: int
    aspi_change_pct: float | None


@dataclass(frozen=True, slots=True)
class AppetiteBackfillResult:
    source: str
    dates_targeted: int
    dates_upserted: int
    dates_skipped: int


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def band_for_score(score: float) -> str:
    """Map a 0–100 appetite score to a band label."""
    s = _finite(score)
    if s is None:
        return "neutral"
    s = _clamp(s)
    if s < 20.0:
        return "extreme_caution"
    if s < 40.0:
        return "caution"
    if s < 60.0:
        return "neutral"
    if s < 80.0:
        return "appetite"
    return "strong_appetite"


def map_breadth_score(advancer_share_pct: float) -> float:
    """% advancers → 0–100 (0%→0, 50%→50, 100%→100)."""
    pct = _finite(advancer_share_pct)
    if pct is None:
        return 50.0
    return _clamp(pct)


def map_intensity_score(up_share_among_movers_pct: float | None) -> float:
    """Share of |chg|≥2% names that are up → 0–100; None (no movers) → 50."""
    if up_share_among_movers_pct is None:
        return 50.0
    pct = _finite(up_share_among_movers_pct)
    if pct is None:
        return 50.0
    return _clamp(pct)


def map_index_score(aspi_change_pct: float | None) -> float:
    """ASPI daily change_pct: −3%→0 … 0%→50 … +3%→100."""
    pct = _finite(aspi_change_pct)
    if pct is None:
        return 50.0
    return _clamp((pct + INDEX_CLAMP_PCT) / (2.0 * INDEX_CLAMP_PCT) * 100.0)


def map_participation_z_score(z: float | None) -> float:
    """Turnover z-score → 0–100 via clamp(−2…+2)."""
    val = _finite(z)
    if val is None:
        return 50.0
    return _clamp((val + PARTICIPATION_Z_CLAMP) / (2.0 * PARTICIPATION_Z_CLAMP) * 100.0)


def map_participation_volume_share(share_pct: float) -> float:
    """Share of symbols with volume>0 that day → 0–100 (weak fallback)."""
    pct = _finite(share_pct)
    if pct is None:
        return 50.0
    return _clamp(pct)


def map_participation_volume_total(
    total: float | None,
    history: list[float] | None,
) -> float | None:
    """Market-wide volume sum z-score → 0–100; None if history too thin."""
    t = _finite(total)
    if t is None:
        return None
    hist = [h for h in (history or []) if _finite(h) is not None]
    if len(hist) < 5:
        return None
    z = turnover_zscore(t, hist)
    return map_participation_z_score(z)


def turnover_zscore(value: float, history: list[float]) -> float | None:
    """Sample z-score of ``value`` vs ``history`` (needs ≥2 finite points)."""
    vals = [v for v in history if _finite(v) is not None]
    if len(vals) < 2:
        return None
    mean = statistics.mean(vals)
    stdev = statistics.stdev(vals)
    if stdev == 0.0 or not math.isfinite(stdev):
        return 0.0
    z = (value - mean) / stdev
    return z if math.isfinite(z) else None


def component_scores(
    *,
    change_pcts: list[float],
    volumes: list[float | None] | None = None,
    aspi_change_pct: float | None = None,
    turnover: float | None = None,
    turnover_history: list[float] | None = None,
    volume_total: float | None = None,
    volume_total_history: list[float] | None = None,
) -> dict[str, float]:
    """Component scores (0–100) from one day's breadth inputs.

    ``change_pcts`` are daily % changes for names with a computable change.
    """
    finite_chgs = [c for c in (_finite(x) for x in change_pcts) if c is not None]
    n = len(finite_chgs)
    if n == 0:
        breadth = 50.0
        intensity = 50.0
    else:
        advancers = sum(1 for c in finite_chgs if c > 0.0)
        breadth = map_breadth_score((advancers / n) * 100.0)
        movers = [c for c in finite_chgs if abs(c) >= INTENSITY_MOVE_PCT]
        if not movers:
            intensity = map_intensity_score(None)
        else:
            up = sum(1 for c in movers if c > 0.0)
            intensity = map_intensity_score((up / len(movers)) * 100.0)

    index = map_index_score(aspi_change_pct)

    participation: float
    t = _finite(turnover)
    hist = turnover_history or []
    if t is not None and len([h for h in hist if _finite(h) is not None]) >= 2:
        z = turnover_zscore(t, hist)
        participation = map_participation_z_score(z)
    else:
        via_total = map_participation_volume_total(
            volume_total, volume_total_history
        )
        if via_total is not None:
            participation = via_total
        else:
            # Last resort — share with volume>0 is often ~100% on CSE bars.
            vols = volumes or []
            if vols:
                active = sum(
                    1
                    for v in vols
                    if (vv := _finite(v)) is not None and vv > 0.0
                )
                participation = map_participation_volume_share(
                    (active / len(vols)) * 100.0
                )
            else:
                participation = 50.0

    return {
        "breadth": breadth,
        "intensity": intensity,
        "index": index,
        "participation": participation,
    }


def composite_score(components: dict[str, float]) -> float:
    """Weighted 0–100 appetite score from component dict."""
    score = (
        WEIGHT_BREADTH * float(components.get("breadth", 50.0))
        + WEIGHT_INTENSITY * float(components.get("intensity", 50.0))
        + WEIGHT_INDEX * float(components.get("index", 50.0))
        + WEIGHT_PARTICIPATION * float(components.get("participation", 50.0))
    )
    return _clamp(score)


def _count_breadth(change_pcts: list[float]) -> tuple[int, int, int, int]:
    """Return (universe_n, advancers, decliners, unchanged)."""
    finite = [c for c in (_finite(x) for x in change_pcts) if c is not None]
    adv = sum(1 for c in finite if c > 0.0)
    dec = sum(1 for c in finite if c < 0.0)
    unc = sum(1 for c in finite if c == 0.0)
    return len(finite), adv, dec, unc


def build_day_result(
    *,
    trade_date: date,
    change_pcts: list[float],
    volumes: list[float | None] | None = None,
    aspi_change_pct: float | None = None,
    turnover: float | None = None,
    turnover_history: list[float] | None = None,
    volume_total: float | None = None,
    volume_total_history: list[float] | None = None,
    source: str = "cse",
) -> AppetiteDayResult | None:
    """Build a scored day from breadth inputs. None if no usable changes."""
    src = source if source in VALID_SOURCES else "cse"
    universe_n, adv, dec, unc = _count_breadth(change_pcts)
    if universe_n == 0:
        return None
    comps = component_scores(
        change_pcts=change_pcts,
        volumes=volumes,
        aspi_change_pct=aspi_change_pct,
        turnover=turnover,
        turnover_history=turnover_history,
        volume_total=volume_total,
        volume_total_history=volume_total_history,
    )
    score = composite_score(comps)
    return AppetiteDayResult(
        trade_date=trade_date,
        score=score,
        band=band_for_score(score),
        components=comps,
        source=src,
        universe_n=universe_n,
        advancers=adv,
        decliners=dec,
        unchanged=unc,
        aspi_change_pct=_finite(aspi_change_pct),
    )


async def compute_day(
    storage: Storage,
    trade_date: date,
    *,
    source: str = "cse",
) -> AppetiteDayResult | None:
    """Compute appetite for one trade_date from daily bars (+ market summary)."""
    src = source if source in VALID_SOURCES else "cse"
    rows = await storage.list_daily_bar_changes_for_date(trade_date, source=src)
    if not rows:
        return None
    change_pcts = [r["change_pct"] for r in rows if _finite(r.get("change_pct")) is not None]
    volumes = [r.get("volume") for r in rows]
    aspi_pct = await storage.aspi_change_pct_for_date(trade_date, source=src)
    mkt = await storage.list_market_daily_summary()
    turnover_by_date = {
        r["trade_date"]: _finite(r.get("market_turnover"))
        for r in mkt
        if isinstance(r.get("trade_date"), date)
    }
    turnover = turnover_by_date.get(trade_date)
    history = [
        v
        for d, v in sorted(turnover_by_date.items())
        if d <= trade_date and v is not None
    ]
    result = build_day_result(
        trade_date=trade_date,
        change_pcts=change_pcts,
        volumes=volumes,
        aspi_change_pct=aspi_pct,
        turnover=turnover,
        turnover_history=history,
        source=src,
    )
    if result is None:
        return None
    await storage.upsert_market_appetite_daily(result)
    return result


async def compute_from_snapshots(
    storage: Storage,
    *,
    trade_date: date | None = None,
    source: str = "cse",
) -> AppetiteDayResult | None:
    """Optional live path: latest price_snapshots vs previous_close / change_pct."""
    src = source if source in VALID_SOURCES else "cse"
    snaps = await storage.list_latest_price_snapshots()
    if not snaps:
        return None
    change_pcts: list[float] = []
    volumes: list[float | None] = []
    day = trade_date
    for snap in snaps:
        if snap.symbol.upper() == "ASPI" or snap.symbol.upper() == "MARKET":
            continue
        if day is None:
            day = snap.ts.date()
        pct = _finite(snap.change_pct)
        if pct is None:
            price = _finite(snap.price)
            prev = _finite(snap.previous_close)
            if price is not None and prev is not None and prev != 0.0:
                pct = (price / prev - 1.0) * 100.0
        if pct is None:
            continue
        change_pcts.append(pct)
        volumes.append(_finite(snap.volume))
    if day is None or not change_pcts:
        return None
    aspi_pct = await storage.latest_index_change_pct("ASPI")
    mkt = await storage.list_market_daily_summary()
    turnover_by_date = {
        r["trade_date"]: _finite(r.get("market_turnover"))
        for r in mkt
        if isinstance(r.get("trade_date"), date)
    }
    turnover = turnover_by_date.get(day)
    history = [
        v
        for d, v in sorted(turnover_by_date.items())
        if d <= day and v is not None
    ]
    result = build_day_result(
        trade_date=day,
        change_pcts=change_pcts,
        volumes=volumes,
        aspi_change_pct=aspi_pct,
        turnover=turnover,
        turnover_history=history,
        source=src,
    )
    if result is None:
        return None
    await storage.upsert_market_appetite_daily(result)
    return result


async def backfill_appetite(
    storage: Storage,
    *,
    source: str = "cse",
    force: bool = False,
) -> AppetiteBackfillResult:
    """Compute and upsert appetite for all distinct trade_dates in bars table."""
    src = source if source in VALID_SOURCES else "cse"
    dates = await storage.list_daily_bar_trade_dates(source=src)
    existing: set[date] = set()
    if not force:
        existing = {
            r["trade_date"]
            for r in await storage.list_market_appetite_daily(source=src)
            if isinstance(r.get("trade_date"), date)
        }

    mkt = await storage.list_market_daily_summary()
    turnover_by_date = {
        r["trade_date"]: _finite(r.get("market_turnover"))
        for r in mkt
        if isinstance(r.get("trade_date"), date)
    }
    # Prefetch all change rows once for efficiency.
    all_rows = await storage.list_all_daily_bar_changes(source=src)
    by_date: dict[date, list[dict[str, Any]]] = {}
    for row in all_rows:
        d = row.get("trade_date")
        if not isinstance(d, date):
            continue
        by_date.setdefault(d, []).append(row)

    aspi_by_date = await storage.list_aspi_change_pcts(source=src)

    volume_total_by_date: dict[date, float] = {}
    for d, rows in by_date.items():
        total = 0.0
        any_v = False
        for r in rows:
            vv = _finite(r.get("volume"))
            if vv is None:
                continue
            total += vv
            any_v = True
        if any_v:
            volume_total_by_date[d] = total

    upserted = skipped = 0
    for trade_date in dates:
        if not force and trade_date in existing:
            skipped += 1
            continue
        rows = by_date.get(trade_date) or []
        change_pcts = [
            c
            for r in rows
            if (c := _finite(r.get("change_pct"))) is not None
        ]
        volumes = [r.get("volume") for r in rows]
        turnover = turnover_by_date.get(trade_date)
        history = [
            v
            for d, v in sorted(turnover_by_date.items())
            if d <= trade_date and v is not None
        ]
        vol_hist = [
            v
            for d, v in sorted(volume_total_by_date.items())
            if d <= trade_date
        ]
        result = build_day_result(
            trade_date=trade_date,
            change_pcts=change_pcts,
            volumes=volumes,
            aspi_change_pct=aspi_by_date.get(trade_date),
            turnover=turnover,
            turnover_history=history,
            volume_total=volume_total_by_date.get(trade_date),
            volume_total_history=vol_hist,
            source=src,
        )
        if result is None:
            skipped += 1
            continue
        await storage.upsert_market_appetite_daily(result)
        upserted += 1

    out = AppetiteBackfillResult(
        source=src,
        dates_targeted=len(dates),
        dates_upserted=upserted,
        dates_skipped=skipped,
    )
    log.info("appetite_backfill_done", **asdict(out))
    return out
