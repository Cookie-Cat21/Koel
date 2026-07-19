"use client";

import { Minus, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type FaqItem = { question: string; answer: string };

/**
 * Watermelon faq-3 — numbered FAQ rows.
 * Native <details> for reliable expand (visual port of faq-3).
 */
export function FaqSection({
  items,
  eyebrow = "FAQ",
  heading = "Questions",
  description,
  className,
}: {
  items: FaqItem[];
  eyebrow?: string;
  heading?: string;
  description?: string;
  className?: string;
}) {
  return (
    <section className={cn("w-full", className)} aria-labelledby="faq-heading">
      <div className="mb-10 flex w-full max-w-xl flex-col sm:mb-12">
        <Badge
          variant="outline"
          className="mb-4 w-fit gap-1.5 rounded-full border-border bg-background px-3 py-1 text-xs font-medium tracking-wide text-muted-foreground"
        >
          <span className="inline-block size-1.5 rounded-full bg-foreground" />
          {eyebrow}
        </Badge>
        <h2
          id="faq-heading"
          className="font-display text-2xl font-semibold tracking-tight text-foreground sm:text-3xl"
        >
          {heading}
        </h2>
        {description ? (
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted-foreground sm:text-base">
            {description}
          </p>
        ) : null}
      </div>

      <div className="flex w-full flex-col gap-2">
        {items.map((item, i) => {
          const num = String(i + 1).padStart(2, "0");
          return (
            <details
              key={item.question}
              className="group overflow-hidden border border-border bg-muted/30 transition-colors hover:bg-muted/50 open:bg-muted/60"
            >
              <summary className="flex cursor-pointer list-none items-center gap-4 px-5 py-4 marker:content-none sm:px-6 sm:py-5 [&::-webkit-details-marker]:hidden">
                <span className="w-8 shrink-0 text-center font-mono text-xs font-semibold tracking-widest text-muted-foreground/60 tabular-nums">
                  {num}
                </span>
                <span className="flex-1 text-left text-sm font-medium leading-snug text-foreground sm:text-base">
                  {item.question}
                </span>
                <span className="flex size-7 shrink-0 items-center justify-center text-muted-foreground">
                  <Plus className="block size-3.5 group-open:hidden" />
                  <Minus className="hidden size-3.5 group-open:inline" />
                </span>
              </summary>
              <div className="px-5 pb-5 pl-[4.25rem] sm:px-6 sm:pb-6">
                <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
                  {item.answer}
                </p>
              </div>
            </details>
          );
        })}
      </div>
    </section>
  );
}
