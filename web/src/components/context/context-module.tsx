import Link from "next/link";
import type { ReactNode } from "react";

import type { MacroSeriesCard } from "@/lib/api/macro-context";
import { cn } from "@/lib/utils";

function MiniSpark({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max !== min ? max - min : 1;
  const w = 140;
  const h = 40;
  const pad = 2;
  const pts = values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (w - pad * 2);
      const y = pad + (1 - (v - min) / span) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const up = values[values.length - 1]! >= values[0]!;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-10 w-36" aria-hidden>
      <polyline
        fill="none"
        stroke={up ? "oklch(0.45 0.08 185)" : "oklch(0.5 0.1 25)"}
        strokeWidth="1.75"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={pts}
      />
    </svg>
  );
}

function fmtValue(n: number | null, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e3) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return n.toFixed(digits);
}

/**
 * HyperUI / Tremor spark-ticker pattern — one job per module.
 */
export function ContextModule({
  title,
  subtitle,
  card,
  formatDigits = 2,
  sectorHref,
  sectorLabel,
  emptyHint,
  footer,
}: {
  title: string;
  subtitle: string;
  card: MacroSeriesCard;
  formatDigits?: number;
  sectorHref?: string;
  sectorLabel?: string;
  emptyHint: string;
  footer?: ReactNode;
}) {
  const latest = card.latest;
  const delta = card.delta_pct;
  const tone =
    delta == null ? "flat" : delta > 0 ? "up" : delta < 0 ? "down" : "flat";

  return (
    <section
      className="rounded-lg border border-border/80 bg-muted/10 px-4 py-4"
      aria-label={title}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
            {title}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        </div>
        {latest ? (
          <MiniSpark values={card.history.map((p) => p.value)} />
        ) : null}
      </div>

      {latest ? (
        <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="font-mono text-3xl font-semibold tabular-nums tracking-tight">
              {fmtValue(latest.value, formatDigits)}
              {latest.unit ? (
                <span className="ms-1 text-sm font-normal text-muted-foreground">
                  {latest.unit}
                </span>
              ) : null}
            </p>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
              As of {latest.as_of_date ?? "—"}
              {latest.attribution ? ` · ${latest.attribution}` : null}
            </p>
          </div>
          {delta != null ? (
            <span
              className={cn(
                "inline-flex items-center rounded-sm px-2 py-1 font-mono text-xs tabular-nums",
                tone === "up" &&
                  "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300",
                tone === "down" &&
                  "bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300",
                tone === "flat" && "bg-muted text-muted-foreground",
              )}
            >
              {delta > 0 ? "+" : ""}
              {delta.toFixed(2)}%
            </span>
          ) : null}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">{emptyHint}</p>
      )}

      <div className="mt-4 flex flex-wrap gap-3 text-xs">
        {sectorHref && sectorLabel ? (
          <Link
            href={sectorHref}
            className="font-medium underline-offset-4 hover:underline"
          >
            {sectorLabel} →
          </Link>
        ) : null}
        <Link
          href="/alerts"
          className="font-medium underline-offset-4 hover:underline"
        >
          Telegram alerts
        </Link>
      </div>
      {footer}
    </section>
  );
}
