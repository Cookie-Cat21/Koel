import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

export type SectorHeatItem = {
  sector_id: number;
  name: string;
  change_pct: number | null;
};

/**
 * Soft sector heat strip — color by change_pct, not a heatmap terminal.
 */
export function SectorHeatStrip({
  items,
  className,
  empty = "No sector data yet.",
}: {
  items: SectorHeatItem[];
  className?: string;
  empty?: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }

  return (
    <ul
      className={cn("flex flex-wrap gap-1.5", className)}
      aria-label="Sector performance"
    >
      {items.map((item) => {
        const pct = item.change_pct;
        const up = pct != null && pct > 0;
        const down = pct != null && pct < 0;
        return (
          <li
            key={item.sector_id}
            title={`${item.name}: ${formatPct(pct)}`}
            className={cn(
              "rounded-md border px-2 py-1 text-xs",
              up &&
                "border-emerald-500/25 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
              down &&
                "border-destructive/25 bg-destructive/10 text-destructive",
              !up &&
                !down &&
                "border-border bg-muted/40 text-muted-foreground",
            )}
          >
            <span className="max-w-[10rem] truncate font-medium">{item.name}</span>
            <span className="ml-1.5 font-mono tabular-nums">
              {formatPct(pct)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
