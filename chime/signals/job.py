"""Batch Signal Board scoring from ``daily_bars`` → ``symbol_scores``."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from chime.domain import DailyBar
from chime.logging_setup import get_logger
from chime.signals.forecast import forecast_path
from chime.signals.score import (
    MODEL_VERSION,
    ExtraFactors,
    score_symbol_path,
)
from chime.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SignalScoreResult:
    symbols_targeted: int
    symbols_scored: int
    symbols_skipped: int
    forecasts_written: int
    model_version: str


def _window_return_from_bars(bars: list[DailyBar], n: int = 20) -> float | None:
    """20-session return from daily bars."""
    ordered = sorted(bars, key=lambda b: b.trade_date)
    prices = [b.price for b in ordered if math.isfinite(b.price)]
    if len(prices) <= n:
        return None
    start, end = prices[-(n + 1)], prices[-1]
    if start == 0 or not math.isfinite(start) or not math.isfinite(end):
        return None
    return (end / start) - 1.0


async def _sector_peer_ret_20d(
    storage: Storage,
    *,
    symbol: str,
    cache: dict[str, float | None],
) -> float | None:
    sector = await storage.get_stock_sector(symbol)
    if sector is None:
        return None
    if sector in cache:
        return cache[sector]
    peers = await storage.list_symbols_in_sector(sector)
    rets: list[float] = []
    for peer in peers:
        if peer == symbol:
            continue
        peer_bars = await storage.list_daily_bars(peer)
        ret = _window_return_from_bars(peer_bars, 20)
        if ret is not None:
            rets.append(ret)
    value = statistics.median(rets) if len(rets) >= 2 else None
    cache[sector] = value
    return value


async def run_signal_score_job(
    *,
    storage: Storage,
    limit: int | None = None,
    model_version: str = MODEL_VERSION,
) -> SignalScoreResult:
    """Score all symbols that have daily bars (or first ``limit`` symbols)."""
    symbols = await storage.list_symbols_with_daily_bars()
    if (
        limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
    ):
        symbols = symbols[:limit]

    scored = 0
    skipped = 0
    forecasts = 0
    peer_cache: dict[str, float | None] = {}
    since = datetime.now(UTC) - timedelta(days=30)
    aspi_pct = await storage.latest_index_change_pct("ASPI")

    for symbol in symbols:
        bars = await storage.list_daily_bars(symbol)
        yoy = await storage.get_latest_filing_yoy(symbol)
        peer_ret = await _sector_peer_ret_20d(
            storage, symbol=symbol, cache=peer_cache
        )
        disc_n = await storage.count_disclosures_since(symbol, since=since)
        cats = await storage.count_disclosure_categories_since(symbol, since=since)
        fin_share: float | None = None
        if cats and disc_n > 0:
            fin_n = 0
            for cat, n in cats.items():
                low = cat.lower()
                if any(
                    key in low
                    for key in (
                        "financial",
                        "interim",
                        "annual",
                        "quarter",
                        "accounts",
                        "earnings",
                    )
                ):
                    fin_n += n
            fin_share = fin_n / float(disc_n)
        extra = ExtraFactors(
            eps_yoy_pct=yoy.get("eps_yoy_pct"),
            rev_yoy_pct=yoy.get("rev_yoy_pct"),
            profit_yoy_pct=yoy.get("profit_yoy_pct"),
            sector_peer_ret_20d=peer_ret,
            disclosure_count_30d=disc_n if disc_n > 0 else None,
            financial_disclosure_share=fin_share,
            aspi_change_pct=aspi_pct,
        )
        result = score_symbol_path(
            bars, extra=extra, model_version=model_version
        )
        if result is None:
            skipped += 1
            continue
        await storage.upsert_symbol_score(
            symbol=result.symbol,
            as_of=result.as_of,
            model_version=model_version,
            score=result.score,
            components=result.components,
            reasons=result.reasons,
            bar_count=result.bar_count,
        )
        scored += 1
        points = forecast_path(bars)
        if points:
            forecasts += await storage.replace_forecast_points(points)

    out = SignalScoreResult(
        symbols_targeted=len(symbols),
        symbols_scored=scored,
        symbols_skipped=skipped,
        forecasts_written=forecasts,
        model_version=model_version,
    )
    log.info("signal_score_job_done", **asdict(out))
    return out
