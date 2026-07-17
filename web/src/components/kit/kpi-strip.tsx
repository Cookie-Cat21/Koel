import { cn } from "@/lib/utils";

export type KpiStripItem = {
  id: string;
  label: string;
  value: string;
  hint?: string;
};

/**
 * Dense HyperUI-style KPI strip — index-strip density, not a StatCard wall.
 * Ownership / research maps only.
 */
export function KpiStrip({
  items,
  className,
  ariaLabel = "Summary metrics",
}: {
  items: KpiStripItem[];
  className?: string;
  ariaLabel?: string;
}) {
  if (items.length === 0) return null;

  return (
    <ul
      className={cn("flex flex-wrap gap-3", className)}
      aria-label={ariaLabel}
    >
      {items.map((item) => (
        <li
          key={item.id}
          className="min-w-[8.5rem] flex-1 rounded-lg border border-border/80 bg-muted/20 px-3 py-2"
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            {item.label}
          </p>
          <p className="mt-0.5 font-mono text-sm font-semibold tabular-nums tracking-tight text-foreground sm:text-base">
            {item.value}
          </p>
          {item.hint ? (
            <p className="mt-0.5 text-[11px] text-muted-foreground">{item.hint}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
