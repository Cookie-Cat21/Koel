import { formatNumber } from "@/lib/format";
import { finiteSparklinePoints } from "@/lib/sparkline";

export { finiteSparklinePoints } from "@/lib/sparkline";

type Point = { ts: string | null; price: number | null | undefined };

/** Minimal price polyline — not TA, just recent ticks. */
export function Sparkline({
  points,
  className,
}: {
  points: Point[];
  className?: string;
}) {
  const series = finiteSparklinePoints(points);
  if (series.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Not enough ticks yet. koel needs at least two stored ticks for this sparkline.
      </p>
    );
  }

  const prices = series.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  // Guard degenerate / non-finite span (all equal, or poisoned min/max).
  const span = Number.isFinite(max - min) && max !== min ? max - min : 1;
  const w = 320;
  const h = 72;
  const pad = 4;

  const coords = series.map((p, i) => {
    const x = pad + (i / (series.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (p.price - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  // Fail closed: never emit NaN/Inf into SVG polyline points.
  if (coords.some((c) => c.includes("NaN") || c.includes("Infinity"))) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Not enough ticks yet. koel needs at least two stored ticks for this sparkline.
      </p>
    );
  }

  const first = prices[0]!;
  const last = prices[prices.length - 1]!;
  const up = last >= first;
  const dir = up ? "up" : "down";
  const aria = `Recent price ${dir} from ${formatNumber(first)} to ${formatNumber(last)} across ${series.length} ticks`;

  return (
    <div className={className ?? "max-w-md"}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-16 w-full"
        role="img"
        aria-label={aria}
      >
        <polyline
          fill="none"
          stroke={up ? "oklch(0.45 0.08 185)" : "oklch(0.5 0.1 25)"}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={coords.join(" ")}
        />
      </svg>
      <p className="mt-1 text-xs text-muted-foreground">
        {series.length} stored ticks · {formatNumber(first)} → {formatNumber(last)}
      </p>
    </div>
  );
}
