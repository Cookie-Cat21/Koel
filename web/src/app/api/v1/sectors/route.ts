import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type SectorRow = {
  sector_id: number | string;
  symbol: string;
  name: string;
  index_code: string | null;
  index_name: string | null;
  index_value: number | string | null;
  change: number | string | null;
  change_pct: number | string | null;
  volume_today: number | string | null;
  turnover_today: number | string | null;
  previous_close: number | string | null;
  ts: Date | string;
};

function toFiniteNumber(value: unknown): number | null {
  if (value == null) return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * GET /api/v1/sectors — thin read of latest CSE sector index rows from Postgres.
 * Populated only when poller runs with SECTORS_INGEST=1. Session required;
 * CSRF not required (safe GET). No cse.lk. Not a screener / heatmap.
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  try {
    const pool = getPool();
    const result = await pool.query<SectorRow>(
      `SELECT sector_id, symbol, name, index_code, index_name,
              index_value, change, change_pct, volume_today, turnover_today,
              previous_close, ts
       FROM sectors
       ORDER BY change_pct DESC NULLS LAST, symbol ASC`,
    );

    const items = result.rows.flatMap((row) => {
      const sector_id = toFiniteNumber(row.sector_id);
      // Drop non-finite ids — JSON.stringify(NaN) becomes null and breaks clients.
      if (sector_id == null) return [];
      return [
        {
          sector_id,
          symbol: row.symbol,
          name: row.name,
          index_code: row.index_code,
          index_name: row.index_name,
          index_value: toFiniteNumber(row.index_value),
          change: toFiniteNumber(row.change),
          change_pct: toFiniteNumber(row.change_pct),
          volume_today: toFiniteNumber(row.volume_today),
          turnover_today: toFiniteNumber(row.turnover_today),
          previous_close: toFiniteNumber(row.previous_close),
          ts: toIso(row.ts),
        },
      ];
    });

    return jsonOk({ items });
  } catch (err) {
    console.error("GET /sectors failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
