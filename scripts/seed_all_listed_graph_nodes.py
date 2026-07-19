#!/usr/bin/env python3
"""Upsert every ``stocks`` row as a listed ``company_graph_nodes`` issuer.

The ownership map can then show the full CSE board (isolates included),
even before PDF drains attach links.
"""

from __future__ import annotations

import asyncio
import os

from chime.adapters.cse import normalize_company_name
from chime.storage import Storage


async def main() -> None:
    db = os.environ.get("DATABASE_URL")
    if not db:
        raise SystemExit("DATABASE_URL is required")
    storage = Storage(db)
    await storage.open()
    try:
        async with storage._pool.connection() as conn:  # noqa: SLF001
            # Ordinary voting shares only — skip indexes (ASPI/MARKET) and
            # preference lines (.X0000) that share a PLC name_norm with .N0000.
            cur = await conn.execute(
                """
                SELECT symbol, name
                FROM stocks
                WHERE symbol LIKE '%.N0000'
                  AND symbol <> 'MARKET'
                ORDER BY symbol
                """
            )
            rows = await cur.fetchall()
        upserted = 0
        for row in rows:
            mapping = dict(row) if not isinstance(row, dict) else row
            symbol = str(mapping["symbol"]).strip().upper()
            raw_name = mapping.get("name")
            name = (
                raw_name.strip()
                if isinstance(raw_name, str) and raw_name.strip()
                else symbol
            )
            name_norm = normalize_company_name(name) or symbol
            await storage.upsert_company_graph_node(
                {
                    "symbol": symbol,
                    "display_name": name[:200],
                    "name_norm": name_norm[:200],
                    "node_kind": "listed",
                    "update_equity": False,
                }
            )
            upserted += 1
        print(f"seed_all_listed_graph_nodes: upserted={upserted}")
    finally:
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
