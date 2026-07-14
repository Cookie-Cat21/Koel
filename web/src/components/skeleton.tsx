import { NfaFooter } from "@/components/nfa-footer";
import { cn } from "@/lib/utils";

/** Pulse placeholder bar — teal-tinted muted, not purple. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "motion-safe:animate-pulse rounded-md bg-muted/80",
        className,
      )}
      aria-hidden
    />
  );
}

/** Cap skeleton rows — ``Array.from({ length: Infinity })`` throws; huge N OOMs. */
export const MAX_SKELETON_ROWS = 24;

/**
 * Allowlisted Tailwind width tokens for the loading title bar.
 * Medium: a misbuilt / hostile ``titleWidth`` used to inject arbitrary
 * className strings (including multi-KB junk) into the skeleton shell.
 */
const SKELETON_TITLE_WIDTHS = new Set([
  "w-24",
  "w-28",
  "w-32",
  "w-36",
  "w-40",
]);

export function safeSkeletonTitleWidth(raw: unknown): string {
  return typeof raw === "string" && SKELETON_TITLE_WIDTHS.has(raw)
    ? raw
    : "w-40";
}

/** Shared shell chrome for route `loading.tsx` (lists, browse, health, symbol). */
export function ListPageSkeleton({
  titleWidth = "w-40",
  rows = 5,
}: {
  titleWidth?: string;
  rows?: number;
}) {
  // Fail closed — non-integer / ≤0 / oversized rows must not allocate.
  const safeRows =
    typeof rows === "number" &&
    Number.isInteger(rows) &&
    rows > 0 &&
    rows <= MAX_SKELETON_ROWS
      ? rows
      : 5;
  // Fail closed — only allowlisted width tokens reach className.
  const safeTitleWidth = safeSkeletonTitleWidth(titleWidth);
  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <div className="sticky top-0 z-40 border-b border-border/70 bg-background/80 px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Skeleton className="h-7 w-20" />
          <div className="hidden gap-4 sm:flex">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-14" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
      </div>
      <div
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
        role="status"
        aria-busy="true"
        aria-label="Loading"
      >
        <Skeleton className={cn("h-9", safeTitleWidth)} />
        <Skeleton className="mt-3 h-4 w-full max-w-md" />
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end">
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-10 w-24 shrink-0" />
        </div>
        <ul className="mt-8 divide-y divide-border/60">
          {Array.from({ length: safeRows }, (_, i) => (
            <li
              key={i}
              className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 flex-1 space-y-2">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-3 w-40 max-w-full" />
              </div>
              <div className="flex items-center gap-3">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-8 w-20" />
              </div>
            </li>
          ))}
        </ul>
        <span className="sr-only">Loading…</span>
      </div>
      <NfaFooter />
    </div>
  );
}
