/**
 * CSE tape pulse — foreign flow + market-wide book pressure from Postgres.
 * Tier A only (no upstream calls from web/).
 */

import type { Pool } from "pg";

import { toFiniteNumber } from "@/lib/api/finite-number";
import { toIso } from "@/lib/api/time";

export type ForeignDay = {
  trade_date: string;
  foreign_net: number | null;
  equity_foreign_purchase: number | null;
  equity_foreign_sales: number | null;
  volume_of_turnover: number | null;
  foreign_share_pct: number | null;
};

export type BookPressure = {
  imbalance_pct: number | null;
  bid_share_pct: number | null;
  sample_n: number;
  as_of: string | null;
  label: "bid_heavy" | "ask_heavy" | "balanced" | "unknown";
};

/** One market-wide book sample window for the Book detail page spark. */
export type BookSamplePoint = {
  as_of: string;
  sample_n: number;
  bid_share_pct: number;
  imbalance_pct: number;
};

export type TapePulse = {
  foreign: ForeignDay | null;
  foreign_history: ForeignDay[];
  foreign_delta: number | null;
  book: BookPressure;
};

function asDateIso(raw: unknown): string | null {
  if (raw instanceof Date && !Number.isNaN(raw.getTime())) {
    return raw.toISOString().slice(0, 10);
  }
  if (typeof raw === "string") {
    const m = raw.match(/^(\d{4}-\d{2}-\d{2})/);
    return m ? m[1]! : null;
  }
  return null;
}

function sharePct(
  purchase: number | null,
  sales: number | null,
  turnover: number | null,
): number | null {
  if (purchase == null || sales == null || turnover == null) return null;
  if (!(turnover > 0)) return null;
  const activity = purchase + sales;
  if (!(activity >= 0) || !Number.isFinite(activity)) return null;
  return (activity / turnover) * 100;
}

function parseForeignRow(row: Record<string, unknown>): ForeignDay | null {
  const trade_date = asDateIso(row.trade_date);
  if (!trade_date) return null;
  const purchase = toFiniteNumber(row.equity_foreign_purchase);
  const sales = toFiniteNumber(row.equity_foreign_sales);
  const turnover = toFiniteNumber(row.volume_of_turnover);
  return {
    trade_date,
    foreign_net: toFiniteNumber(row.foreign_net),
    equity_foreign_purchase: purchase,
    equity_foreign_sales: sales,
    volume_of_turnover: turnover,
    foreign_share_pct: sharePct(purchase, sales, turnover),
  };
}

function bookLabel(imbPct: number | null): BookPressure["label"] {
  if (imbPct == null || !Number.isFinite(imbPct)) return "unknown";
  if (imbPct >= 8) return "bid_heavy";
  if (imbPct <= -8) return "ask_heavy";
  return "balanced";
}

/**
 * Latest foreign row + short history (asc), plus latest-session book sample.
 */
export async function queryTapePulse(
  pool: Pool,
  opts?: { foreignLimit?: number; bookLookbackMinutes?: number },
): Promise<TapePulse> {
  const foreignLimit = Math.min(Math.max(opts?.foreignLimit ?? 30, 1), 120);
  const bookLookback = Math.min(
    Math.max(opts?.bookLookbackMinutes ?? 24 * 60, 30),
    7 * 24 * 60,
  );

  const foreignRes = await pool.query(
    `SELECT trade_date, foreign_net, equity_foreign_purchase,
            equity_foreign_sales, volume_of_turnover
     FROM market_daily_summary
     ORDER BY trade_date DESC
     LIMIT $1`,
    [foreignLimit],
  );

  const historyDesc = foreignRes.rows
    .map((r) => parseForeignRow(r as Record<string, unknown>))
    .filter((r): r is ForeignDay => r != null);
  const foreign_history = [...historyDesc].reverse();
  const foreign = historyDesc[0] ?? null;
  const prior = historyDesc[1] ?? null;
  let foreign_delta: number | null = null;
  if (
    foreign?.foreign_net != null &&
    prior?.foreign_net != null &&
    Number.isFinite(foreign.foreign_net) &&
    Number.isFinite(prior.foreign_net)
  ) {
    foreign_delta = foreign.foreign_net - prior.foreign_net;
  }

  const bookRes = await pool.query(
    `SELECT total_bids, total_asks, ts
     FROM order_book_snapshots
     WHERE ts >= now() - ($1::text || ' minutes')::interval
     ORDER BY ts DESC
     LIMIT 500`,
    [String(bookLookback)],
  );

  let sumBids = 0;
  let sumAsks = 0;
  let sample_n = 0;
  let latestTs: string | null = null;
  for (const row of bookRes.rows) {
    const bids = toFiniteNumber(row.total_bids);
    const asks = toFiniteNumber(row.total_asks);
    if (bids == null || asks == null || bids <= 0 || asks <= 0) continue;
    sumBids += bids;
    sumAsks += asks;
    sample_n += 1;
    if (!latestTs) latestTs = toIso(row.ts);
  }

  const total = sumBids + sumAsks;
  let imbalance_pct: number | null = null;
  let bid_share_pct: number | null = null;
  if (total > 0 && sample_n > 0) {
    bid_share_pct = (sumBids / total) * 100;
    imbalance_pct = ((sumBids - sumAsks) / total) * 100;
  }

  return {
    foreign,
    foreign_history,
    foreign_delta,
    book: {
      imbalance_pct,
      bid_share_pct,
      sample_n,
      as_of: latestTs,
      label: bookLabel(imbalance_pct),
    },
  };
}

/**
 * Bucket recent public book totals into ~15m windows (asc) for Book detail.
 * Fail-soft — empty when no usable samples.
 */
export async function queryBookPressureSeries(
  pool: Pool,
  opts?: { lookbackMinutes?: number; maxPoints?: number },
): Promise<BookSamplePoint[]> {
  const bookLookback = Math.min(
    Math.max(opts?.lookbackMinutes ?? 24 * 60, 30),
    7 * 24 * 60,
  );
  const maxPoints = Math.min(Math.max(opts?.maxPoints ?? 48, 4), 120);

  const bookRes = await pool.query(
    `SELECT total_bids, total_asks, ts
     FROM order_book_snapshots
     WHERE ts >= now() - ($1::text || ' minutes')::interval
     ORDER BY ts ASC
     LIMIT 2000`,
    [String(bookLookback)],
  );

  type Bucket = {
    key: number;
    as_of: string;
    sumBids: number;
    sumAsks: number;
    sample_n: number;
  };
  const buckets = new Map<number, Bucket>();
  const BUCKET_MS = 15 * 60 * 1000;

  for (const row of bookRes.rows) {
    const bids = toFiniteNumber(row.total_bids);
    const asks = toFiniteNumber(row.total_asks);
    if (bids == null || asks == null || bids <= 0 || asks <= 0) continue;
    const iso = toIso(row.ts);
    if (!iso) continue;
    const ms = Date.parse(iso);
    if (!Number.isFinite(ms)) continue;
    const key = Math.floor(ms / BUCKET_MS) * BUCKET_MS;
    const existing = buckets.get(key);
    if (existing) {
      existing.sumBids += bids;
      existing.sumAsks += asks;
      existing.sample_n += 1;
      existing.as_of = iso;
    } else {
      buckets.set(key, {
        key,
        as_of: iso,
        sumBids: bids,
        sumAsks: asks,
        sample_n: 1,
      });
    }
  }

  const points: BookSamplePoint[] = [];
  for (const b of [...buckets.values()].sort((a, c) => a.key - c.key)) {
    const total = b.sumBids + b.sumAsks;
    if (!(total > 0) || b.sample_n < 1) continue;
    points.push({
      as_of: b.as_of,
      sample_n: b.sample_n,
      bid_share_pct: (b.sumBids / total) * 100,
      imbalance_pct: ((b.sumBids - b.sumAsks) / total) * 100,
    });
  }
  if (points.length <= maxPoints) return points;
  return points.slice(points.length - maxPoints);
}
