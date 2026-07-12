type Point = { ts: string | null; price: number | null | undefined };

export type FiniteSparklinePoint = { ts: string | null; price: number };

/**
 * Cap sparkline series length — snapshots API max is 200; a hostile /
 * unbounded points array used to allocate huge SVG polylines.
 */
export const MAX_SPARKLINE_POINTS = 200;

function isFinitePrice(price: unknown): price is number {
  return typeof price === "number" && Number.isFinite(price);
}

/** Drop null / NaN / ±Inf prices so SVG coords stay finite. */
export function finiteSparklinePoints(points: Point[]): FiniteSparklinePoint[] {
  const out: FiniteSparklinePoint[] = [];
  // Hostile / wrong-shape callers must not throw on non-iterable input.
  if (!Array.isArray(points)) return out;
  for (const p of points) {
    if (out.length >= MAX_SPARKLINE_POINTS) break;
    if (p == null || typeof p !== "object") continue;
    if (!isFinitePrice(p.price)) continue;
    out.push({ ts: p.ts, price: p.price });
  }
  return out;
}
