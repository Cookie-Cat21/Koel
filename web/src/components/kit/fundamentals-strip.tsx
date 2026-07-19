import type { FundamentalsLabels } from "@/lib/api/fundamentals";
import { formatCompactNumber, formatNumber, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Honest NAV / P/B / ROE when equity extract exists — never invent blanks.
 * Research / NFA.
 */
export function FundamentalsStrip({
  labels,
  className,
}: {
  labels: FundamentalsLabels;
  className?: string;
}) {
  const hasAny =
    labels.nav != null ||
    labels.price_to_book != null ||
    labels.roe_pct != null;
  if (!hasAny) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 border-t border-border/50 px-5 py-3 sm:px-6",
        className,
      )}
      aria-label="Fundamentals from filings"
    >
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Book
      </span>
      {labels.nav != null ? (
        <span className="inline-flex items-center gap-1 rounded-md border border-border/60 bg-muted/30 px-2 py-0.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/80">NAV</span>
          <span className="font-mono tabular-nums">
            {formatCompactNumber(labels.nav)} {labels.currency}
          </span>
        </span>
      ) : null}
      {labels.price_to_book != null ? (
        <span className="inline-flex items-center gap-1 rounded-md border border-border/60 bg-muted/30 px-2 py-0.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/80">P/B</span>
          <span className="font-mono tabular-nums">
            {formatNumber(labels.price_to_book, 2)}
          </span>
        </span>
      ) : null}
      {labels.roe_pct != null ? (
        <span className="inline-flex items-center gap-1 rounded-md border border-border/60 bg-muted/30 px-2 py-0.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/80">ROE</span>
          <span className="font-mono tabular-nums">
            {formatPct(labels.roe_pct)}
          </span>
        </span>
      ) : null}
      {labels.as_of ? (
        <span className="text-[11px] text-muted-foreground/80">
          as of {labels.as_of}
        </span>
      ) : null}
    </div>
  );
}
