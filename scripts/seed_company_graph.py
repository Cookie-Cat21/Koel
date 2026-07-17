#!/usr/bin/env python3
"""Seed annual financial disclosures + drain company/people graph.

Defaults to the top market-cap listed issuers so the people map is dense.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from chime.adapters.cse import CSEClient
from chime.domain import Disclosure
from chime.drain import drain_graph, drain_people
from chime.financials_backfill import _title_for
from chime.graph import GraphSettings
from chime.graph.directors_sync import run_directors_sync
from chime.config import Settings
from chime.storage import Storage

# Fallback if DB has no market-cap snapshots yet
_DEFAULT_SYMBOLS = [
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
    "DIAL.N0000",
    "COMB.N0000",
    "HNB.N0000",
    "SAMP.N0000",
    "SLTL.N0000",
    "LOFC.N0000",
    "NDB.N0000",
    "DFCC.N0000",
    "SEYB.N0000",
    "PABC.N0000",
    "CINS.N0000",
    "TJLH.N0000",
    "AHPL.N0000",
    "AHUN.N0000",
    "SPEN.N0000",
    "RICH.N0000",
    "DIPD.N0000",
    "EXPO.N0000",
    "TKYO.N0000",
    "GRAN.N0000",
    "RCL.N0000",
    "TILE.N0000",
    "LLUB.N0000",
    "BIL.N0000",
    "ASIR.N0000",
    "SOFT.N0000",
    "CCS.N0000",
    "KFP.N0000",
    "UAL.N0000",
    "NTB.N0000",
    "KHL.N0000",
    "TSML.N0000",
    "VONE.N0000",
    "SUN.N0000",
    "AAF.N0000",
    "CFIN.N0000",
    "PLC.N0000",
    "BRWN.N0000",
    "BFL.N0000",
    "LAL.N0000",
    "LWL.N0000",
    "CONN.N0000",
    "HEXP.N0000",
    "KVAL.N0000",
    "HOPL.N0000",
    "TPL.N0000",
    "ALUM.N0000",
    "SERV.N0000",
]


async def _top_symbols(storage: Storage, *, limit: int = 60) -> list[str]:
    out = await storage.list_top_symbols_by_market_cap(limit=limit)
    return out or _DEFAULT_SYMBOLS[:limit]


async def main() -> None:
    os.environ.setdefault("COMPANY_GRAPH_ENABLED", "1")
    os.environ.setdefault("COMPANY_GRAPH_KEEP_LOW", "0")
    os.environ.setdefault("COMPANY_PEOPLE_ENABLED", "1")
    db = os.environ.get("DATABASE_URL")
    if not db:
        raise SystemExit("DATABASE_URL is required")
    limit = int(os.environ.get("SEED_SYMBOL_LIMIT", "60"))
    storage = Storage(db)
    await storage.open()
    cse = CSEClient(min_interval_seconds=0.25)
    upserted = 0
    try:
        symbols = await _top_symbols(storage, limit=limit)
        print(f"seeding {len(symbols)} symbols")
        seen_at = datetime.now(UTC)
        for symbol in symbols:
            try:
                docs = await cse.fetch_company_financial_docs(symbol)
            except Exception as exc:  # noqa: BLE001
                print(f"list fail {symbol}: {exc}")
                continue
            annual = [d for d in docs if d[0] == "annual" and d[2]]
            for kind, filing_date, pdf_url in annual[-2:]:
                disc = Disclosure(
                    external_id=(
                        f"financials:{kind}:{filing_date.isoformat()}:{symbol}"
                    )[:200],
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

        # Official CSE boards first (source of truth for people map).
        settings = Settings.from_env(require_token=False)
        d = await run_directors_sync(
            settings=settings,
            storage=storage,
            cse=cse,
            symbols=symbols,
            force=True,
            sleep_seconds=0.25,
        )
        print(
            "directors-backfill: "
            f"targeted={d.symbols_targeted} updated={d.symbols_updated} "
            f"skipped={d.symbols_skipped} failed={d.symbols_failed} "
            f"seats={d.seats_written} roles={d.roles_written}"
        )

        cfg = GraphSettings.from_env()
        g = await drain_graph(
            storage=storage,
            settings=cfg,
            limit=max(80, len(symbols) * 2),
            watched_only=False,
            symbols=symbols,
        )
        print(
            f"drain-graph: examined={g.examined} updated={g.updated} "
            f"skipped={g.skipped} errors={g.errors}"
        )
        # Optional PDF supplement (noisy); CSE sync already replaced roles.
        if os.environ.get("SEED_PDF_PEOPLE", "0").strip() == "1":
            p = await drain_people(
                storage=storage,
                settings=cfg,
                limit=max(80, len(symbols) * 2),
                watched_only=False,
                symbols=symbols,
            )
            print(
                f"drain-people: examined={p.examined} updated={p.updated} "
                f"skipped={p.skipped} errors={p.errors} "
                f"disclosures_upserted~={upserted}"
            )
        else:
            print(
                f"drain-people: skipped (use SEED_PDF_PEOPLE=1); "
                f"disclosures_upserted~={upserted}"
            )
    finally:
        await cse.aclose()
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
