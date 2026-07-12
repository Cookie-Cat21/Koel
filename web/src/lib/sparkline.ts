import { MAX_ISO_INPUT_LENGTH } from "@/lib/api/time";

type Point = { ts: string | null; price: number | null | undefined };

export type FiniteSparklinePoint = { ts: string | null; price: number };

/**
 * Cap sparkline series length — snapshots API max is 200; a hostile /
 * unbounded points array used to allocate huge SVG polylines.
 */
export const MAX_SPARKLINE_POINTS = 200;

/**
 * Cap absolute price magnitude (parity ``MAX_FORMAT_ABS_VALUE``).
 * Hostile finite extremes (e.g. ``1e308``) used to enter SVG span math and
 * balloon ``toFixed`` polyline coordinates.
 */
export const MAX_SPARKLINE_ABS_PRICE = 1e15;

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/;

function isFinitePrice(price: unknown): price is number {
  return (
    typeof price === "number" &&
    Number.isFinite(price) &&
    Math.abs(price) <= MAX_SPARKLINE_ABS_PRICE
  );
}

/**
 * Fail-closed sparkline ts — non-strings / controls / overlong used to sit
 * in FiniteSparklinePoint and leak into title/aria callers.
 */
function sanitizeSparklineTs(raw: unknown): string | null {
  if (raw == null) return null;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > MAX_ISO_INPUT_LENGTH) return null;
  if (CTRL_RE.test(trimmed)) return null;
  return trimmed;
}

/** Drop null / NaN / ±Inf / absurd-magnitude prices so SVG coords stay finite. */
export function finiteSparklinePoints(points: Point[]): FiniteSparklinePoint[] {
  const out: FiniteSparklinePoint[] = [];
  // Hostile / wrong-shape callers must not throw on non-iterable input.
  if (!Array.isArray(points)) return out;
  for (const p of points) {
    if (out.length >= MAX_SPARKLINE_POINTS) break;
    if (p == null || typeof p !== "object") continue;
    if (!isFinitePrice(p.price)) continue;
    out.push({ ts: sanitizeSparklineTs(p.ts), price: p.price });
  }
  return out;
}
