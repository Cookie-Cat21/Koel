#!/usr/bin/env python3
"""Drain one annual financial PDF per listed issuer into the ownership graph.

Picks the newest pending annual/audited disclosure per symbol (not yet in
``filing_graph_extracts``), then runs ``process_disclosure_graph``.

Env:
  DATABASE_URL (required)
  COMPANY_GRAPH_ENABLED=1
  DRAIN_SYMBOL_LIMIT — cap symbols (default: all pending)
  DRAIN_SLEEP_SECONDS — pause between PDFs (default 0.35)
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime

from koel.domain import Disclosure
from koel.graph import GraphSettings
from koel.graph.worker import process_disclosure_graph
from koel.storage import Storage


def _as_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return None


async def _pending_annual_by_symbol(storage: Storage) -> list[Disclosure]:
    """Newest pending annual-ish PDF per symbol."""
    async with storage._pool.connection() as conn:  # noqa: SLF001
        cur = await conn.execute(
            """
            SELECT DISTINCT ON (d.symbol)
                   d.id, d.external_id, d.symbol, d.title, d.category, d.url,
                   d.company_name, d.published_at, d.seen_at, d.pdf_url
            FROM disclosures d
            LEFT JOIN filing_graph_extracts g ON g.disclosure_id = d.id
            WHERE d.pdf_url IS NOT NULL
              AND btrim(d.pdf_url) <> ''
              AND d.symbol IS NOT NULL
              AND d.symbol LIKE '%.N0000'
              AND g.id IS NULL
              -- True annual only — '%financial statement%' used to match interims
              -- and burn the drain on not_annual skips.
              AND (
                d.external_id LIKE 'financials:annual:%'
                OR d.title ILIKE '%annual report%'
                OR (
                  d.category ILIKE '%annual%'
                  AND d.title ILIKE '%annual%'
                )
              )
              AND d.title NOT ILIKE '%interim%'
              AND d.title NOT ILIKE '%quarterly%'
              AND d.title NOT ILIKE '%three months%'
              AND d.external_id NOT LIKE 'financials:quarterly:%'
              AND d.external_id NOT LIKE 'financials:other:%'
            ORDER BY d.symbol, d.published_at DESC NULLS LAST, d.id DESC
            """
        )
        rows = await cur.fetchall()
    out: list[Disclosure] = []
    for row in rows:
        m = dict(row) if not isinstance(row, dict) else row
        ext = m.get("external_id")
        sym = m.get("symbol")
        if not isinstance(ext, str) or not isinstance(sym, str):
            continue
        pdf = m.get("pdf_url") if isinstance(m.get("pdf_url"), str) else None
        url = m.get("url") if isinstance(m.get("url"), str) and m.get("url") else pdf
        if not url:
            continue
        published = _as_dt(m.get("published_at"))
        seen = _as_dt(m.get("seen_at"))
        if published is None or seen is None:
            continue
        disc = Disclosure(
            external_id=ext,
            symbol=sym.strip().upper(),
            company_name=m.get("company_name")
            if isinstance(m.get("company_name"), str)
            else None,
            title=m.get("title") if isinstance(m.get("title"), str) else "",
            category=m.get("category")
            if isinstance(m.get("category"), str)
            else None,
            url=url,
            published_at=published,
            seen_at=seen,
            pdf_url=pdf,
            id=int(m["id"]) if m.get("id") is not None else None,
        )
        out.append(disc)
    return out


async def main() -> None:
    os.environ.setdefault("COMPANY_GRAPH_ENABLED", "1")
    db = os.environ.get("DATABASE_URL")
    if not db:
        raise SystemExit("DATABASE_URL is required")
    sleep_s = float(os.environ.get("DRAIN_SLEEP_SECONDS", "0.35"))
    limit_raw = os.environ.get("DRAIN_SYMBOL_LIMIT", "").strip()
    limit = int(limit_raw) if limit_raw.isdigit() else None

    storage = Storage(db)
    await storage.open()
    cfg = GraphSettings.from_env()
    try:
        pending = await _pending_annual_by_symbol(storage)
        if limit is not None and limit > 0:
            pending = pending[:limit]
        print(f"drain_graph_all_listed: symbols={len(pending)}")
        updated = skipped = errors = 0
        t0 = time.monotonic()
        for i, disc in enumerate(pending, start=1):
            try:
                result = await process_disclosure_graph(
                    storage=storage,
                    disclosure=disc,
                    settings=cfg,
                )
                if result is None or result.extract_id is None:
                    skipped += 1
                    status = "skip"
                else:
                    updated += 1
                    status = (
                        f"ok edges={result.edges_written} "
                        f"equity={result.equity_ok} relations={result.extract_ok}"
                    )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                status = f"err {str(exc)[:120]}"
            print(f"[{i}/{len(pending)}] {disc.symbol}: {status}")
            if sleep_s > 0 and i < len(pending):
                await asyncio.sleep(sleep_s)
        elapsed = time.monotonic() - t0
        print(
            "drain_graph_all_listed: "
            f"updated={updated} skipped={skipped} errors={errors} "
            f"elapsed_s={elapsed:.1f}"
        )
    finally:
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
