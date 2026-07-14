import { ChangeBadge } from "@/components/kit/change-badge";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export type IndexStripItem = {
  code: string;
  name: string;
  value: number | null;
  change_pct: number | null;
  ts?: string | null;
};

/**
 * Zero-Sum style index strip — ASPI / S&P SL20 from poller-persisted snaps only.
 */
export function IndexStrip({
  items,
  className,
  empty = "Index snapshots not available yet.",
}: {
  items: IndexStripItem[];
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
      className={cn(
        "flex flex-wrap gap-3 sm:gap-4",
        className,
      )}
      aria-label="Market indexes"
    >
      {items.map((item) => (
        <li
          key={item.code}
          className="min-w-[9rem] flex-1 rounded-lg border border-border/80 bg-muted/20 px-3 py-2"
        >
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {item.name}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-medium tabular-nums">
              {formatNumber(item.value)}
            </span>
            <ChangeBadge changePct={item.change_pct} />
          </div>
        </li>
      ))}
    </ul>
  );
}
