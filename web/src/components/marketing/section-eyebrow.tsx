import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Dinaya / HyperUI section label — 3px rule + tracked caps. */
export function SectionEyebrow({
  children,
  className,
  accent = "ink",
}: {
  children: ReactNode;
  className?: string;
  /** `fired` = Signal Ice red rule (marketing interruption). */
  accent?: "ink" | "fired";
}) {
  return (
    <p
      className={cn(
        "relative mb-4 pl-3 text-xs font-semibold tracking-[0.18em] uppercase",
        accent === "fired" ? "text-[var(--fired)]" : "text-[var(--ink)]",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "absolute top-1/2 left-0 h-3 w-[3px] -translate-y-1/2 rounded-sm",
          accent === "fired" ? "bg-[var(--fired)]" : "bg-[var(--ink)]",
        )}
      />
      {children}
    </p>
  );
}
