/**
 * Shared Postgres browse for GET /api/v1/symbols and /api/v1/market/movers.
 * Latest price_snapshots via INNER JOIN — thin discovery, not a screener.
 */

import type { Pool } from "pg";

import {
  MAX_STOCK_NAME_LENGTH,
  MAX_STOCK_SECTOR_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import {
  MAX_FINITE_NUMBER_STRING_LENGTH,
  toFiniteNumber,
} from "@/lib/api/finite-number";
import { escapeLikePattern } from "@/lib/api/market-query";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";

export type MarketBrowseSort = "change_pct" | "change_pct_asc" | "symbol";

/** Movers sign filter: only strictly positive (up) or negative (down) %. */
export type MarketBrowseDirection = "up" | "down";

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
  /**
   * Exact sector name match (case-insensitive) after sanitize — light P1 filter,
   * not a multi-filter screener.
   */
  sector?: string;
  /** When true, only symbols with a successful EPS extract. */
  has_eps?: boolean;
  sort: MarketBrowseSort;
  /**
   * Optional movers fence: `up` ⇒ change_pct > 0, `down` ⇒ change_pct < 0.
   * Excludes flats/nulls so "gainers"/"losers" cannot mislabel opposite moves.
   */
  direction?: MarketBrowseDirection;
};

/** Re-export — callers may import from market-browse or finite-number. */
export { MAX_FINITE_NUMBER_STRING_LENGTH, toFiniteNumber };

function orderClause(sort: MarketBrowseSort): string {
  if (sort === "symbol") return "s.symbol ASC";
  if (sort === "change_pct_asc") {
    return "ps.change_pct ASC NULLS LAST, s.symbol ASC";
  }
  return "ps.change_pct DESC NULLS LAST, s.symbol ASC";
}

type BrowseFilter = Pick<
  MarketBrowseQuery,
  "q" | "direction" | "sector" | "has_eps"
>;

/** Shared FROM + WHERE for list + count (latest snapshot INNER JOIN). */
function browseFromWhere(opts: BrowseFilter): {
  fromSql: string;
  whereSql: string;
  params: unknown[];
} {
  const params: unknown[] = [];
  const whereParts: string[] = [];
  // Fail closed — non-string q used to throw on .trim mid browse (parity
  // normalizeMarketQuery typeof / firstSearchParam guards).
  const q = typeof opts.q === "string" ? opts.q.trim() : "";
  if (q) {
    params.push(`%${escapeLikePattern(q.toUpperCase())}%`);
    whereParts.push(
      `(UPPER(s.symbol) LIKE $${params.length} ESCAPE '\\' OR UPPER(COALESCE(s.name, '')) LIKE $${params.length} ESCAPE '\\')`,
    );
  }
  const sector =
    typeof opts.sector === "string" ? opts.sector.trim() : "";
  if (sector) {
    params.push(sector.toUpperCase());
    whereParts.push(`UPPER(COALESCE(s.sector, '')) = $${params.length}`);
  }
  if (opts.has_eps === true) {
    whereParts.push(`EXISTS (
      SELECT 1 FROM filing_metrics fm
      WHERE fm.symbol = s.symbol
        AND fm.extract_ok = TRUE
        AND fm.eps_basic IS NOT NULL
    )`);
  }
  if (opts.direction === "up") {
    whereParts.push("ps.change_pct > 0");
  } else if (opts.direction === "down") {
    whereParts.push("ps.change_pct < 0");
  }

  const fromSql = `FROM stocks s
     INNER JOIN LATERAL (
       SELECT price, change, change_pct, ts
       FROM price_snapshots
       WHERE symbol = s.symbol
       ORDER BY ts DESC, id DESC
       LIMIT 1
     ) ps ON TRUE`;
  const whereSql =
    whereParts.length > 0 ? `WHERE ${whereParts.join(" AND ")}` : "";
  return { fromSql, whereSql, params };
}

/**
 * Count stocks with a latest snapshot matching the same filters as browse.
 */
export async function countMarketBrowse(
  pool: Pool,
  opts: BrowseFilter,
): Promise<number> {
  const { fromSql, whereSql, params } = browseFromWhere(opts);
  const result = await pool.query<{ n: string | number }>(
    `SELECT COUNT(*)::int AS n ${fromSql} ${whereSql}`,
    params,
  );
  const raw = result.rows[0]?.n;
  const n = typeof raw === "number" ? raw : Number.parseInt(String(raw ?? "0"), 10);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

/**
 * Latest snapshot per stock (INNER JOIN). Optional `q` substring on symbol/name.
 * Optional `direction` sign filter for thin movers (not a screener).
 */
export async function queryMarketBrowse(
  pool: Pool,
  opts: MarketBrowseQuery,
): Promise<MarketBrowseRow[]> {
  const { fromSql, whereSql, params } = browseFromWhere(opts);

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
     ${fromSql}
     ${whereSql}
     ORDER BY ${orderClause(opts.sort)}
     LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
    params,
  );

  return result.rows.flatMap((row) => {
    // Fail closed — only CSE SYMBOL_RE (not sanitize-only junk).
    const symbol = normalizeSymbol(row.symbol);
    if (!symbol) return [];
    return [
      {
        symbol,
        name: sanitizeDisclosureText(row.name, MAX_STOCK_NAME_LENGTH),
        sector: sanitizeDisclosureText(row.sector, MAX_STOCK_SECTOR_LENGTH),
        price: toFiniteNumber(row.price),
        change: toFiniteNumber(row.change),
        change_pct: toFiniteNumber(row.change_pct),
        ts: toIso(row.ts),
      },
    ];
  });
}
