import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

/** HyperUI-style stat card — overview / health KPIs (Ceyfi port, Quiverly tokens). */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  href,
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: LucideIcon;
  /** Optional click-through (overview KPIs → watchlist / alerts / history). */
  href?: string;
  className?: string;
}) {
  const body = (
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
  );

  const shellClass = cn(
    "rounded-xl border border-border bg-card p-5 transition-colors hover:border-foreground/20",
    href ? "block focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" : null,
    className,
  );

  if (href) {
    return (
      <Link href={href} className={shellClass} aria-label={`${label}: ${value}`}>
        {body}
      </Link>
    );
  }

  return <article className={shellClass}>{body}</article>;
}
