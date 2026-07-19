import type { FilingMetricComparison } from "@/components/kit/filing-metrics-panel";
import { formatNumber, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Compact EPS + YoY strip for symbol quote — densify cake without fake NAV.
 * Research / NFA.
 */
export function FilingSnapshotStrip({
  epsBasic,
  currency,
  comparison,
  className,
}: {
  epsBasic: number | null;
  currency?: string | null;
  comparison?: FilingMetricComparison | null;
  className?: string;
}) {
  if (epsBasic == null || !Number.isFinite(epsBasic)) return null;

  const yoy =
    comparison?.eps_delta_pct != null &&
    Number.isFinite(comparison.eps_delta_pct)
      ? comparison.eps_delta_pct
      : null;
  const cur = currency && /^[A-Z]{3,8}$/.test(currency) ? currency : "LKR";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 border-t border-border/50 px-5 py-3 sm:px-6",
        className,
      )}
      aria-label="Filing snapshot"
    >
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Filing
      </span>
      <span className="text-xs text-muted-foreground">
        EPS{" "}
        <span className="font-mono tabular-nums text-foreground">
          {formatNumber(epsBasic)} {cur}
        </span>
      </span>
      {yoy != null ? (
        <span className="text-xs text-muted-foreground">
          YoY{" "}
          <span
            className={cn(
              "font-mono tabular-nums",
              yoy > 0 && "text-emerald-700 dark:text-emerald-300",
              yoy < 0 && "text-rose-700 dark:text-rose-300",
            )}
          >
            {formatPct(yoy)}
          </span>
        </span>
      ) : null}
    </div>
  );
}
