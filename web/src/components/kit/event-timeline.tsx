import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type EventTimelineItem = {
  id: string;
  /** ISO date or display string; shown as mono meta. */
  at?: string | null;
  title: string;
  href?: string | null;
  external?: boolean;
  badge?: string | null;
  meta?: string | null;
  /** Dot emphasis: live = filled ring, empty = dashed, default = solid border. */
  emphasis?: "default" | "live" | "empty";
  /** Optional body under the title (seat lists, etc.). */
  children?: ReactNode;
};

/**
 * HyperUI-style vertical timeline for research events (filings, board notes).
 * Time-ordered only — not a news terminal.
 */
export function EventTimeline({
  items,
  className,
  empty,
}: {
  items: EventTimelineItem[];
  className?: string;
  empty?: ReactNode;
}) {
  if (items.length === 0) {
    return (
      empty ?? (
        <p className="text-sm text-muted-foreground">No events on file yet.</p>
      )
    );
  }

  return (
    <ol
      className={cn("relative space-y-3 border-l border-border pl-4", className)}
    >
      {items.map((item) => {
        const titleNode =
          item.href && item.external && /^https?:\/\//i.test(item.href) ? (
            <a
              href={item.href}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block text-[13px] text-foreground underline-offset-2 hover:underline"
            >
              {item.title}
              <span className="sr-only"> (opens in new tab)</span>
            </a>
          ) : item.href ? (
            <Link
              href={item.href}
              className="mt-1 block text-[13px] text-foreground underline-offset-2 hover:underline"
            >
              {item.title}
            </Link>
          ) : (
            <p className="mt-1 text-[13px] text-foreground">{item.title}</p>
          );

        return (
          <li key={item.id} className="relative">
            <span
              aria-hidden
              className={cn(
                "absolute -left-[1.3rem] top-1.5 size-2.5 rounded-full border bg-background",
                item.emphasis === "live" && "border-2 border-foreground",
                item.emphasis === "empty" &&
                  "border border-dashed border-muted-foreground/40",
                (!item.emphasis || item.emphasis === "default") &&
                  "border-border",
              )}
            />
            <div
              className={cn(
                "rounded-lg px-4 py-2.5",
                item.emphasis === "live"
                  ? "border border-border bg-background"
                  : item.emphasis === "empty"
                    ? "border border-dashed border-border/80"
                    : "border border-border/80 bg-card/40",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                {item.at ? (
                  <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                    {item.at}
                  </span>
                ) : null}
                {item.badge ? (
                  <Badge variant="outline" className="text-[10px]">
                    {item.badge}
                  </Badge>
                ) : null}
                {item.meta ? (
                  <span className="font-mono text-[11px] font-semibold text-muted-foreground">
                    {item.meta}
                  </span>
                ) : null}
              </div>
              {titleNode}
              {item.children}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
