type Point = { ts: string | null; price: number };

/** Minimal price polyline — not TA, just recent ticks. */
export function Sparkline({
  points,
  className,
}: {
  points: Point[];
  className?: string;
}) {
  if (points.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Not enough ticks yet. Chime needs at least two stored ticks for this sparkline.
      </p>
    );
  }

  const prices = points.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const w = 320;
  const h = 72;
  const pad = 4;

  const coords = points.map((p, i) => {
    const x = pad + (i / (points.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (p.price - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const up = prices[prices.length - 1]! >= prices[0]!;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={className ?? "h-16 w-full max-w-md"}
      role="img"
      aria-label="Recent price sparkline"
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
  );
}
