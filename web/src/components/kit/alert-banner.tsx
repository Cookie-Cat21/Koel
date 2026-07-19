import { Info, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { cn } from "@/lib/utils";

type Tone = "info" | "success" | "warning" | "danger";

const tones: Record<Tone, string> = {
  info: "border-border bg-muted/50 text-foreground *:[svg]:text-foreground",
  success:
    "border-emerald-200/80 bg-emerald-50 text-emerald-950 *:[svg]:text-emerald-800",
  warning:
    "border-amber-200/80 bg-amber-50 text-amber-950 *:[svg]:text-amber-800",
  danger: "border-red-200/80 bg-red-50 text-red-950 *:[svg]:text-red-800",
};

/**
 * Watermelon alert-01 — shadcn Alert + Info icon.
 * lucide instead of @aliimam/icons; koel tones (no blue candy default).
 */
export function AlertBanner({
  tone = "info",
  title,
  description,
  icon: Icon = Info,
  action,
  className,
  role = "status",
}: {
  tone?: Tone;
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: ReactNode;
  className?: string;
  role?: "status" | "alert";
}) {
  return (
    <Alert
      role={role}
      className={cn(tones[tone], "items-start", className)}
    >
      <Icon className="size-4" aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <div className="min-w-0">
          <AlertTitle>{title}</AlertTitle>
          {description ? (
            <AlertDescription>{description}</AlertDescription>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </Alert>
  );
}
