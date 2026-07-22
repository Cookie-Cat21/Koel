import type { NextRequest } from "next/server";

import {
  classifyFiling,
  FILING_CATEGORY_LABELS,
} from "@/lib/api/filing-categories";
import {
  MAX_DISCLOSURE_TITLE_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/**
 * GET /api/v1/events — thin calendar: upcoming XD + recent results filings
 * for the session watchlist (Groww-style events, Postgres only).
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;
  const userId = gated.session.user_id;

  try {
    const pool = getPool();

    const xd = await pool.query<{
      id: number;
      symbol: string;
      d_xd: Date | string | null;
      dps: number | null;
      title: string | null;
    }>(
      `SELECT de.id, de.symbol, de.d_xd, de.dps, de.title
         FROM dividend_events de
         JOIN watchlist_items w
           ON w.symbol = de.symbol AND w.user_id = $1
        WHERE de.d_xd IS NOT NULL
          AND de.d_xd >= CURRENT_DATE
          AND de.d_xd <= (CURRENT_DATE + 60)
        ORDER BY de.d_xd ASC
        LIMIT 40`,
      [userId],
    );

    const results = await pool.query<{
      id: number;
      symbol: string;
      title: string | null;
      category: string | null;
      published_at: Date | string | null;
    }>(
      `SELECT d.id, d.symbol, d.title, d.category, d.published_at
         FROM disclosures d
         JOIN watchlist_items w
           ON w.symbol = d.symbol AND w.user_id = $1
        WHERE d.published_at >= (NOW() - INTERVAL '45 days')
        ORDER BY d.published_at DESC NULLS LAST
        LIMIT 80`,
      [userId],
    );

    const xdItems = xd.rows.flatMap((row) => {
      const symbol = normalizeSymbol(row.symbol);
      if (!symbol) return [];
      const amt =
        typeof row.dps === "number" && Number.isFinite(row.dps)
          ? ` · Rs ${row.dps}`
          : "";
      return [
        {
          id: `xd:${row.id}`,
          kind: "xd" as const,
          at: toIso(row.d_xd),
          symbol,
          title:
            sanitizeDisclosureText(row.title, MAX_DISCLOSURE_TITLE_LENGTH) ||
            `Ex-dividend${amt}`,
          badge: "XD",
          href: `/symbols/${encodeURIComponent(symbol)}`,
        },
      ];
    });

    const resultItems = results.rows.flatMap((row) => {
      const symbol = normalizeSymbol(row.symbol);
      if (!symbol) return [];
      const tag = classifyFiling(row.category, row.title);
      if (tag !== "results") return [];
      return [
        {
          id: `results:${row.id}`,
          kind: "results" as const,
          at: toIso(row.published_at),
          symbol,
          title:
            sanitizeDisclosureText(row.title, MAX_DISCLOSURE_TITLE_LENGTH) ||
            "Results filing",
          badge: FILING_CATEGORY_LABELS.results,
          href: `/symbols/${encodeURIComponent(symbol)}`,
        },
      ];
    });

    return jsonOk({
      xd: xdItems,
      results: resultItems.slice(0, 40),
      count: xdItems.length + Math.min(resultItems.length, 40),
    });
  } catch (err) {
    console.error("GET /events failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
