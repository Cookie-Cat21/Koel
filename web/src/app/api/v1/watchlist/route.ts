import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { normalizeSymbol } from "@/lib/api/symbol";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession, requireSessionAndCsrf } from "@/lib/auth/guard";
import { addWatch, getPool, getStock } from "@/lib/db";

export const runtime = "nodejs";

/**
 * GET /api/v1/watchlist — session user's symbols + latest price_snapshots join.
 * Postgres only; no cse.lk.
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
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
       ORDER BY w.symbol ASC`,
      [gated.session.user_id],
    );

    const items = result.rows.map((row) => ({
      symbol: row.symbol,
      name: row.name,
      sector: row.sector,
      price: row.price == null ? null : Number(row.price),
      change: row.change == null ? null : Number(row.change),
      change_pct: row.change_pct == null ? null : Number(row.change_pct),
      ts: toIso(row.ts),
    }));

    return jsonOk({ items });
  } catch (err) {
    console.error("GET /watchlist failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}

/**
 * POST /api/v1/watchlist — add symbol (CSRF). Postgres stocks only; no cse.lk.
 */
export async function POST(request: NextRequest) {
  const gated = requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonError(400, "validation_error", "Invalid JSON body.");
  }

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
      return jsonError(404, "not_found", "Unknown symbol.");
    }

    const inserted = await addWatch(gated.session.user_id, symbol);
    return jsonOk(
      { symbol: stock.symbol, name: stock.name },
      inserted ? 201 : 200,
    );
  } catch (err) {
    console.error("POST /watchlist failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
