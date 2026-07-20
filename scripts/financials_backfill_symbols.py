#!/usr/bin/env python3
"""Backfill POST /financials PDFs for an explicit symbol list (or all .N0000).

Unlike ``koel financials-backfill``, this does not require daily_bars rows,
so thin/illiquid issuers still get annual PDFs for the ownership drain.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, date, datetime, timedelta

from koel.adapters.cse import CSEClient
from koel.config import Settings
from koel.domain import Disclosure
from koel.financials_backfill import _title_for
from koel.storage import Storage


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbols (default: all stocks LIKE %.N0000)",
    )
    parser.add_argument("--sleep", type=float, default=0.25)
    args = parser.parse_args()

    db = os.environ.get("DATABASE_URL")
    if not db:
        raise SystemExit("DATABASE_URL is required")

    settings = Settings.from_env(require_token=False)
    storage = Storage(db)
    await storage.open()
    cse = CSEClient(
        base_url=settings.cse_base_url,
        timeout=settings.http_timeout_seconds,
        fail_max=settings.circuit_fail_max,
        reset_timeout=settings.circuit_reset_seconds,
        min_interval_seconds=settings.cse_min_interval_seconds,
    )
    try:
        if args.symbols.strip():
            symbols = [
                s.strip().upper()
                for s in args.symbols.split(",")
                if s.strip()
            ]
        else:
            async with storage._pool.connection() as conn:  # noqa: SLF001
                cur = await conn.execute(
                    """
                    SELECT symbol FROM stocks
                    WHERE symbol LIKE '%.N0000'
                    ORDER BY symbol
                    """
                )
                rows = await cur.fetchall()
            symbols = [str(dict(r)["symbol"]).upper() for r in rows]

        cutoff = date.today() - timedelta(days=800)
        seen_at = datetime.now(UTC)
        ok = failed = upserted = 0
        for i, symbol in enumerate(symbols):
            try:
                docs = await cse.fetch_company_financial_docs(symbol)
                for kind, filing_date, pdf_url in docs:
                    if kind not in {"quarterly", "annual"}:
                        continue
                    if filing_date < cutoff:
                        continue
                    if not pdf_url:
                        continue
                    ext = f"financials:{kind}:{filing_date.isoformat()}:{symbol}"
                    disc = Disclosure(
                        external_id=ext[:200],
                        symbol=symbol,
                        company_name=None,
                        title=_title_for(kind, filing_date),
                        category=(
                            "FINANCIAL STATEMENTS - QUARTERLY"
                            if kind == "quarterly"
                            else "FINANCIAL STATEMENTS - ANNUAL"
                        ),
                        url=pdf_url,
                        published_at=datetime(
                            filing_date.year,
                            filing_date.month,
                            filing_date.day,
                            12,
                            0,
                            tzinfo=UTC,
                        ),
                        seen_at=seen_at,
                        pdf_url=pdf_url,
                    )
                    await storage.upsert_disclosure(disc)
                    upserted += 1
                ok += 1
                print(f"ok {symbol} docs={len(docs)}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"err {symbol}: {str(exc)[:160]}")
            if args.sleep > 0 and i + 1 < len(symbols):
                await asyncio.sleep(args.sleep)
        print(
            f"financials_backfill_symbols: targeted={len(symbols)} "
            f"ok={ok} failed={failed} upserted={upserted}"
        )
    finally:
        await cse.aclose()
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
