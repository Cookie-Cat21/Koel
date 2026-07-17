"""Backfill forecast_outcomes from purged walk-forward (historical ground truth)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from chime.logging_setup import get_logger
from chime.ml.always_on import (
    enrich_samples_with_financial_filings,
    enrich_samples_with_sector_rs,
    enrich_samples_with_yoy,
    load_yoy_events,
)
from chime.ml.dataset import build_samples, load_symbol_bars
from chime.ml.diagnose import PredRow, load_sector_map
from chime.ml.harden import _demean_by_day, _purge_train
from chime.ml.iterate import _enrich_cross_section, _predict_lmt_bagged, _rows_from_scores
from chime.ml.outcomes import _add_trading_days, market_calendar
from chime.ml.regime import tag_regime
from chime.ml.walkforward import _unique_sorted_dates
from chime.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BackfillResult:
    rows: int
    folds: int


def _aspi_ret_map(closes: list[tuple[date, float]]) -> dict[date, float | None]:
    """Map trade_date -> trailing 20d ASPI return (in-memory)."""
    out: dict[date, float | None] = {}
    prices: list[float] = []
    for d, p in closes:
        prices.append(p)
        if len(prices) < 21:
            out[d] = None
            continue
        a, b = prices[-21], prices[-1]
        out[d] = None if a == 0 else (b / a) - 1.0
    return out


async def backfill_walkforward_outcomes(
    storage: Storage,
    *,
    model_version: str = "wf_fin_sector_h1",
    horizon: int = 1,
) -> BackfillResult:
    """Run purged WF and write already-realized outcomes (scored=true)."""
    series = await load_symbol_bars(storage)
    base = _enrich_cross_section(
        _demean_by_day(build_samples(series, horizon=horizon, min_history=60))
    )
    sectors = await load_sector_map(storage)
    samples = enrich_samples_with_sector_rs(base, sectors)
    cache = Path("data/financial_filings_cache.json")
    if cache.is_file():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        filings = [(str(a), date.fromisoformat(str(b)), str(c)) for a, b, c in raw]
        samples = enrich_samples_with_financial_filings(samples, filings)
    yoy = await load_yoy_events(storage)
    if yoy:
        samples = enrich_samples_with_yoy(samples, yoy)

    dates = _unique_sorted_dates(samples)
    min_train_days, fold_step, embargo = 100, 10, 2
    cut = min_train_days
    fold = 0
    all_rows: list[PredRow] = []
    while cut + fold_step <= len(dates):
        test_dates = set(dates[cut : cut + fold_step])
        train = _purge_train(
            samples, dates=dates, cut=cut, horizon=horizon, embargo=embargo
        )
        test = [s for s in samples if s.as_of in test_dates]
        cut += fold_step
        if len(train) < 50 or len(test) < 10:
            continue
        try:
            scores = _predict_lmt_bagged(train, test)
        except Exception as exc:
            log.warning("wf_backfill_fold_failed", fold=fold, error=str(exc))
            continue
        all_rows.extend(_rows_from_scores(test, scores, fold=fold, sectors=sectors))
        fold += 1
        log.info("wf_backfill_fold", fold=fold, rows=len(all_rows))

    # Regime tags from ASPI bars (one fetch)
    aspi_bars = await storage.list_daily_bars("ASPI")
    aspi_closes = [
        (b.trade_date, b.price)
        for b in aspi_bars
        if math.isfinite(b.price)
    ]
    aspi_closes.sort(key=lambda x: x[0])
    aspi_rets = _aspi_ret_map(aspi_closes)
    cal = await market_calendar(storage)

    batch: list[tuple] = []
    for r in all_rows:
        aspi_r = aspi_rets.get(r.as_of)
        tag = tag_regime(as_of=r.as_of, aspi_ret_20d=aspi_r).tag
        realized = _add_trading_days(r.as_of, horizon, cal)
        conf = min(1.0, abs(float(r.score)) * 2.0)
        batch.append(
            (
                model_version,
                model_version,
                r.symbol,
                r.as_of,
                horizon,
                float(r.score),
                conf,
                "wf_shadow",
                realized,
                float(r.y_ret),
                bool(r.hit),
                tag,
                True,
            )
        )

    if not batch:
        return BackfillResult(rows=0, folds=fold)

    # Chunked upsert — already scored
    chunk = 2000
    async with storage._pool.connection() as conn, conn.cursor() as cur:
        for i in range(0, len(batch), chunk):
            part = batch[i : i + chunk]
            await cur.executemany(
                """
                    INSERT INTO forecast_outcomes (
                        model_id, model_version, symbol, issued_at, horizon_days,
                        y_pred, confidence, gate, realized_at,
                        y_real, hit, regime_tag, scored, scored_at
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now()
                    )
                    ON CONFLICT (model_version, symbol, issued_at, horizon_days)
                    DO UPDATE SET
                        y_pred = EXCLUDED.y_pred,
                        confidence = EXCLUDED.confidence,
                        gate = EXCLUDED.gate,
                        realized_at = COALESCE(
                            EXCLUDED.realized_at, forecast_outcomes.realized_at
                        ),
                        y_real = EXCLUDED.y_real,
                        hit = EXCLUDED.hit,
                        regime_tag = EXCLUDED.regime_tag,
                        scored = TRUE,
                        scored_at = now()
                    """,
                part,
            )
            log.info(
                "wf_outcomes_chunk",
                written=min(i + chunk, len(batch)),
                total=len(batch),
            )

    log.info("wf_outcomes_backfilled", rows=len(batch), folds=fold)
    return BackfillResult(rows=len(batch), folds=fold)
