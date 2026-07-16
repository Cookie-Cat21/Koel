import type { NextRequest } from "next/server";

import {
  MAX_SECTOR_INDEX_CODE_LENGTH,
  MAX_SECTOR_INDEX_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/market-browse";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/** ASPI + S&P SL20, with headroom for future CSE market indexes. */
const MAX_INDEXES = 20;

type IndexRow = {
  code: string | null;
  name: string | null;
  value: number | string | null;
  change_pct: number | string | null;
  ts: Date | string;
};

/**
 * GET /api/v1/indexes — latest market index ticks from Postgres only.
 * Session required; CSRF not required. No CSE HTTP from the dashboard.
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  try {
    const pool = getPool();
    const result = await pool.query<IndexRow>(
      `SELECT DISTINCT ON (code)
         code, name, value, change_pct, ts
       FROM index_snapshots
       WHERE code IS NOT NULL AND btrim(code) <> ''
       ORDER BY code, ts DESC
       LIMIT $1`,
      [MAX_INDEXES],
    );

    const items = result.rows.flatMap((row) => {
      const code = sanitizeDisclosureText(
        row.code,
        MAX_SECTOR_INDEX_CODE_LENGTH,
      );
      if (!code) return [];
      return [
        {
          code,
          name: sanitizeDisclosureText(row.name, MAX_SECTOR_INDEX_NAME_LENGTH),
          value: toFiniteNumber(row.value),
          change_pct: toFiniteNumber(row.change_pct),
          ts: toIso(row.ts),
        },
      ];
    });

    return jsonOk({ items });
  } catch (err) {
    console.error("GET /indexes failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
