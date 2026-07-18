import { ExpandablePriceChart } from "@/components/charts/expandable-price-chart";
import { ChangeBadge } from "@/components/kit/change-badge";
import type { DailyBarPoint } from "@/lib/api/daily-bars";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export type IndexStripItem = {
  code: string;
  name: string;
  value: number | null;
  change_pct: number | null;
  ts?: string | null;
};

export type IndexStripBars = Record<string, DailyBarPoint[]>;
export type IndexStripTicks = Record<
  string,
  { ts: string | null; price: number | null }[]
>;

/**
 * Zero-Sum style index strip — ASPI / S&P SL20 from poller-persisted snaps,
 * with expandable daily candles (same expand pattern as symbol pages).
 */
export function IndexStrip({
  items,
  barsByCode,
  ticksByCode,
  className,
  empty = "Index snapshots not available yet.",
}: {
  items: IndexStripItem[];
  barsByCode?: IndexStripBars;
  ticksByCode?: IndexStripTicks;
  className?: string;
  empty?: string;
}) {
  if (items.length === 0) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)} role="status">
        {empty}
      </p>
    );
  }

  return (
    <ul
      className={cn("grid gap-3 sm:grid-cols-2", className)}
      aria-label="Market indexes"
    >
      {items.map((item) => {
        const bars = barsByCode?.[item.code] ?? [];
        const ticks = ticksByCode?.[item.code] ?? [];
        const hasChart = bars.length >= 2 || ticks.length >= 2;
        return (
          <li
            key={item.code}
            className="min-w-0 overflow-hidden rounded-lg border border-border/80 bg-muted/20"
          >
            <div className="flex flex-wrap items-end justify-between gap-2 px-3 pt-3">
              <div className="min-w-0">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  {item.name}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="font-mono text-lg font-semibold tabular-nums tracking-tight">
                    {formatNumber(item.value)}
                  </span>
                  <ChangeBadge changePct={item.change_pct} />
                </div>
              </div>
            </div>
            {hasChart ? (
              <div className="mt-2 px-2 pb-2">
                <ExpandablePriceChart
                  symbol={item.code}
                  seriesKind="index"
                  points={ticks}
                  initialBars={bars.length >= 2 ? bars : null}
                  initialRange="3M"
                  className="w-full max-w-none"
                />
              </div>
            ) : (
              <p className="px-3 pb-3 pt-2 text-xs text-muted-foreground">
                Path history not loaded yet for this index.
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
