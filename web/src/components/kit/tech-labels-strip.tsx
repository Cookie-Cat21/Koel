import type { TechLabels } from "@/lib/api/tech-labels";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

function Chip({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "muted";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-border/60 bg-muted/30 px-2 py-0.5 text-xs",
        tone === "up" && "text-emerald-700 dark:text-emerald-300",
        tone === "down" && "text-rose-700 dark:text-rose-300",
        (tone == null || tone === "muted") && "text-muted-foreground",
      )}
    >
      <span className="font-medium text-foreground/80">{label}</span>
      <span className="font-mono tabular-nums">{value}</span>
    </span>
  );
}

/**
 * Thin TA labels for symbol detail (popover-density strip).
 * Not financial advice — observational only.
 */
export function TechLabelsStrip({
  labels,
  className,
}: {
  labels: TechLabels;
  className?: string;
}) {
  const hasAny =
    labels.sma50_pct != null ||
    labels.atr_pct != null ||
    labels.macd_bias != null ||
    labels.bb_pos != null ||
    labels.week52_pct != null;
  if (!hasAny) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 border-t border-border/50 px-5 py-3 sm:px-6",
        className,
      )}
      aria-label="Technical labels"
    >
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Tech
      </span>
      {labels.sma50_pct != null ? (
        <Chip
          label="SMA50"
          value={formatPct(labels.sma50_pct)}
          tone={
            labels.sma50_pct > 0 ? "up" : labels.sma50_pct < 0 ? "down" : "muted"
          }
        />
      ) : null}
      {labels.atr_pct != null ? (
        <Chip label="ATR" value={`${labels.atr_pct.toFixed(1)}%`} />
      ) : null}
      {labels.macd_bias != null ? (
        <Chip
          label="MACD"
          value={labels.macd_bias}
          tone={labels.macd_bias === "BULL" ? "up" : "down"}
        />
      ) : null}
      {labels.bb_pos != null ? <Chip label="BB" value={labels.bb_pos} /> : null}
      {labels.week52_pct != null ? (
        <Chip
          label="52W"
          value={`${Math.round(labels.week52_pct)}%`}
          tone={
            labels.week52_pct >= 70
              ? "up"
              : labels.week52_pct <= 30
                ? "down"
                : "muted"
          }
        />
      ) : null}
    </div>
  );
}
