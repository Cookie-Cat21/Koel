import Link from "next/link";

import { ChangeBadge } from "@/components/kit/change-badge";
import type { PeriodReturns } from "@/lib/api/period-returns";
import { cn } from "@/lib/utils";

const ORDER = ["1W", "1M", "3M", "1Y"] as const;

/**
 * Compact multi-horizon return chips for symbol detail.
 * Research / NFA — not a screener column farm.
 */
export function PeriodReturnsStrip({
  returns,
  className,
}: {
  returns: PeriodReturns;
  className?: string;
}) {
  const hasAny = ORDER.some((k) => returns[k] != null);
  if (!hasAny) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 border-t border-border/50 px-5 py-3 sm:px-6",
        className,
      )}
      aria-label="Period returns"
    >
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Returns
      </span>
      <Link
        href="/help#symbol-returns-tech"
        className="text-[11px] text-muted-foreground underline underline-offset-4 transition-colors hover:text-foreground"
      >
        How calculated
      </Link>
      {ORDER.map((key) => {
        const v = returns[key];
        return (
          <span
            key={key}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span className="font-medium">{key}</span>
            {v == null ? (
              <span className="text-muted-foreground/70">—</span>
            ) : (
              <ChangeBadge changePct={v} />
            )}
          </span>
        );
      })}
    </div>
  );
}
