"""Build hybrid Yahoo + CSE daily bars → ``hybrid_daily_bars``.

Splice rules (locked):
1. CSE ``daily_bars`` always win on overlapping dates.
2. Yahoo fills only dates **before** the symbol's first CSE bar
   (and never on/after ``YAHOO_STALE_CUTOFF`` — feed went flat/wrong).
3. CSE ``daily_bars`` stay the product spine; hybrid is ML/research only.

Flag: ``HYBRID_BACKFILL_ENABLED`` (default 0). CLI may ``--force``.
Yahoo Finance has no official API; uses ``yfinance`` unofficially.
Not financial advice. Do not redistribute Yahoo rows as CSE truth.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from chime.config import Settings
from chime.domain import DailyBar
from chime.logging_setup import get_logger
from chime.storage import Storage

log = get_logger(__name__)

COLOMBO = ZoneInfo("Asia/Colombo")
# Empirically Yahoo CSE closes matched CSE until ~2026-02-18, then went stale.
DEFAULT_YAHOO_STALE_CUTOFF = date(2026, 2, 18)


@dataclass(frozen=True, slots=True)
class HybridSymbolResult:
    symbol: str
    yahoo_ticker: str
    cse_bars: int
    yahoo_fetched: int
    yahoo_kept: int
    upserted: int
    skipped_reason: str | None = None


@dataclass(frozen=True, slots=True)
class HybridBackfillResult:
    symbols_targeted: int
    symbols_ok: int
    symbols_skipped: int
    symbols_failed: int
    bars_upserted: int
    yahoo_bars_kept: int
    cse_bars_copied: int


def cse_symbol_to_yahoo(symbol: str) -> str | None:
    """Map CSE ``JKH.N0000`` → Yahoo ``JKH-N0000.CM``."""
    if not isinstance(symbol, str) or not symbol.strip():
        return None
    sym = symbol.strip().upper()
    if sym == "ASPI":
        return None
    # Prefer ordinary / voting lines; still try others.
    if "." not in sym:
        return f"{sym}.CM"
    base, suffix = sym.split(".", 1)
    if not base or not suffix:
        return None
    return f"{base}-{suffix}.CM"


def splice_bars(
    *,
    symbol: str,
    cse_bars: list[DailyBar],
    yahoo_rows: list[tuple[date, float, float | None, float | None, float | None, float | None]],
    yahoo_ticker: str,
    stale_cutoff: date = DEFAULT_YAHOO_STALE_CUTOFF,
) -> list[dict]:
    """Return hybrid row dicts: CSE everywhere it exists; Yahoo only before CSE start."""
    by_date: dict[date, dict] = {}
    cse_dates = sorted(b.trade_date for b in cse_bars)
    cse_start = cse_dates[0] if cse_dates else None

    for b in cse_bars:
        if not math.isfinite(b.price) or b.price <= 0:
            continue
        by_date[b.trade_date] = {
            "symbol": symbol,
            "trade_date": b.trade_date,
            "price": float(b.price),
            "high": b.high,
            "low": b.low,
            "open": b.open,
            "volume": b.volume,
            "source": "cse",
            "yahoo_ticker": None,
            "bar_ts": b.bar_ts,
        }

    yahoo_kept = 0
    for trade_date, price, high, low, open_, volume in yahoo_rows:
        if trade_date >= stale_cutoff:
            continue
        if cse_start is not None and trade_date >= cse_start:
            # Overlap / CSE coverage — never override with Yahoo.
            continue
        if trade_date in by_date:
            continue
        if not math.isfinite(price) or price <= 0:
            continue
        bar_ts = datetime.combine(trade_date, time(14, 30), tzinfo=COLOMBO).astimezone(
            UTC
        )
        by_date[trade_date] = {
            "symbol": symbol,
            "trade_date": trade_date,
            "price": float(price),
            "high": float(high) if high is not None and math.isfinite(high) else None,
            "low": float(low) if low is not None and math.isfinite(low) else None,
            "open": float(open_) if open_ is not None and math.isfinite(open_) else None,
            "volume": float(volume)
            if volume is not None and math.isfinite(volume)
            else None,
            "source": "yahoo",
            "yahoo_ticker": yahoo_ticker,
            "bar_ts": bar_ts,
        }
        yahoo_kept += 1

    rows = [by_date[d] for d in sorted(by_date)]
    # Attach kept count via attribute for callers (pure function returns rows only).
    return rows


def fetch_yahoo_history(
    yahoo_ticker: str,
    *,
    period: str = "max",
) -> list[tuple[date, float, float | None, float | None, float | None, float | None]]:
    """Download Yahoo OHLCV via yfinance. Empty list on miss/error."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance not installed — pip install -e '.[hybrid]' or pip install yfinance"
        ) from exc

    ticker = yf.Ticker(yahoo_ticker)
    # history() is more reliable than download for single symbols
    hist = ticker.history(period=period, auto_adjust=False)
    if hist is None or getattr(hist, "empty", True):
        return []

    out: list[tuple[date, float, float | None, float | None, float | None, float | None]] = []
    for idx, row in hist.iterrows():
        try:
            if hasattr(idx, "date") or isinstance(idx, datetime):
                d = idx.date()
            else:
                d = date.fromisoformat(str(idx)[:10])
        except (TypeError, ValueError):
            continue
        try:
            close = float(row["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(close) or close <= 0:
            continue

        def _opt(key: str, series_row: object = row) -> float | None:
            try:
                v = float(series_row[key])  # type: ignore[index]
            except (KeyError, TypeError, ValueError):
                return None
            return v if math.isfinite(v) else None

        out.append((d, close, _opt("High"), _opt("Low"), _opt("Open"), _opt("Volume")))
    return out


async def run_hybrid_backfill(
    *,
    settings: Settings,
    storage: Storage,
    force: bool = False,
    limit: int | None = None,
    sleep_seconds: float | None = None,
    stale_cutoff: date | None = None,
) -> HybridBackfillResult:
    """Backfill ``hybrid_daily_bars`` for symbols that have CSE ``daily_bars``."""
    if not force and not settings.hybrid_backfill_enabled:
        log.info("hybrid_backfill_disabled")
        return HybridBackfillResult(0, 0, 0, 0, 0, 0, 0)

    cutoff = stale_cutoff or settings.yahoo_stale_cutoff
    pause = (
        sleep_seconds
        if sleep_seconds is not None
        else settings.hybrid_backfill_sleep_seconds
    )

    symbols = await storage.list_symbols_with_daily_bars()
    if (
        limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
    ):
        symbols = symbols[:limit]

    ok = 0
    skipped = 0
    failed = 0
    upserted = 0
    yahoo_kept_total = 0
    cse_copied = 0

    import asyncio

    for symbol in symbols:
        yahoo_ticker = cse_symbol_to_yahoo(symbol)
        if yahoo_ticker is None:
            skipped += 1
            log.info("hybrid_skip_no_ticker", symbol=symbol)
            continue
        try:
            cse_bars = await storage.list_daily_bars(symbol)
            yahoo_rows = await asyncio.to_thread(fetch_yahoo_history, yahoo_ticker)
            rows = splice_bars(
                symbol=symbol,
                cse_bars=cse_bars,
                yahoo_rows=yahoo_rows,
                yahoo_ticker=yahoo_ticker,
                stale_cutoff=cutoff,
            )
            yahoo_n = sum(1 for r in rows if r["source"] == "yahoo")
            cse_n = sum(1 for r in rows if r["source"] == "cse")
            n = await storage.persist_hybrid_daily_bars(rows)
            upserted += n
            yahoo_kept_total += yahoo_n
            cse_copied += cse_n
            ok += 1
            log.info(
                "hybrid_symbol_ok",
                symbol=symbol,
                yahoo_ticker=yahoo_ticker,
                cse=cse_n,
                yahoo_fetched=len(yahoo_rows),
                yahoo_kept=yahoo_n,
                upserted=n,
            )
        except Exception as exc:
            failed += 1
            log.warning(
                "hybrid_symbol_failed",
                symbol=symbol,
                yahoo_ticker=yahoo_ticker,
                error=str(exc)[:200],
            )
        if pause > 0:
            await asyncio.sleep(pause)

    result = HybridBackfillResult(
        symbols_targeted=len(symbols),
        symbols_ok=ok,
        symbols_skipped=skipped,
        symbols_failed=failed,
        bars_upserted=upserted,
        yahoo_bars_kept=yahoo_kept_total,
        cse_bars_copied=cse_copied,
    )
    log.info("hybrid_backfill_done", **asdict(result))
    return result
