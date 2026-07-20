/**
 * Disclosure-first Context news — Postgres CSE filings + market notices only.
 * No third-party publisher scrape.
 */

import type { Pool } from "pg";

import {
  MAX_DISCLOSURE_TITLE_LENGTH,
  safeFilingHref,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toIso } from "@/lib/api/time";

const MAX_SYMBOL = 32;

export type ContextNewsItem = {
  kind: "disclosure" | "notice";
  id: number;
  symbol: string | null;
  title: string;
  as_of: string | null;
  href: string | null;
};

function cleanSymbol(raw: unknown): string | null {
  const s = sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    MAX_SYMBOL,
  );
  return s;
}

/**
 * Recent CSE disclosures + market notices for the Context strip.
 * Drops absurd future ``published_at`` by preferring ``seen_at`` when
 * published is more than 2 days ahead of now.
 */
export async function queryContextNews(
  pool: Pool,
  limit = 12,
): Promise<ContextNewsItem[]> {
  const lim = Math.min(Math.max(limit, 1), 40);
  try {
    const res = await pool.query(
      `WITH filings AS (
         SELECT
           d.id,
           'disclosure'::text AS kind,
           d.symbol,
           d.title,
           d.pdf_url,
           d.url,
           CASE
             WHEN d.published_at IS NOT NULL
              AND d.published_at <= (now() + interval '2 days')
             THEN d.published_at
             ELSE d.seen_at
           END AS as_of
         FROM disclosures d
         WHERE d.title IS NOT NULL
           AND length(trim(d.title)) > 0
       ),
       notices AS (
         SELECT
           n.id,
           'notice'::text AS kind,
           n.symbol,
           n.title,
           NULL::text AS pdf_url,
           n.url,
           CASE
             WHEN n.published_at IS NOT NULL
              AND n.published_at <= (now() + interval '2 days')
             THEN n.published_at
             ELSE n.seen_at
           END AS as_of
         FROM market_notices n
         WHERE n.title IS NOT NULL
           AND length(trim(n.title)) > 0
       ),
       combined AS (
         SELECT * FROM filings
         UNION ALL
         SELECT * FROM notices
       )
       SELECT id, kind, symbol, title, pdf_url, url, as_of
       FROM combined
       WHERE as_of IS NOT NULL
         AND as_of >= (now() - interval '45 days')
       ORDER BY as_of DESC
       LIMIT $1`,
      [lim],
    );

    const out: ContextNewsItem[] = [];
    for (const row of res.rows) {
      const title = sanitizeDisclosureText(
        typeof row.title === "string" ? row.title : null,
        MAX_DISCLOSURE_TITLE_LENGTH,
      );
      if (!title) continue;
      const id = typeof row.id === "number" ? row.id : Number(row.id);
      if (!Number.isSafeInteger(id) || id < 1) continue;
      const kind = row.kind === "notice" ? "notice" : "disclosure";
      out.push({
        kind,
        id,
        symbol: cleanSymbol(row.symbol),
        title,
        as_of: toIso(row.as_of),
        href: safeFilingHref(row.pdf_url, row.url),
      });
    }
    return out;
  } catch {
    return [];
  }
}
