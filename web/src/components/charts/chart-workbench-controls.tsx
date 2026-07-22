"use client";

import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * HyperUI / shadcn-inspired workbench chrome for the koel chart dialog.
 * Fence: in-tree only — no DaisyUI, Tremor charts, React Bits, or marketplace dumps.
 */

export function ChartSegmentGroup({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg border border-border/60 bg-muted/60 p-0.5",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function ChartSegmentButton({
  pressed,
  onClick,
  children,
  title,
  className,
}: {
  pressed: boolean;
  onClick: () => void;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      title={title}
      className={cn(
        "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
        pressed
          ? "bg-background font-semibold text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground",
        className,
      )}
    >
      {children}
    </button>
  );
}

export type OverlayTone = "amber" | "violet" | "emerald" | "sky" | "neutral";

const TONE: Record<
  OverlayTone,
  { on: string; dot: string }
> = {
  amber: {
    on: "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100",
    dot: "bg-amber-500",
  },
  violet: {
    on: "border-violet-500/40 bg-violet-500/10 text-violet-900 dark:text-violet-100",
    dot: "bg-violet-500",
  },
  emerald: {
    on: "border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100",
    dot: "bg-emerald-500",
  },
  sky: {
    on: "border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-200",
    dot: "bg-sky-500",
  },
  neutral: {
    on: "border-foreground/30 bg-foreground/5 text-foreground",
    dot: "bg-foreground/70",
  },
};

/** Colored toggle chip with legend dot (HyperUI filter-chip density). */
export function ChartToggleChip({
  pressed,
  onClick,
  children,
  title,
  tone = "neutral",
  count,
  disabled,
  id,
}: {
  pressed: boolean;
  onClick: () => void;
  children: ReactNode;
  title?: string;
  tone?: OverlayTone;
  count?: number;
  disabled?: boolean;
  id?: string;
}) {
  const t = TONE[tone];
  return (
    <button
      type="button"
      id={id}
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-45",
        pressed
          ? t.on
          : "border-border text-muted-foreground hover:text-foreground",
      )}
    >
      <span
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          pressed ? t.dot : "bg-muted-foreground/40",
        )}
        aria-hidden
      />
      {children}
      {typeof count === "number" && count > 0 ? (
        <Badge variant="secondary" className="h-4 min-w-4 px-1 font-mono text-[10px]">
          {count}
        </Badge>
      ) : null}
    </button>
  );
}

/** Active session summary — HyperUI-style filter chips under the toolbar. */
export function ChartActiveStrip({
  chips,
}: {
  chips: { key: string; label: string; tone?: OverlayTone }[];
}) {
  if (chips.length === 0) return null;
  return (
    <div
      className="flex flex-wrap items-center gap-1.5 px-5 pb-2"
      aria-label="Active chart layers"
    >
      <span className="text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
        Active
      </span>
      {chips.map((c) => {
        const t = TONE[c.tone ?? "neutral"];
        return (
          <span
            key={c.key}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
              t.on,
            )}
          >
            <span className={cn("size-1.5 rounded-full", t.dot)} aria-hidden />
            {c.label}
          </span>
        );
      })}
    </div>
  );
}

export function ChartShortcutsHint() {
  return (
    <p className="hidden text-[10px] text-muted-foreground sm:block">
      Keys:{" "}
      <kbd className="rounded border border-border/70 bg-muted/50 px-1 font-mono">
        1–5
      </kbd>{" "}
      range ·{" "}
      <kbd className="rounded border border-border/70 bg-muted/50 px-1 font-mono">
        D
      </kbd>{" "}
      disclosures ·{" "}
      <kbd className="rounded border border-border/70 bg-muted/50 px-1 font-mono">
        F
      </kbd>{" "}
      fires ·{" "}
      <kbd className="rounded border border-border/70 bg-muted/50 px-1 font-mono">
        A
      </kbd>{" "}
      alerts ·{" "}
      <kbd className="rounded border border-border/70 bg-muted/50 px-1 font-mono">
        Esc
      </kbd>{" "}
      close
    </p>
  );
}
