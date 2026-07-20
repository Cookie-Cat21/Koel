import {
  MAX_DISCLOSURE_TITLE_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { MAX_DIVIDEND_DPS } from "@/lib/dividends";
import { getPool } from "@/lib/db";

const MAX_DIVIDEND_EVENT_TEXT = 64;
const MAX_UPCOMING_DIVIDENDS = 100;
const MAX_SYMBOL_DIVIDENDS = 50;

export type DividendEvent = {
  id: number;
  symbol: string;
  disclosure_id: number | null;
  d_ann: string | null;
  d_xd: string | null;
  d_pay: string | null;
  dps: number | null;
  kind: string | null;
  fy: string | null;
  dates_tbd: boolean;
  title: string | null;
};

export type UpcomingDividendEvent = Pick<
  DividendEvent,
  "id" | "symbol" | "d_xd" | "d_pay" | "dps" | "kind" | "title" | "dates_tbd"
>;

type DividendEventSqlRow = {
  id: string | number;
  symbol: string;
  disclosure_id: string | number | null;
  d_ann: Date | string | null;
  d_xd: Date | string | null;
  d_pay: Date | string | null;
  dps: number | string | null;
  kind: string | null;
  fy: string | null;
  dates_tbd: boolean | null;
  title: string | null;
};

function dateOnly(raw: unknown): string | null {
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  }
  const iso = toIso(raw);
  return iso ? iso.slice(0, 10) : null;
}

function shortText(raw: unknown): string | null {
  return sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    MAX_DIVIDEND_EVENT_TEXT,
  );
}

function safeDps(raw: unknown): number | null {
  const dps = toFiniteNumber(raw);
  if (dps == null || dps <= 0 || dps > MAX_DIVIDEND_DPS) return null;
  return dps;
}

export function mapDividendEvent(row: DividendEventSqlRow): DividendEvent | null {
  const id = toSafePositiveInt(row.id);
  const symbol = normalizeSymbol(row.symbol);
  if (id == null || !symbol) return null;
  const disclosure_id =
    row.disclosure_id == null ? null : toSafePositiveInt(row.disclosure_id);
  return {
    id,
    symbol,
    disclosure_id,
    d_ann: dateOnly(row.d_ann),
    d_xd: dateOnly(row.d_xd),
    d_pay: dateOnly(row.d_pay),
    dps: safeDps(row.dps),
    kind: shortText(row.kind),
    fy: shortText(row.fy),
    dates_tbd: row.dates_tbd === true,
    title: sanitizeDisclosureText(row.title, MAX_DISCLOSURE_TITLE_LENGTH),
  };
}

export async function loadUpcomingDividendEvents({
  horizonDays,
  userId,
  watchlistOnly = false,
  limit = MAX_UPCOMING_DIVIDENDS,
}: {
  horizonDays: number;
  userId?: number;
  watchlistOnly?: boolean;
  limit?: number;
}): Promise<UpcomingDividendEvent[]> {
  const days = Math.min(Math.max(Math.trunc(horizonDays), 0), 90);
  const cappedLimit = Math.min(Math.max(Math.trunc(limit), 1), MAX_UPCOMING_DIVIDENDS);
  const watchUserId = watchlistOnly && Number.isSafeInteger(userId) ? userId : null;
  const pool = getPool();
  const result = await pool.query<DividendEventSqlRow>(
    `SELECT id, symbol, disclosure_id, d_ann, d_xd, d_pay, dps, kind, fy,
            dates_tbd, title
       FROM dividend_events de
      WHERE de.d_xd IS NOT NULL
        AND de.d_xd >= timezone('Asia/Colombo', now())::date
        AND de.d_xd <= (timezone('Asia/Colombo', now())::date + $1::int)
        AND (
          $2::int IS NULL
          OR EXISTS (
            SELECT 1
              FROM watchlist_items w
             WHERE w.user_id = $2::int
               AND w.symbol = de.symbol
          )
        )
      ORDER BY de.d_xd ASC, de.symbol ASC, de.id DESC
      LIMIT $3`,
    [days, watchUserId, cappedLimit],
  );
  // Dedupe natural (symbol, d_xd, dps) — sync + manual upsert can double rows.
  const seen = new Set<string>();
  const out: UpcomingDividendEvent[] = [];
  for (const row of result.rows) {
    const mapped = mapDividendEvent(row);
    if (!mapped || !mapped.d_xd) continue;
    const key = `${mapped.symbol}|${mapped.d_xd}|${mapped.dps ?? ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      id: mapped.id,
      symbol: mapped.symbol,
      d_xd: mapped.d_xd,
      d_pay: mapped.d_pay,
      dps: mapped.dps,
      kind: mapped.kind,
      title: mapped.title,
      dates_tbd: mapped.dates_tbd,
    });
  }
  return out;
}

export async function loadDividendEventsForSymbol(
  symbol: string,
  limit = MAX_SYMBOL_DIVIDENDS,
): Promise<DividendEvent[]> {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) return [];
  const cappedLimit = Math.min(Math.max(Math.trunc(limit), 1), MAX_SYMBOL_DIVIDENDS);
  const pool = getPool();
  const result = await pool.query<DividendEventSqlRow>(
    `SELECT id, symbol, disclosure_id, d_ann, d_xd, d_pay, dps, kind, fy,
            dates_tbd, title
       FROM dividend_events
      WHERE symbol = $1
      ORDER BY
        CASE
          WHEN d_xd IS NOT NULL
           AND d_xd >= timezone('Asia/Colombo', now())::date THEN 0
          ELSE 1
        END,
        CASE
          WHEN d_xd IS NOT NULL
           AND d_xd >= timezone('Asia/Colombo', now())::date THEN d_xd
          ELSE NULL
        END ASC NULLS LAST,
        d_xd DESC NULLS LAST,
        d_ann DESC NULLS LAST,
        id DESC
      LIMIT $2`,
    [normalized, cappedLimit],
  );
  return result.rows.flatMap((row) => {
    const mapped = mapDividendEvent(row);
    return mapped ? [mapped] : [];
  });
}
