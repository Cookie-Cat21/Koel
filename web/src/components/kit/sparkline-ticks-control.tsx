"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import {
  DEFAULT_SPARKLINE_TICKS,
  SPARKLINE_TICK_OPTIONS,
  type SparklineTickOption,
} from "@/lib/sparkline-ticks";
import { cn } from "@/lib/utils";

export {
  ABSOLUTE_MAX_SPARKLINE_TICKS,
  DEFAULT_SPARKLINE_TICKS,
  parseSparklineTicks,
  SPARKLINE_TICK_OPTIONS,
  type SparklineTickOption,
} from "@/lib/sparkline-ticks";

/**
 * Query-param control for sparkline depth (`?ticks=`). Server page re-fetches
 * snapshots with the chosen limit.
 */
export function SparklineTicksControl({
  value,
  className,
}: {
  value: SparklineTickOption;
  className?: string;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  return (
    <div
      className={cn("flex flex-wrap items-center gap-1.5", className)}
      role="group"
      aria-label="Sparkline tick count"
    >
      <span className="text-xs text-muted-foreground">Ticks</span>
      {SPARKLINE_TICK_OPTIONS.map((n) => {
        const params = new URLSearchParams(searchParams.toString());
        if (n === DEFAULT_SPARKLINE_TICKS) {
          params.delete("ticks");
        } else {
          params.set("ticks", String(n));
        }
        const qs = params.toString();
        const href = qs ? `${pathname}?${qs}` : pathname;
        const active = value === n;
        return (
          <Link
            key={n}
            href={href}
            scroll={false}
            className={cn(
              "inline-flex min-h-7 items-center rounded-md border px-2 text-xs tabular-nums transition-colors",
              active
                ? "border-foreground bg-foreground text-background"
                : "border-border/70 text-muted-foreground hover:bg-muted/40 hover:text-foreground",
            )}
            aria-current={active ? "true" : undefined}
          >
            {n}
          </Link>
        );
      })}
    </div>
  );
}
