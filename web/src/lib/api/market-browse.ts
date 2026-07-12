/**
 * Shared Postgres browse for GET /api/v1/symbols and /api/v1/market/movers.
 * Latest price_snapshots via INNER JOIN — thin discovery, not a screener.
 */

import type { Pool } from "pg";

import { escapeLikePattern } from "@/lib/api/market-query";
import { toIso } from "@/lib/api/time";

export type MarketBrowseSort = "change_pct" | "change_pct_asc" | "symbol";

export type MarketBrowseRow = {
  symbol: string;
  name: string | null;
  sector: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  ts: string | null;
};

export type MarketBrowseQuery = {
  limit: number;
  offset: number;
  /** Already normalized (or empty). */
  q?: string;
  sort: MarketBrowseSort;
};

function orderClause(sort: MarketBrowseSort): string {
  if (sort === "symbol") return "s.symbol ASC";
  if (sort === "change_pct_asc") {
    return "ps.change_pct ASC NULLS LAST, s.symbol ASC";
  }
  return "ps.change_pct DESC NULLS LAST, s.symbol ASC";
}

/**
 * Latest snapshot per stock (INNER JOIN). Optional `q` substring on symbol/name.
 */
export async function queryMarketBrowse(
  pool: Pool,
  opts: MarketBrowseQuery,
): Promise<MarketBrowseRow[]> {
  const params: unknown[] = [];
  let where = "";
  const q = opts.q?.trim() ?? "";
  if (q) {
    params.push(`%${escapeLikePattern(q.toUpperCase())}%`);
    where = `WHERE UPPER(s.symbol) LIKE $1 ESCAPE '\\' OR UPPER(COALESCE(s.name, '')) LIKE $1 ESCAPE '\\'`;
  }

  params.push(opts.limit);
  const limitIdx = params.length;
  params.push(opts.offset);
  const offsetIdx = params.length;

  const result = await pool.query<{
    symbol: string;
    name: string | null;
    sector: string | null;
    price: number | null;
    change: number | null;
    change_pct: number | null;
    ts: Date | string | null;
  }>(
    `SELECT
       s.symbol,
       s.name,
       s.sector,
       ps.price,
       ps.change,
       ps.change_pct,
       ps.ts
     FROM stocks s
     INNER JOIN LATERAL (
       SELECT price, change, change_pct, ts
       FROM price_snapshots
       WHERE symbol = s.symbol
       ORDER BY ts DESC, id DESC
       LIMIT 1
     ) ps ON TRUE
     ${where}
     ORDER BY ${orderClause(opts.sort)}
     LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
    params,
  );

  return result.rows.map((row) => ({
    symbol: row.symbol,
    name: row.name,
    sector: row.sector,
    price: row.price == null ? null : Number(row.price),
    change: row.change == null ? null : Number(row.change),
    change_pct: row.change_pct == null ? null : Number(row.change_pct),
    ts: toIso(row.ts),
  }));
}
