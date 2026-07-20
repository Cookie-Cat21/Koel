import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  title: string;
  description: ReactNode;
  action?: ReactNode;
  className?: string;
};

/**
 * Cap empty-panel titles so a misbuilt caller cannot balloon the status
 * region (parity with toast / inline-error message caps).
 */
export const MAX_EMPTY_STATE_TITLE_LENGTH = 120;

/**
 * Cap string descriptions — JSX ReactNode children stay trusted; plain
 * string props used to render uncapped / control-laden copy.
 */
export const MAX_EMPTY_STATE_DESCRIPTION_LENGTH = 600;

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/g;

/** Strip controls + length-cap before rendering empty-state titles. */
export function sanitizeEmptyStateTitle(raw: unknown): string {
  if (typeof raw !== "string") return "Nothing here yet";
  const cleaned = raw.replace(CTRL_RE, "").trim();
  if (!cleaned) return "Nothing here yet";
  return cleaned.length > MAX_EMPTY_STATE_TITLE_LENGTH
    ? cleaned.slice(0, MAX_EMPTY_STATE_TITLE_LENGTH).trimEnd()
    : cleaned;
}

/** Strip controls + length-cap for plain-string empty-state descriptions. */
export function sanitizeEmptyStateDescription(raw: unknown): string {
  if (typeof raw !== "string") return "";
  const cleaned = raw.replace(CTRL_RE, "").trim();
  if (!cleaned) return "";
  return cleaned.length > MAX_EMPTY_STATE_DESCRIPTION_LENGTH
    ? cleaned.slice(0, MAX_EMPTY_STATE_DESCRIPTION_LENGTH).trimEnd()
    : cleaned;
}

/**
 * Brand-readable empty panel for list surfaces (watchlist, alerts).
 * Deliberate first-viewport signal — not a blank table.
 */
export function EmptyState({
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  // Fail closed — never render uncapped / control-laden titles.
  const safeTitle = sanitizeEmptyStateTitle(title);
  // String descriptions must be sanitized; JSX ReactNode stays as-is.
  const safeDescription =
    typeof description === "string"
      ? sanitizeEmptyStateDescription(description)
      : description;
  return (
    <div
      className={cn(
        "koel-rise mt-8 overflow-hidden rounded-xl border border-border/70",
        className,
      )}
      role="status"
    >
      <div className="koel-atmosphere px-5 py-10 sm:px-8 sm:py-12">
        <p className="font-display text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          {safeTitle}
        </p>
        <div className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground sm:text-base">
          {safeDescription}
        </div>
        {action ? <div className="mt-6">{action}</div> : null}
      </div>
    </div>
  );
}
