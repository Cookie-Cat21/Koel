import { ArrowDown, ArrowUp, Minus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

function changeDirectionSr(pct: number | null | undefined): string {
  if (pct == null || !Number.isFinite(pct)) return "change unknown";
  if (pct > 0) return "up ";
  if (pct < 0) return "down ";
  return "unchanged ";
}

/**
 * Daily % change chip — Tremor badge-03 / HyperUI pattern, koel tokens.
 * Soft fill; not a solid KPI wall.
 */
export function ChangeBadge({
  changePct,
  className,
}: {
  changePct: number | null | undefined;
  className?: string;
}) {
  if (changePct == null || !Number.isFinite(changePct)) {
    return (
      <Badge
        variant="outline"
        className={cn(
          "border-border bg-muted/50 font-mono text-muted-foreground",
          className,
        )}
      >
        <span className="sr-only">change unknown</span>
        <Minus className="size-3" aria-hidden />
        —
      </Badge>
    );
  }

  const up = changePct > 0;
  const down = changePct < 0;
  const Icon = up ? ArrowUp : down ? ArrowDown : Minus;

  return (
    <Badge
      variant="outline"
      className={cn(
        "font-mono tabular-nums",
        up &&
          "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        down &&
          "border-destructive/30 bg-destructive/10 text-destructive",
        !up &&
          !down &&
          "border-border bg-muted/50 text-muted-foreground",
        className,
      )}
    >
      <span className="sr-only">{changeDirectionSr(changePct)}</span>
      <Icon className="size-3" aria-hidden />
      {formatPct(changePct)}
    </Badge>
  );
}
