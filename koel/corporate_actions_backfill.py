"""Backfill ``corporate_actions`` from disclosures + daily_bars price cliffs.

Run: ``python3 -m koel corporate-actions-backfill [--force] [--limit N]``
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from koel.corporate_actions import detect_splits_from_closes, is_split_disclosure
from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)


@dataclass
class CorporateActionsBackfillResult:
    disclosures_scanned: int = 0
    disclosures_upserted: int = 0
    symbols_scanned: int = 0
    price_hits: int = 0
    price_upserted: int = 0
    errors: int = 0


def _as_mapping(row: object) -> dict:
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}  # type: ignore[index]
    # Fallback positional (id, symbol, title, category, published_at) etc.
    return {}


def _trade_date(raw: object) -> date | None:
    if isinstance(raw, date) and not hasattr(raw, "hour"):
        return raw
    if hasattr(raw, "date") and callable(raw.date):
        try:
            d = raw.date()
            if isinstance(d, date):
                return d
        except Exception:
            return None
    if isinstance(raw, str) and len(raw) >= 10:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return None


async def run_corporate_actions_backfill(
    *,
    storage: Storage,
    limit: int | None = None,
    force: bool = False,
) -> CorporateActionsBackfillResult:
    """Scan stored disclosures + daily bars for split/consolidation events.

    ``force`` is accepted for CLI parity; detection is idempotent via unique keys.
    """
    del force  # idempotent upserts
    result = CorporateActionsBackfillResult()

    # --- disclosure text path ---
    async with storage._pool.connection() as conn:
        if limit is not None and limit > 0:
            rows = await (
                await conn.execute(
                    """
                    SELECT id, symbol, title, category, published_at
                    FROM disclosures
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (int(limit),),
                )
            ).fetchall()
        else:
            rows = await (
                await conn.execute(
                    """
                    SELECT id, symbol, title, category, published_at
                    FROM disclosures
                    ORDER BY id DESC
                    """
                )
            ).fetchall()

    for row in rows:
        result.disclosures_scanned += 1
        data = _as_mapping(row)
        if not data:
            continue
        title = data.get("title") if isinstance(data.get("title"), str) else None
        category = (
            data.get("category") if isinstance(data.get("category"), str) else None
        )
        if not is_split_disclosure(category, title):
            continue
        try:
            stored = await storage.upsert_corporate_action_from_disclosure(
                symbol=str(data["symbol"]),
                disclosure_id=int(data["id"]) if data.get("id") is not None else None,
                title=title,
                category=category,
                published_at=data.get("published_at"),
            )
            if stored is not None:
                result.disclosures_upserted += 1
        except Exception as exc:
            result.errors += 1
            log.warning(
                "corporate_actions_disclosure_backfill_failed",
                error=str(exc),
            )

    # --- daily_bars price-ratio path ---
    async with storage._pool.connection() as conn:
        sym_rows = await (
            await conn.execute(
                """
                SELECT DISTINCT symbol
                FROM daily_bars
                ORDER BY symbol
                """
            )
        ).fetchall()
    symbols = []
    for r in sym_rows:
        m = _as_mapping(r)
        if m and m.get("symbol"):
            symbols.append(str(m["symbol"]))
        elif not m and len(r) > 0:  # type: ignore[arg-type]
            symbols.append(str(r[0]))  # type: ignore[index]
    if limit is not None and limit > 0:
        symbols = symbols[: int(limit)]

    for symbol in symbols:
        result.symbols_scanned += 1
        try:
            async with storage._pool.connection() as conn:
                bar_rows = await (
                    await conn.execute(
                        """
                        SELECT trade_date, price
                        FROM daily_bars
                        WHERE symbol = %s
                        ORDER BY trade_date ASC
                        """,
                        (symbol,),
                    )
                ).fetchall()
            points: list[tuple[date, float]] = []
            for br in bar_rows:
                m = _as_mapping(br)
                if m:
                    td, px = m.get("trade_date"), m.get("price")
                else:
                    td, px = br[0], br[1]  # type: ignore[index]
                d = _trade_date(td)
                try:
                    px_f = float(px)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                if d is None or px_f <= 0:
                    continue
                points.append((d, px_f))

            for effective, hit in detect_splits_from_closes(points):
                result.price_hits += 1
                # Reconstruct prices that re-detect to the same N.
                if hit.kind == "split":
                    curr, prev = 100.0, 100.0 * float(hit.n)
                else:
                    prev, curr = 100.0, 100.0 * float(hit.n)
                stored = await storage.upsert_corporate_action_from_price(
                    symbol=symbol,
                    prev_price=prev,
                    curr_price=curr,
                    as_of=effective,
                )
                if stored is not None:
                    result.price_upserted += 1
        except Exception as exc:
            result.errors += 1
            log.warning(
                "corporate_actions_price_backfill_failed",
                symbol=symbol,
                error=str(exc),
            )

    log.info(
        "corporate_actions_backfill_done",
        disclosures_scanned=result.disclosures_scanned,
        disclosures_upserted=result.disclosures_upserted,
        symbols_scanned=result.symbols_scanned,
        price_hits=result.price_hits,
        price_upserted=result.price_upserted,
        errors=result.errors,
    )
    return result
