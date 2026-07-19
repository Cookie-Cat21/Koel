"use client";

import { Minus, Plus } from "lucide-react";

import { cn } from "@/lib/utils";

export type FaqSplitItem = {
  id: string;
  question: string;
  answer: string;
};

/**
 * Watermelon faq-6 — dashed split FAQ (paper / hairline layout).
 * Native <details> for reliable open/close (Radix accordion was no-op here).
 */
export function FaqSplit({
  badge = "FAQ",
  title,
  faqs,
  className,
}: {
  badge?: string;
  title: React.ReactNode;
  faqs: FaqSplitItem[];
  className?: string;
}) {
  return (
    <section
      className={cn(
        "mx-auto w-full max-w-5xl border-y border-dashed border-border md:border-x",
        className,
      )}
      aria-labelledby="faq-split-heading"
    >
      <div className="relative grid grid-cols-1 md:grid-cols-12">
        <div className="flex flex-col justify-start border-b border-dashed border-border p-8 md:col-span-4 md:border-r md:border-b-0 md:p-10 lg:col-span-5">
          {badge ? (
            <span className="mb-4 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
              {badge}
            </span>
          ) : null}
          <h2
            id="faq-split-heading"
            className="font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl"
          >
            {title}
          </h2>
        </div>

        <div className="relative md:col-span-8 lg:col-span-7">
          <div className="w-full">
            {faqs.map((faq, index) => (
              <details
                key={faq.id}
                className="group border-b border-dashed border-border px-6 last:border-b-0 md:px-8"
              >
                <summary className="flex cursor-pointer list-none items-center py-6 marker:content-none md:py-7 [&::-webkit-details-marker]:hidden">
                  <div className="flex flex-1 items-center gap-5">
                    <span className="font-mono text-xs font-semibold tracking-widest text-muted-foreground tabular-nums">
                      Q{index + 1}
                    </span>
                    <span className="text-left text-base font-medium text-foreground md:text-lg">
                      {faq.question}
                    </span>
                  </div>
                  <div className="ml-auto flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground transition-colors group-hover:bg-muted/80">
                    <Plus className="block size-3 group-open:hidden" />
                    <Minus className="hidden size-3 group-open:block" />
                  </div>
                </summary>
                <div className="pr-12 pb-8 pl-[3.25rem]">
                  <p className="text-sm leading-relaxed text-muted-foreground md:text-base">
                    {faq.answer}
                  </p>
                </div>
              </details>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
