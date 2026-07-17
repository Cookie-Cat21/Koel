/**
 * Direct Postgres loaders for symbol-page SSR.
 *
 * On Vercel, cookie-bearing ``serverApiGet`` self-fetches go to
 * ``VERCEL_URL`` / production host. Deployment Protection (SSO) often
 * returns a 200 HTML login shell — pages then parse empty ``items`` and
 * show “No disclosures yet” even when Neon has rows. Reading the pool
 * here keeps SSR on the same DATABASE_URL as the route handlers.
 */

import {
  MAX_BRIEF_LENGTH,
  MAX_DISCLOSURE_CATEGORY_LENGTH,
  MAX_DISCLOSURE_COMPANY_LENGTH,
  MAX_DISCLOSURE_EXTERNAL_ID_LENGTH,
  MAX_DISCLOSURE_TITLE_LENGTH,
  MAX_STOCK_NAME_LENGTH,
  MAX_STOCK_SECTOR_LENGTH,
  type BriefStatus,
  normalizeBriefStatus,
  safeAnnouncementUrl,
  safePdfUrl,
  sanitizeBriefText,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { getPool } from "@/lib/db";

const MAX_METRIC_ITEMS = 8;
const MAX_METRIC_TEXT = 32;

const METRIC_KINDS = new Set(["quarterly", "annual", "unknown"]);
const METRIC_ENTITIES = new Set(["group", "company", "unknown"]);
const METRIC_SCALES = new Set(["units", "thousands", "millions", "unknown"]);
const MATCH_QUALITIES = new Set([
  "exact_yoy",
  "approx_yoy",
  "missing_prior",
  "scale_mismatch",
  "entity_mismatch",
  "currency_mismatch",
  "skipped",
]);

function allowlistedText(
  raw: unknown,
  allowed: ReadonlySet<string>,
): string | null {
  const text = sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    MAX_METRIC_TEXT,
  );
  return text && allowed.has(text) ? text : null;
}

function metricCurrency(raw: unknown): string {
  const text = sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    MAX_METRIC_TEXT,
  );
  return text && /^[A-Z]{3,8}$/.test(text) ? text : "LKR";
}

function dateOnly(raw: unknown): string | null {
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  }
  const iso = toIso(raw);
  return iso ? iso.slice(0, 10) : null;
}

export type SymbolPageStock = {
  symbol: string;
  name: string | null;
  sector: string | null;
  last: {
    price: number | null;
    change: number | null;
    change_pct: number | null;
    volume: number | null;
    ts: string | null;
  } | null;
};

export type SymbolPageDisclosure = {
  id: number;
  external_id: string;
  title: string;
  category: string | null;
  url: string | null;
  published_at: string | null;
  company_name: string | null;
  pdf_url: string | null;
  brief: string | null;
  brief_status: BriefStatus | null;
};

export type SymbolPageMetric = {
  id: number;
  kind: string;
  fiscal_period_end: string | null;
  entity: string;
  scale: string;
  currency: string;
  revenue: number | null;
  profit: number | null;
  eps_basic: number | null;
  extract_ok: boolean;
  comparison: {
    match_quality: string;
    eps_delta_pct: number | null;
    revenue_delta_pct: number | null;
    profit_delta_pct: number | null;
    prior_filing_metrics_id: number | null;
  } | null;
};

export type SymbolPageBrief = {
  title: string;
  text: string;
  published_at: string;
};

export async function loadSymbolPageStock(
  symbol: string,
): Promise<SymbolPageStock | null> {
  const pool = getPool();
  const stock = await pool.query<{
    symbol: string;
    name: string | null;
    sector: string | null;
  }>(`SELECT symbol, name, sector FROM stocks WHERE symbol = $1`, [symbol]);
  if (stock.rows.length === 0) return null;
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
          price: toFiniteNumber(snap.rows[0].price),
          change: toFiniteNumber(snap.rows[0].change),
          change_pct: toFiniteNumber(snap.rows[0].change_pct),
          volume: toFiniteNumber(snap.rows[0].volume),
          ts: toIso(snap.rows[0].ts),
        };
  return {
    symbol: normalizeSymbol(row.symbol) ?? symbol,
    name: sanitizeDisclosureText(row.name, MAX_STOCK_NAME_LENGTH),
    sector: sanitizeDisclosureText(row.sector, MAX_STOCK_SECTOR_LENGTH),
    last,
  };
}

export async function loadSymbolPageDisclosures(
  symbol: string,
  limit = 20,
): Promise<SymbolPageDisclosure[]> {
  const pool = getPool();
  const result = await pool.query<{
    id: string | number;
    external_id: string;
    title: string;
    category: string | null;
    url: string;
    published_at: Date | string;
    company_name: string | null;
    pdf_url: string | null;
    brief: string | null;
    brief_status: string | null;
  }>(
    `SELECT d.id, d.external_id, d.title, d.category, d.url, d.published_at,
            d.company_name, d.pdf_url,
            b.brief, b.status AS brief_status
     FROM disclosures d
     LEFT JOIN disclosure_briefs b ON b.disclosure_id = d.id
     WHERE d.symbol = $1
     ORDER BY d.published_at DESC, d.id DESC
     LIMIT $2`,
    [symbol, Math.min(Math.max(limit, 1), 100)],
  );

  return result.rows.flatMap((row) => {
    const id = toSafePositiveInt(row.id);
    if (id == null) return [];
    const brief_status = normalizeBriefStatus(row.brief_status);
    const title =
      sanitizeDisclosureText(row.title, MAX_DISCLOSURE_TITLE_LENGTH) ?? "";
    if (!title) return [];
    return [
      {
        id,
        external_id:
          sanitizeDisclosureText(
            row.external_id,
            MAX_DISCLOSURE_EXTERNAL_ID_LENGTH,
          ) ?? "",
        title,
        category: sanitizeDisclosureText(
          row.category,
          MAX_DISCLOSURE_CATEGORY_LENGTH,
        ),
        url: safeAnnouncementUrl(row.url),
        published_at: toIso(row.published_at),
        company_name: sanitizeDisclosureText(
          row.company_name,
          MAX_DISCLOSURE_COMPANY_LENGTH,
        ),
        pdf_url: safePdfUrl(row.pdf_url),
        brief: sanitizeBriefText(row.brief, brief_status),
        brief_status,
      },
    ];
  });
}

export async function loadSymbolPageMetrics(symbol: string): Promise<{
  items: SymbolPageMetric[];
  brief: SymbolPageBrief | null;
}> {
  const pool = getPool();
  const metrics = await pool.query<{
    id: string | number;
    kind: string;
    fiscal_period_end: Date | string | null;
    entity: string;
    scale: string;
    currency: string;
    revenue: number | string | null;
    profit: number | string | null;
    eps_basic: number | string | null;
    extract_ok: boolean;
    match_quality: string | null;
    eps_delta_pct: number | string | null;
    revenue_delta_pct: number | string | null;
    profit_delta_pct: number | string | null;
    prior_filing_metrics_id: string | number | null;
  }>(
    `SELECT fm.id, fm.kind, fm.fiscal_period_end, fm.entity, fm.scale,
            fm.currency, fm.revenue, fm.profit, fm.eps_basic, fm.extract_ok,
            fc.match_quality, fc.eps_delta_pct, fc.revenue_delta_pct,
            fc.profit_delta_pct, fc.prior_filing_metrics_id
       FROM filing_metrics fm
       LEFT JOIN filing_comparisons fc ON fc.filing_metrics_id = fm.id
      WHERE fm.symbol = $1
      ORDER BY fm.fiscal_period_end DESC NULLS LAST, fm.id DESC
      LIMIT $2`,
    [symbol, MAX_METRIC_ITEMS],
  );

  const items = metrics.rows.flatMap((row) => {
    const id = toSafePositiveInt(row.id);
    if (id == null) return [];
    const kind = allowlistedText(row.kind, METRIC_KINDS);
    const entity = allowlistedText(row.entity, METRIC_ENTITIES);
    const scale = allowlistedText(row.scale, METRIC_SCALES);
    if (!kind || !entity || !scale) return [];

    const matchQuality = allowlistedText(row.match_quality, MATCH_QUALITIES);
    const priorId =
      row.prior_filing_metrics_id == null
        ? null
        : toSafePositiveInt(row.prior_filing_metrics_id);
    const comparison =
      matchQuality == null
        ? null
        : {
            match_quality: matchQuality,
            eps_delta_pct: toFiniteNumber(row.eps_delta_pct),
            revenue_delta_pct: toFiniteNumber(row.revenue_delta_pct),
            profit_delta_pct: toFiniteNumber(row.profit_delta_pct),
            prior_filing_metrics_id: priorId,
          };

    return [
      {
        id,
        kind,
        fiscal_period_end: dateOnly(row.fiscal_period_end),
        entity,
        scale,
        currency: metricCurrency(row.currency),
        revenue: toFiniteNumber(row.revenue),
        profit: toFiniteNumber(row.profit),
        eps_basic: toFiniteNumber(row.eps_basic),
        extract_ok: row.extract_ok === true,
        comparison,
      },
    ];
  });

  const briefResult = await pool.query<{
    title: string;
    brief: string | null;
    published_at: Date | string;
  }>(
    `SELECT d.title, b.brief, d.published_at
       FROM disclosure_briefs b
       JOIN disclosures d ON d.id = b.disclosure_id
      WHERE d.symbol = $1 AND b.status = 'ready'
      ORDER BY d.published_at DESC, d.id DESC
      LIMIT 1`,
    [symbol],
  );
  const briefRow = briefResult.rows[0];
  const briefText = sanitizeBriefText(briefRow?.brief ?? null, "ready");
  const briefTitle = sanitizeDisclosureText(
    briefRow?.title,
    MAX_DISCLOSURE_TITLE_LENGTH,
  );
  const briefPublishedAt = toIso(briefRow?.published_at);
  const brief =
    briefText && briefTitle && briefPublishedAt
      ? {
          title: briefTitle,
          text:
            sanitizeDisclosureText(briefText, MAX_BRIEF_LENGTH) ?? briefText,
          published_at: briefPublishedAt,
        }
      : null;

  return { items, brief };
}
