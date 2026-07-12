import type { NextRequest } from "next/server";

import {
  MAX_HISTORY_SYMBOL_LENGTH,
  MAX_STOCK_NAME_LENGTH,
  MAX_STOCK_SECTOR_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/market-browse";
import { normalizeSymbolParam } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ symbol: string }> };

/**
 * GET /api/v1/symbols/{symbol} — stock row + slim last snapshot.
 * Postgres only; no cse.lk.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const { symbol: raw } = await context.params;
  // safeDecode — malformed % sequences must 400, not URIError 500.
  const symbol = normalizeSymbolParam(raw);
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid symbol.");
  }

  try {
    const pool = getPool();
    const stock = await pool.query<{
      symbol: string;
      name: string | null;
      sector: string | null;
    }>(`SELECT symbol, name, sector FROM stocks WHERE symbol = $1`, [symbol]);

    if (stock.rows.length === 0) {
      return jsonError(404, "not_found", "Unknown symbol.");
    }

    const row = stock.rows[0];
    const snap = await pool.query<{
      price: number;
      change: number | null;
      change_pct: number | null;
      volume: number | null;
      ts: Date | string;
    }>(
      `SELECT price, change, change_pct, volume, ts
       FROM price_snapshots
       WHERE symbol = $1
       ORDER BY ts DESC
       LIMIT 1`,
      [symbol],
    );

    const last =
      snap.rows.length === 0
        ? null
        : {
            // Finite-only egress (parity with movers/browse) — NaN/±Inf → null.
            price: toFiniteNumber(snap.rows[0].price),
            change: toFiniteNumber(snap.rows[0].change),
            change_pct: toFiniteNumber(snap.rows[0].change_pct),
            volume: toFiniteNumber(snap.rows[0].volume),
            ts: toIso(snap.rows[0].ts),
          };

    return jsonOk({
      symbol:
        sanitizeDisclosureText(row.symbol, MAX_HISTORY_SYMBOL_LENGTH) ?? symbol,
      name: sanitizeDisclosureText(row.name, MAX_STOCK_NAME_LENGTH),
      sector: sanitizeDisclosureText(row.sector, MAX_STOCK_SECTOR_LENGTH),
      last,
    });
  } catch (err) {
    console.error("GET /symbols/:symbol failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
