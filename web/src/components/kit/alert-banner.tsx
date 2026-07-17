import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Tone = "info" | "success" | "warning" | "danger";

const tones: Record<Tone, string> = {
  info: "border-border bg-muted/40 text-foreground",
  success: "border-emerald-200 bg-emerald-50 text-emerald-950",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  danger: "border-red-200 bg-red-50 text-red-950",
};

/** HyperUI-style alert banner — ops notices (Ceyfi port). */
export function AlertBanner({
  tone = "info",
  title,
  description,
  icon: Icon,
  action,
  className,
  role = "status",
}: {
  tone?: Tone;
  title: string;
  description?: string;
  icon: LucideIcon;
  action?: ReactNode;
  className?: string;
  /** Use `alert` for interruptive ops failures; default `status` for static chrome. */
  role?: "status" | "alert";
}) {
  return (
    <div
      role={role}
      className={cn("rounded-xl border p-4 sm:p-5", tones[tone], className)}
    >
      <div className="flex items-start gap-3 sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <Icon className="mt-0.5 size-5 shrink-0" aria-hidden />
          <div className="min-w-0">
            <p className="text-sm font-semibold leading-snug">{title}</p>
            {description ? (
              <p className="mt-1 text-xs leading-relaxed opacity-80">
                {description}
              </p>
            ) : null}
          </div>
        </div>
        {action}
      </div>
    </div>
  );
}
