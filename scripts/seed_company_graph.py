#!/usr/bin/env python3
"""Seed annual financial disclosures + drain company graph for demo holdings."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from chime.adapters.cse import CSEClient
from chime.domain import Disclosure
from chime.drain import drain_graph
from chime.financials_backfill import _title_for
from chime.graph import GraphSettings
from chime.storage import Storage

SYMBOLS = [
    "JKH.N0000",
    "HAYL.N0000",
    "LOLC.N0000",
    "CARS.N0000",
    "MELS.N0000",
    "ACL.N0000",
    "APLA.N0000",
    "CTHR.N0000",
    "CARG.N0000",
    "DIST.N0000",
    "LION.N0000",
    "CTC.N0000",
]


async def main() -> None:
    os.environ.setdefault("COMPANY_GRAPH_ENABLED", "1")
    os.environ.setdefault("COMPANY_GRAPH_KEEP_LOW", "1")
    db = os.environ.get("DATABASE_URL")
    if not db:
        raise SystemExit("DATABASE_URL is required")
    storage = Storage(db)
    await storage.open()
    cse = CSEClient(min_interval_seconds=0.3)
    upserted = 0
    try:
        seen_at = datetime.now(UTC)
        for symbol in SYMBOLS:
            try:
                docs = await cse.fetch_company_financial_docs(symbol)
            except Exception as exc:  # noqa: BLE001
                print(f"list fail {symbol}: {exc}")
                continue
            annual = [d for d in docs if d[0] == "annual" and d[2]]
            # latest 2 annuals
            for kind, filing_date, pdf_url in annual[-2:]:
                disc = Disclosure(
                    external_id=f"financials:{kind}:{filing_date.isoformat()}:{symbol}"[
                        :200
                    ],
                    symbol=symbol,
                    title=_title_for(kind, filing_date),
                    category=(
                        "FINANCIAL STATEMENTS - ANNUAL"
                        if kind == "annual"
                        else "FINANCIAL STATEMENTS - QUARTERLY"
                    ),
                    url=pdf_url,
                    company_name=None,
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
                try:
                    await storage.upsert_disclosure(disc)
                    upserted += 1
                except Exception as exc2:  # noqa: BLE001
                    print(f"upsert fail {symbol}: {exc2}")
            print(f"seeded docs for {symbol}")

        result = await drain_graph(
            storage=storage,
            settings=GraphSettings.from_env(),
            limit=40,
            watched_only=False,
            symbols=SYMBOLS,
        )
        print(
            f"drain-graph: examined={result.examined} updated={result.updated} "
            f"skipped={result.skipped} errors={result.errors} disclosures_upserted~={upserted}"
        )
    finally:
        await cse.aclose()
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
