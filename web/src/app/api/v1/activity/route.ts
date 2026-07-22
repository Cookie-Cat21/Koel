import type { NextRequest } from "next/server";

import {
  classifyFiling,
  FILING_CATEGORY_LABELS,
} from "@/lib/api/filing-categories";
import {
  MAX_DISCLOSURE_TITLE_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const MAX_ITEMS = 80;

export type ActivityItem = {
  id: string;
  kind: "fire" | "disclosure" | "xd";
  at: string | null;
  symbol: string | null;
  title: string;
  href: string | null;
  badge: string | null;
  meta: string | null;
};

/**
 * GET /api/v1/activity — merged watchlist timeline (fires + disclosures + XD).
 * Postgres only; research / NFA surface.
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const url = new URL(request.url);
  const limitRaw = toSafePositiveInt(url.searchParams.get("limit"));
  const limit = Math.min(limitRaw ?? 40, MAX_ITEMS);
  const userId = gated.session.user_id;

  try {
    const pool = getPool();
    const items: ActivityItem[] = [];

    const fires = await pool.query<{
      id: number;
      symbol: string;
      type: string;
      message_text: string | null;
      fired_at: Date | string;
    }>(
      `SELECT al.id, ar.symbol, ar.type, al.message_text, al.fired_at
         FROM alert_log al
         JOIN alert_rules ar ON ar.id = al.rule_id
        WHERE ar.user_id = $1
        ORDER BY al.fired_at DESC
        LIMIT $2`,
      [userId, limit],
    );
    for (const row of fires.rows) {
      const symbol = normalizeSymbol(row.symbol);
      // Prefer a short trigger line over the full Telegram body (NFA blob).
      const rawMsg =
        typeof row.message_text === "string" ? row.message_text : "";
      const triggerLine =
        rawMsg
          .split("\n")
          .map((l) => l.trim())
          .find((l) => /^trigger:/i.test(l))
          ?.replace(/^trigger:\s*/i, "") ?? "";
      const title =
        sanitizeDisclosureText(
          triggerLine || `Alert fired (${row.type})`,
          MAX_DISCLOSURE_TITLE_LENGTH,
        ) || `Alert fired (${row.type})`;
      items.push({
        id: `fire:${row.id}`,
        kind: "fire",
        at: toIso(row.fired_at),
        symbol,
        title,
        href: symbol ? `/symbols/${encodeURIComponent(symbol)}` : "/alerts/history",
        badge: "Fire",
        meta: typeof row.type === "string" ? row.type : null,
      });
    }

    const disclosures = await pool.query<{
      id: number;
      symbol: string;
      title: string | null;
      category: string | null;
      published_at: Date | string | null;
      url: string | null;
    }>(
      `SELECT d.id, d.symbol, d.title, d.category, d.published_at, d.url
         FROM disclosures d
         JOIN watchlist_items w
           ON w.symbol = d.symbol AND w.user_id = $1
        ORDER BY d.published_at DESC NULLS LAST, d.id DESC
        LIMIT $2`,
      [userId, limit],
    );
    for (const row of disclosures.rows) {
      const symbol = normalizeSymbol(row.symbol);
      const title =
        sanitizeDisclosureText(row.title, MAX_DISCLOSURE_TITLE_LENGTH) ||
        "Disclosure";
      const tag = classifyFiling(row.category, row.title);
      items.push({
        id: `disc:${row.id}`,
        kind: "disclosure",
        at: toIso(row.published_at),
        symbol,
        title,
        href: symbol ? `/symbols/${encodeURIComponent(symbol)}` : null,
        badge: FILING_CATEGORY_LABELS[tag],
        meta: sanitizeDisclosureText(row.category, 64),
      });
    }

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
          AND de.d_xd >= (CURRENT_DATE - 7)
          AND de.d_xd <= (CURRENT_DATE + 45)
        ORDER BY de.d_xd ASC
        LIMIT $2`,
      [userId, Math.min(limit, 30)],
    );
    for (const row of xd.rows) {
      const symbol = normalizeSymbol(row.symbol);
      const amt =
        typeof row.dps === "number" && Number.isFinite(row.dps)
          ? `Rs ${row.dps}`
          : null;
      items.push({
        id: `xd:${row.id}`,
        kind: "xd",
        at: toIso(row.d_xd),
        symbol,
        title:
          sanitizeDisclosureText(row.title, MAX_DISCLOSURE_TITLE_LENGTH) ||
          `XD soon${amt ? ` · ${amt}` : ""}`,
        href: symbol ? `/symbols/${encodeURIComponent(symbol)}` : "/dividends",
        badge: "XD",
        meta: amt,
      });
    }

    items.sort((a, b) => {
      const ta = a.at ? Date.parse(a.at) : 0;
      const tb = b.at ? Date.parse(b.at) : 0;
      return tb - ta;
    });

    return jsonOk({ items: items.slice(0, limit), count: Math.min(items.length, limit) });
  } catch (err) {
    console.error("GET /activity failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
