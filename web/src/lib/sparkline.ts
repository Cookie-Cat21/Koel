type Point = { ts: string | null; price: number | null | undefined };

export type FiniteSparklinePoint = { ts: string | null; price: number };

function isFinitePrice(price: unknown): price is number {
  return typeof price === "number" && Number.isFinite(price);
}

/** Drop null / NaN / ±Inf prices so SVG coords stay finite. */
export function finiteSparklinePoints(points: Point[]): FiniteSparklinePoint[] {
  const out: FiniteSparklinePoint[] = [];
  for (const p of points) {
    if (!isFinitePrice(p.price)) continue;
    out.push({ ts: p.ts, price: p.price });
  }
  return out;
}
