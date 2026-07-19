import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/** HyperUI-style stat card — overview / health KPIs (Ceyfi port, koel tokens). */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: LucideIcon;
  className?: string;
}) {
  return (
    <article
      className={cn(
        "rounded-xl border border-border bg-card p-5 transition-colors hover:border-foreground/20",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            {label}
          </p>
          <p className="mt-1 break-words font-mono text-2xl font-semibold tracking-tight text-foreground tabular-nums">
            {value}
          </p>
          {hint ? (
            <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
          ) : null}
        </div>
        {Icon ? (
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-muted text-foreground">
            <Icon className="size-5" aria-hidden />
          </span>
        ) : null}
      </div>
    </article>
  );
}
