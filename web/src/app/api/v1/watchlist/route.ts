import type { NextRequest } from "next/server";

import {
  MAX_STOCK_NAME_LENGTH,
  MAX_STOCK_SECTOR_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/market-browse";
import { readJsonBody } from "@/lib/api/read-json-body";
import { toIso } from "@/lib/api/time";
import { normalizeSymbol } from "@/lib/api/symbol";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession, requireSessionAndCsrf } from "@/lib/auth/guard";
import { addWatch, getPool, getStock } from "@/lib/db";

export const runtime = "nodejs";

/** Cap watchlist list — unbounded SELECT used to OOM SSR / balloon JSON. */
export const MAX_WATCHLIST_ITEMS = 500;

/**
 * GET /api/v1/watchlist — session user's symbols + latest price_snapshots join.
 * Postgres only; no cse.lk.
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  try {
    const pool = getPool();
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
         w.symbol,
         s.name,
         s.sector,
         ps.price,
         ps.change,
         ps.change_pct,
         ps.ts
       FROM watchlist_items w
       JOIN stocks s ON s.symbol = w.symbol
       LEFT JOIN LATERAL (
         SELECT price, change, change_pct, ts
         FROM price_snapshots
         WHERE symbol = w.symbol
         ORDER BY ts DESC
         LIMIT 1
       ) ps ON TRUE
       WHERE w.user_id = $1
       ORDER BY w.symbol ASC
       LIMIT $2`,
      [gated.session.user_id, MAX_WATCHLIST_ITEMS],
    );

    const items = result.rows.flatMap((row) => {
      // Fail closed — only CSE SYMBOL_RE rows (not sanitize-only junk).
      const symbol = normalizeSymbol(row.symbol);
      if (!symbol) return [];
      return [
        {
          symbol,
          // Strip C0/C1 + cap — hostile stock name/sector must not balloon JSON.
          name: sanitizeDisclosureText(row.name, MAX_STOCK_NAME_LENGTH),
          sector: sanitizeDisclosureText(row.sector, MAX_STOCK_SECTOR_LENGTH),
          // Finite-only egress (parity with movers/browse) — NaN/±Inf → null.
          price: toFiniteNumber(row.price),
          change: toFiniteNumber(row.change),
          change_pct: toFiniteNumber(row.change_pct),
          ts: toIso(row.ts),
        },
      ];
    });

    return jsonOk({ items });
  } catch (err) {
    console.error("GET /watchlist failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}

/**
 * POST /api/v1/watchlist — add symbol (CSRF). Postgres stocks only; no cse.lk.
 * Soft messaging: 200 with created:false when already watched (parity DELETE removed).
 */
export async function POST(request: NextRequest) {
  const gated = await requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  const parsed = await readJsonBody(request);
  if (!parsed.ok) {
    if (parsed.reason === "too_large") {
      return jsonError(400, "validation_error", "Request body too large.");
    }
    return jsonError(400, "validation_error", "Invalid JSON body.");
  }
  const body = parsed.value;

  const rawSymbol =
    typeof body === "object" && body !== null && "symbol" in body
      ? (body as { symbol: unknown }).symbol
      : undefined;
  const symbol = normalizeSymbol(rawSymbol);
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid CSE symbol.");
  }

  try {
    const stock = await getStock(symbol);
    if (!stock) {
      return jsonError(
        404,
        "not_found",
        "Unknown symbol. The dashboard only accepts symbols already seeded in Postgres; wait for a poller tick or seed it from Telegram with /watch SYMBOL.",
      );
    }

    const created = await addWatch(gated.session.user_id, symbol);
    return jsonOk(
      {
        symbol,
        name: sanitizeDisclosureText(stock.name, MAX_STOCK_NAME_LENGTH),
        created,
      },
      created ? 201 : 200,
    );
  } catch (err) {
    console.error("POST /watchlist failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
