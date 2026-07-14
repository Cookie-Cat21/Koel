import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Page title block — Ceyfi PageHeader structure, Dinaya left-rule eyebrow.
 * No decorative orbs/cards in the hero sense; one job per section.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0 max-w-2xl">
        {eyebrow ? (
          <p className="relative mb-2 pl-3 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            <span
              aria-hidden
              className="absolute top-1/2 left-0 h-3 w-[3px] -translate-y-1/2 rounded-sm bg-primary"
            />
            {eyebrow}
          </p>
        ) : null}
        <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground">
          {title}
        </h1>
        {description ? (
          <p
            className="mt-2 line-clamp-2 text-sm leading-relaxed text-muted-foreground sm:text-base"
            title={description}
          >
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}
