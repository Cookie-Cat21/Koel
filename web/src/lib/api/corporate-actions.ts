/**
 * Share split / consolidation helpers for chart + period-return adjust.
 * ``daily_bars`` stay CSE-unadjusted; apply factors at read time.
 */

import type { DailyBarPoint } from "@/lib/api/daily-bars";
import { toFiniteNumber } from "@/lib/api/finite-number";

export type CorporateActionKind = "split" | "consolidation";

export type CorporateActionPoint = {
  effective_date: string;
  kind: CorporateActionKind;
  ratio_from: number;
  ratio_to: number;
  source?: string | null;
  title?: string | null;
};

/** Multiply pre-effective OHLC by this to align with post-effective prices. */
export function adjustFactor(ratioFrom: number, ratioTo: number): number {
  if (
    !Number.isFinite(ratioFrom) ||
    !Number.isFinite(ratioTo) ||
    ratioFrom <= 0 ||
    ratioTo <= 0
  ) {
    return 1;
  }
  return ratioFrom / ratioTo;
}

function parseTradeDate(raw: unknown): string | null {
  if (raw instanceof Date) return raw.toISOString().slice(0, 10);
  if (typeof raw !== "string") return null;
  const d = raw.trim().slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : null;
}

export function normalizeCorporateAction(row: {
  effective_date?: unknown;
  kind?: unknown;
  ratio_from?: unknown;
  ratio_to?: unknown;
  source?: unknown;
  title?: unknown;
}): CorporateActionPoint | null {
  const effective = parseTradeDate(row.effective_date);
  if (!effective) return null;
  const kind = row.kind === "consolidation" ? "consolidation" : "split";
  const ratioFrom = toFiniteNumber(row.ratio_from);
  const ratioTo = toFiniteNumber(row.ratio_to);
  if (
    ratioFrom == null ||
    ratioTo == null ||
    ratioFrom <= 0 ||
    ratioTo <= 0 ||
    ratioFrom === ratioTo
  ) {
    return null;
  }
  return {
    effective_date: effective,
    kind,
    ratio_from: Math.round(ratioFrom),
    ratio_to: Math.round(ratioTo),
    source: typeof row.source === "string" ? row.source : null,
    title: typeof row.title === "string" ? row.title : null,
  };
}

/**
 * Scale bars before each action's effective_date so the path is continuous.
 * Bars on/after effective_date keep raw CSE closes.
 */
export function adjustBarsForSplits(
  barsAsc: DailyBarPoint[],
  actions: CorporateActionPoint[],
): DailyBarPoint[] {
  if (!Array.isArray(barsAsc) || barsAsc.length === 0) return [];
  if (!Array.isArray(actions) || actions.length === 0) {
    return barsAsc.map((b) => ({ ...b }));
  }
  const sorted = [...actions].sort((a, b) =>
    a.effective_date.localeCompare(b.effective_date),
  );
  return barsAsc.map((bar) => {
    let factor = 1;
    for (const action of sorted) {
      if (bar.trade_date < action.effective_date) {
        factor *= adjustFactor(action.ratio_from, action.ratio_to);
      }
    }
    if (factor === 1) return { ...bar };
    const scale = (v: number | null): number | null =>
      v == null || !Number.isFinite(v) ? v : v * factor;
    const close = bar.close * factor;
    const open = scale(bar.open);
    let high = bar.high * factor;
    let low = bar.low * factor;
    if (high < low) {
      const tmp = high;
      high = low;
      low = tmp;
    }
    return {
      trade_date: bar.trade_date,
      open,
      high: Math.max(high, close, open ?? close),
      low: Math.min(low, close, open ?? close),
      close,
      volume: bar.volume,
    };
  });
}

export function actionLabel(action: CorporateActionPoint): string {
  if (action.kind === "consolidation") {
    return `${action.ratio_from}:${action.ratio_to} consolidation`;
  }
  return `${action.ratio_from}:${action.ratio_to} share split`;
}
