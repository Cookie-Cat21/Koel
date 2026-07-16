/**
 * Sparkline tick-depth helpers — shared by server pages and the client control.
 * Keep this file free of "use client" so SSR can parse `?ticks=`.
 */

/** Allowed sparkline depths — must stay ≤ API / SVG absolute max (500). */
export const SPARKLINE_TICK_OPTIONS = [60, 120, 200, 500] as const;
export type SparklineTickOption = (typeof SPARKLINE_TICK_OPTIONS)[number];

export const DEFAULT_SPARKLINE_TICKS = 60;
/** Absolute max polyline points (API + SVG + parse caps stay in lockstep). */
export const ABSOLUTE_MAX_SPARKLINE_TICKS = 500;

export function parseSparklineTicks(raw: unknown): SparklineTickOption {
  const text = Array.isArray(raw) ? raw[0] : raw;
  if (typeof text !== "string" || !text.trim()) return DEFAULT_SPARKLINE_TICKS;
  const n = Number.parseInt(text.trim(), 10);
  if (!Number.isSafeInteger(n)) return DEFAULT_SPARKLINE_TICKS;
  if ((SPARKLINE_TICK_OPTIONS as readonly number[]).includes(n)) {
    return n as SparklineTickOption;
  }
  return DEFAULT_SPARKLINE_TICKS;
}
