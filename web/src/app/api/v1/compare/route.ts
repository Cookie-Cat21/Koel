import type { NextRequest } from "next/server";

import { toFiniteNumber } from "@/lib/api/market-browse";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/** Max companies on one compare chart (product scale lock). */
export const MAX_COMPARE_SYMBOLS = 4;
const DEFAULT_LIMIT = 60;
const MAX_LIMIT = 200;
/** Cap raw `symbols` query length before split/normalize. */
const MAX_SYMBOLS_PARAM_CHARS = 256;

/**
 * GET /api/v1/compare?symbols=A,B,C&limit=60
 * Multi-symbol price series from Postgres only (no cse.lk).
 * 1–4 unique symbols; each series ascending by ts (chart-friendly).
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const sp = request.nextUrl.searchParams;
  const symbolsRaw = sp.get("symbols");
  if (typeof symbolsRaw !== "string" || !symbolsRaw.trim()) {
    return jsonError(
      400,
      "validation_error",
      "symbols query required (comma-separated, max 4).",
    );
  }
  if (symbolsRaw.length > MAX_SYMBOLS_PARAM_CHARS) {
    return jsonError(400, "validation_error", "symbols query too long.");
  }

  const seen = new Set<string>();
  const symbols: string[] = [];
  for (const part of symbolsRaw.split(",")) {
    const symbol = normalizeSymbol(part);
    if (!symbol) {
      return jsonError(400, "invalid_symbol", "Invalid symbol in list.");
    }
    if (seen.has(symbol)) continue;
    seen.add(symbol);
    symbols.push(symbol);
    if (symbols.length > MAX_COMPARE_SYMBOLS) {
      return jsonError(
        400,
        "validation_error",
        `At most ${MAX_COMPARE_SYMBOLS} symbols.`,
      );
    }
  }
  if (symbols.length < 1) {
    return jsonError(
      400,
      "validation_error",
      "Provide at least one valid symbol.",
    );
  }

  let limit = DEFAULT_LIMIT;
  const limitRaw = sp.get("limit");
  if (limitRaw != null) {
    const n = toSafePositiveInt(limitRaw);
    if (n == null) {
      return jsonError(
        400,
        "validation_error",
        "limit must be a positive integer.",
      );
    }
    limit = Math.min(n, MAX_LIMIT);
  }

  try {
    const pool = getPool();
    const known = await pool.query<{ symbol: string }>(
      `SELECT symbol FROM stocks WHERE symbol = ANY($1::text[])`,
      [symbols],
    );
    const knownSet = new Set(known.rows.map((r) => r.symbol));
    const missing = symbols.filter((s) => !knownSet.has(s));
    if (missing.length > 0) {
      return jsonError(
        404,
        "not_found",
        `Unknown symbol: ${missing[0]}.`,
      );
    }

    const series: {
      symbol: string;
      points: { ts: string | null; price: number }[];
    }[] = [];

    for (const symbol of symbols) {
      const result = await pool.query<{
        ts: Date | string;
        price: number;
      }>(
        `SELECT ts, price
           FROM price_snapshots
          WHERE symbol = $1
          ORDER BY ts DESC
          LIMIT $2`,
        [symbol, limit],
      );
      const points = result.rows
        .flatMap((row) => {
          const price = toFiniteNumber(row.price);
          if (price == null) return [];
          return [{ ts: toIso(row.ts), price }];
        })
        .reverse();
      series.push({ symbol, points });
    }

    return jsonOk({
      symbols,
      limit,
      max_symbols: MAX_COMPARE_SYMBOLS,
      series,
    });
  } catch (err) {
    console.error("GET /compare failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
