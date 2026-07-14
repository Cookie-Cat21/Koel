import Link from "next/link";

import { ChangeBadge } from "@/components/kit/change-badge";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export type MoverBarItem = {
  symbol: string;
  name?: string | null;
  price?: number | null;
  change_pct: number | null;
};

function changeDirectionSr(pct: number | null): string {
  if (pct == null) return "change unknown";
  if (pct > 0) return "up ";
  if (pct < 0) return "down ";
  return "unchanged ";
}

/**
 * Tremor bar-list-01 pattern — proportional bars by |change_pct|.
 * Links to symbol detail; not a trading terminal.
 */
export function MoversBarList({
  items,
  className,
  empty = "No movers yet.",
}: {
  items: MoverBarItem[];
  className?: string;
  empty?: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }

  const maxAbs = Math.max(
    ...items.map((i) =>
      i.change_pct != null && Number.isFinite(i.change_pct)
        ? Math.abs(i.change_pct)
        : 0,
    ),
    0.01,
  );

  return (
    <ul className={cn("space-y-2", className)}>
      {items.map((item) => {
        const pct = item.change_pct;
        const abs = pct != null && Number.isFinite(pct) ? Math.abs(pct) : 0;
        const width = Math.min(100, Math.round((abs / maxAbs) * 100));
        const up = pct != null && pct > 0;
        const down = pct != null && pct < 0;
        return (
          <li key={item.symbol}>
            <div className="mb-1 flex items-baseline justify-between gap-2">
              <Link
                href={`/symbols/${encodeURIComponent(item.symbol)}`}
                aria-label={`Open ${item.symbol} detail to watch`}
                className="group flex min-w-0 items-baseline gap-2 rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                <span className="font-mono text-sm font-medium underline-offset-4 group-hover:underline">
                  {item.symbol}
                </span>
                <span className="shrink-0 text-xs font-medium text-foreground/70 underline-offset-4 group-hover:underline">
                  Watch
                </span>
              </Link>
              <span className="flex shrink-0 items-center gap-2">
                {item.price != null ? (
                  <span className="font-mono text-xs tabular-nums text-muted-foreground">
                    {formatNumber(item.price)}
                  </span>
                ) : null}
                <span className="sr-only">{changeDirectionSr(pct)}</span>
                <ChangeBadge changePct={pct} />
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full rounded-full transition-[width]",
                  up && "bg-emerald-500/70",
                  down && "bg-destructive/70",
                  !up && !down && "bg-muted-foreground/40",
                )}
                style={{ width: `${width}%` }}
                aria-hidden
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
