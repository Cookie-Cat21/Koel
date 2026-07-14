import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Soft-fill status chips for thin-dash runtime states (armed, delivery).
 * Pattern: dinaya StatusBadge / HyperUI badge — border + muted fill, not solid KPI pills.
 */

const ARMED_CLASS =
  "border-primary/25 bg-primary/10 text-primary hover:bg-primary/10";
const DISARMED_CLASS =
  "border-border bg-muted/60 text-muted-foreground hover:bg-muted/60";

const DELIVERY_CLASS = {
  sent: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 hover:bg-emerald-500/10 dark:text-emerald-300",
  delivered_unmarked:
    "border-sky-500/30 bg-sky-500/10 text-sky-700 hover:bg-sky-500/10 dark:text-sky-300",
  retrying:
    "border-amber-500/30 bg-amber-500/10 text-amber-700 hover:bg-amber-500/10 dark:text-amber-300",
  dead_lettered:
    "border-destructive/30 bg-destructive/10 text-destructive hover:bg-destructive/10",
} as const;

export type DeliveryStatusKey = keyof typeof DELIVERY_CLASS;

export function ArmedBadge({
  armed,
  className,
}: {
  armed: boolean;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={cn(armed ? ARMED_CLASS : DISARMED_CLASS, className)}
    >
      {armed ? "Armed" : "Disarmed"}
    </Badge>
  );
}

export function DeliveryBadge({
  status,
  label,
  className,
}: {
  status: DeliveryStatusKey;
  label: string;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={cn(DELIVERY_CLASS[status], className)}
    >
      {label}
    </Badge>
  );
}
