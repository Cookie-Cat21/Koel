import Link from "next/link";
import type { ReactNode } from "react";

import { AreaSpark } from "@/components/kit/area-spark";
import {
  isDemoMacroAttribution,
  isResearchMacroAttribution,
  type MacroSeriesCard,
} from "@/lib/api/macro-context";
import { toneFromSeries } from "@/lib/area-spark";
import { cn } from "@/lib/utils";

function fmtValue(n: number | null, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e3)
    return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return n.toFixed(digits);
}

/**
 * HyperUI / Tremor spark-ticker module — value + full-width area spark.
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
  const historyValues = card.history.map((p) => p.value);
  // Prefer session Δ tone so the spark matches the badge (not first→last).
  const sparkTone =
    tone === "up" || tone === "down"
      ? tone
      : toneFromSeries(historyValues, true);

  return (
    <section
      className={cn(
        "flex min-h-[13.5rem] flex-col overflow-hidden rounded-xl border border-border/80 bg-background shadow-[0_1px_0_oklch(0.9_0.006_250_/_0.55)]",
        !latest && "border-dashed bg-muted/10 shadow-none",
      )}
      aria-label={title}
    >
      <div className="flex flex-1 flex-col px-4 pt-4 pb-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[10px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
              {title}
            </h2>
            {latest && isDemoMacroAttribution(latest.attribution) ? (
              <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-amber-800 uppercase dark:text-amber-200">
                Demo seed
              </span>
            ) : null}
            {latest &&
            !isDemoMacroAttribution(latest.attribution) &&
            isResearchMacroAttribution(latest.attribution) ? (
              <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
                Research / delayed
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-sm leading-snug text-muted-foreground">
            {subtitle}
          </p>
        </div>

        {latest ? (
          <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0">
              <p className="font-display text-3xl font-semibold tracking-tight tabular-nums">
                {fmtValue(latest.value, formatDigits)}
                {latest.unit ? (
                  <span className="ms-1.5 text-sm font-normal text-muted-foreground">
                    {latest.unit}
                  </span>
                ) : null}
              </p>
              <p className="mt-1 font-mono text-[11px] leading-snug text-muted-foreground">
                As of {latest.as_of_date ?? "—"}
                {latest.attribution ? ` · ${latest.attribution}` : null}
              </p>
            </div>
            {delta != null ? (
              <span
                className={cn(
                  "inline-flex items-center rounded-md px-2 py-1 font-mono text-xs tabular-nums",
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
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            {emptyHint}
          </p>
        )}

        <div className="mt-auto flex flex-wrap gap-3 pt-3 text-xs">
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
      </div>

      {latest && historyValues.length >= 2 ? (
        <div className="border-t border-border/50 bg-muted/15 px-3 pt-2.5 pb-2.5">
          <AreaSpark
            values={historyValues}
            labels={card.history.map((p) => p.as_of_date)}
            tone={sparkTone === "flat" ? "neutral" : sparkTone}
            heightClass="h-[4.5rem]"
            ariaLabel={`${title} history spark`}
            interactive
          />
        </div>
      ) : (
        <div className="mt-auto border-t border-dashed border-border/50 px-4 py-3">
          <div className="h-10 rounded-md bg-muted/40" aria-hidden />
        </div>
      )}
    </section>
  );
}
