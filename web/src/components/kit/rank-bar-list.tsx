import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type RankBarItem = {
  id: string;
  label: string;
  /** Raw score used for bar max-normalization. */
  value: number;
  /** Formatted right-side primary value. */
  valueLabel?: string;
  /** Optional secondary right-side line (e.g. turnover). */
  metaRight?: string | null;
  href?: string;
  sublabel?: string | null;
  /** Mover tones only when the value is a signed %; people influence stays neutral. */
  tone?: "neutral" | "up" | "down";
};

/**
 * Tremor bar-list pattern — proportional bars by max(value).
 * Chime tokens; not a trading terminal.
 */
export function RankBarList({
  items,
  className,
  empty = "Nothing to rank yet.",
  selectedId,
  onSelect,
  showRank = false,
  barClassName,
}: {
  items: RankBarItem[];
  className?: string;
  empty?: string;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  showRank?: boolean;
  barClassName?: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }

  const max = Math.max(...items.map((i) => (Number.isFinite(i.value) ? i.value : 0)), 0.01);

  return (
    <ul className={cn("space-y-1", className)}>
      {items.map((item, index) => {
        const pct = Math.min(100, Math.round(((item.value || 0) / max) * 100));
        const selected = selectedId != null && selectedId === item.id;
        const interactive = Boolean(onSelect);
        const barTone =
          item.tone === "up"
            ? "bg-emerald-500/70"
            : item.tone === "down"
              ? "bg-destructive/70"
              : "bg-foreground/65";

        const body = (
          <>
            <div
              className={cn(
                "grid items-baseline gap-x-2",
                showRank
                  ? "grid-cols-[1.5rem_minmax(0,1fr)_auto]"
                  : "grid-cols-[minmax(0,1fr)_auto]",
              )}
            >
              {showRank ? (
                <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                  {index + 1}
                </span>
              ) : null}
              <span className="min-w-0">
                <span className="block truncate text-[13px] font-medium leading-tight">
                  {item.label}
                </span>
                {item.sublabel ? (
                  <span className="mt-0.5 block truncate text-[11px] text-muted-foreground">
                    {item.sublabel}
                  </span>
                ) : null}
              </span>
              <span className="shrink-0 text-right">
                {item.valueLabel ? (
                  <span className="block font-mono text-xs tabular-nums">
                    {item.valueLabel}
                  </span>
                ) : null}
                {item.metaRight ? (
                  <span className="mt-0.5 block font-mono text-[10px] tabular-nums text-muted-foreground">
                    {item.metaRight}
                  </span>
                ) : null}
              </span>
            </div>
            <div
              className={cn(
                "mt-1 h-1 overflow-hidden rounded-sm bg-muted",
                showRank && "ml-7",
                barClassName,
              )}
              role="img"
              aria-label={`${item.label}: ${item.valueLabel ?? item.value}`}
            >
              <div
                className={cn(
                  "h-full rounded-sm transition-[width] duration-300",
                  barTone,
                )}
                style={{ width: `${Math.max(pct, 2)}%` }}
                aria-hidden
              />
            </div>
          </>
        );

        return (
          <li key={item.id}>
            {interactive ? (
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => onSelect?.(item.id)}
                className={cn(
                  "w-full rounded-md px-2 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected ? "bg-muted" : "hover:bg-muted/60",
                )}
              >
                {body}
              </button>
            ) : item.href ? (
              <Link
                href={item.href}
                className="block rounded-md px-2 py-2 transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {body}
              </Link>
            ) : (
              <div className="px-2 py-2">{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Compact chip toggle for filter bars (HyperUI filter density). */
export function FilterChip({
  active,
  onClick,
  children,
  className,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex h-9 items-center rounded-md px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-foreground text-background"
          : "border border-border/70 text-muted-foreground hover:bg-muted/40",
        className,
      )}
    >
      {children}
    </button>
  );
}
