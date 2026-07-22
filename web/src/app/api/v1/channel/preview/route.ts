import type { NextRequest } from "next/server";

import { toFiniteNumber } from "@/lib/api/finite-number";
import { INDEX_CODES } from "@/lib/api/indexes";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/**
 * GET /api/v1/channel/preview — sample public-channel open/close copy from Postgres.
 * Does not send Telegram; shows what W7 would post when TELEGRAM_PUBLIC_CHANNEL_ID is set.
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  try {
    const pool = getPool();
    const indexes = await pool.query<{
      code: string;
      value: number | null;
      change_pct: number | null;
      ts: Date | string | null;
    }>(
      `SELECT DISTINCT ON (code) code, value, change_pct, ts
         FROM index_snapshots
        WHERE code = ANY($1::text[])
        ORDER BY code, ts DESC`,
      [INDEX_CODES as unknown as string[]],
    );

    const movers = await pool.query<{
      symbol: string;
      change_pct: number | null;
      price: number | null;
    }>(
      `SELECT DISTINCT ON (symbol) symbol, change_pct, price
         FROM price_snapshots
        WHERE ts > NOW() - INTERVAL '2 days'
        ORDER BY symbol, ts DESC`,
    );
    const ranked = movers.rows
      .map((r) => ({
        symbol: r.symbol,
        change_pct: toFiniteNumber(r.change_pct),
        price: toFiniteNumber(r.price),
      }))
      .filter((r) => r.change_pct != null)
      .sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));

    const discCount = await pool.query<{ n: string | number }>(
      `SELECT COUNT(*)::int AS n FROM disclosures
        WHERE published_at >= (CURRENT_DATE AT TIME ZONE 'Asia/Colombo')`,
    );

    const indexLines = indexes.rows.map((r) => {
      const pct = toFiniteNumber(r.change_pct);
      const val = toFiniteNumber(r.value);
      return `${r.code} ${val ?? "?"} (${pct != null ? `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%` : "?"})`;
    });

    const top = ranked.slice(0, 5);
    const bottom = ranked.slice(-5).reverse();
    const nDisc = Number(discCount.rows[0]?.n ?? 0);

    const closeBody = [
      "koel close summary (preview)",
      ...indexLines,
      "",
      "Top movers:",
      ...top.map(
        (m) =>
          `↑ ${m.symbol} ${m.change_pct != null ? `${m.change_pct >= 0 ? "+" : ""}${m.change_pct.toFixed(2)}%` : "?"}`,
      ),
      "",
      "Laggards:",
      ...bottom.map(
        (m) =>
          `↓ ${m.symbol} ${m.change_pct != null ? `${m.change_pct.toFixed(2)}%` : "?"}`,
      ),
      "",
      `Disclosures today: ${Number.isFinite(nDisc) ? nDisc : 0}`,
      "",
      "Get alerts for your stocks → koel bot",
      "Not financial advice.",
    ].join("\n");

    return jsonOk({
      configured: Boolean(process.env.TELEGRAM_PUBLIC_CHANNEL_ID?.trim()),
      as_of: toIso(new Date()),
      preview: closeBody,
      indexes: indexLines,
    });
  } catch (err) {
    console.error("GET /channel/preview failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
