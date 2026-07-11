import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  title: string;
  description: ReactNode;
  action?: ReactNode;
  className?: string;
};

/**
 * Brand-readable empty panel for list surfaces (watchlist, alerts).
 * Deliberate first-viewport signal — not a blank table.
 */
export function EmptyState({
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "chime-rise mt-8 overflow-hidden rounded-xl border border-border/70",
        className,
      )}
      role="status"
    >
      <div className="chime-atmosphere px-5 py-10 sm:px-8 sm:py-12">
        <p className="font-display text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          {title}
        </p>
        <div className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground sm:text-base">
          {description}
        </div>
        {action ? <div className="mt-6">{action}</div> : null}
      </div>
    </div>
  );
}
