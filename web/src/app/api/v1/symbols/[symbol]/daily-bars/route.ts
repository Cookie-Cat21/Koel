import type { NextRequest } from "next/server";

import {
  adjustBarsForSplits,
  normalizeCorporateAction,
  type CorporateActionPoint,
} from "@/lib/api/corporate-actions";
import {
  DEFAULT_DAILY_BARS_LIMIT,
  MAX_DAILY_BARS_LIMIT,
  normalizeDailyBar,
} from "@/lib/api/daily-bars";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbolParam } from "@/lib/api/symbol";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ symbol: string }> };

/**
 * GET /api/v1/symbols/{symbol}/daily-bars — daily OHLC for candlestick expand.
 * Postgres ``daily_bars`` only (~1y path history). Session required.
 *
 * By default returns split-adjusted bars when ``corporate_actions`` exist.
 * Pass ``?adjusted=0`` for raw CSE closes.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const { symbol: raw } = await context.params;
  const symbol = normalizeSymbolParam(raw);
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid symbol.");
  }

  let limit = DEFAULT_DAILY_BARS_LIMIT;
  const limitRaw = request.nextUrl.searchParams.get("limit");
  if (limitRaw != null) {
    const n = toSafePositiveInt(limitRaw);
    if (n == null) {
      return jsonError(
        400,
        "validation_error",
        "limit must be a positive integer.",
      );
    }
    limit = Math.min(n, MAX_DAILY_BARS_LIMIT);
  }

  const adjustedParam = request.nextUrl.searchParams.get("adjusted");
  const wantAdjusted = adjustedParam !== "0" && adjustedParam !== "false";

  try {
    const pool = getPool();
    const exists = await pool.query(
      `SELECT 1 FROM stocks WHERE symbol = $1`,
      [symbol],
    );
    if (exists.rows.length === 0) {
      return jsonError(404, "not_found", "Unknown symbol.");
    }

    // Newest N, then reverse to ascending for chart.
    const result = await pool.query<{
      trade_date: Date | string;
      open: number | null;
      high: number | null;
      low: number | null;
      price: number;
      volume: number | null;
    }>(
      `
      SELECT trade_date, open, high, low, price, volume
      FROM daily_bars
      WHERE symbol = $1
      ORDER BY trade_date DESC
      LIMIT $2
      `,
      [symbol, limit],
    );

    const rawBars = result.rows
      .map((row) => normalizeDailyBar(row))
      .filter((b): b is NonNullable<typeof b> => b != null)
      .reverse();

    let actions: CorporateActionPoint[] = [];
    if (wantAdjusted) {
      try {
        const ca = await pool.query<{
          effective_date: Date | string;
          kind: string;
          ratio_from: number;
          ratio_to: number;
          source: string | null;
          title: string | null;
        }>(
          `
          SELECT effective_date, kind, ratio_from, ratio_to, source, title
          FROM corporate_actions
          WHERE symbol = $1
          ORDER BY effective_date ASC
          `,
          [symbol],
        );
        for (const row of ca.rows) {
          const n = normalizeCorporateAction(row);
          if (n) actions.push(n);
        }
      } catch {
        // Table may not exist yet on an unmigrated DB — serve raw bars.
        actions = [];
      }
    }

    const bars =
      wantAdjusted && actions.length > 0
        ? adjustBarsForSplits(rawBars, actions)
        : rawBars;

    return jsonOk({
      symbol,
      count: bars.length,
      bars,
      adjusted: wantAdjusted && actions.length > 0,
      corporate_actions: actions,
      disclaimer:
        wantAdjusted && actions.length > 0
          ? "Daily OHLC split-adjusted from koel corporate_actions when known — research only, not financial advice. Raw CSE closes: ?adjusted=0."
          : "Daily OHLC from koel path history — research only, not financial advice.",
    });
  } catch (err) {
    console.error("GET /symbols/:symbol/daily-bars failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
