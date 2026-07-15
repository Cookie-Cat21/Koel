import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

export type FaqItem = { question: string; answer: string };

/** HyperUI FAQ pattern — native details + lucide chevron. */
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
    <section className={cn("w-full", className)}>
      <p className="relative mb-2 pl-3 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
        <span
          aria-hidden
          className="absolute top-1/2 left-0 h-3 w-[3px] -translate-y-1/2 rounded-sm bg-primary"
        />
        {eyebrow}
      </p>
      <h2 className="font-display text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
        {heading}
      </h2>
      {description ? (
        <p className="mt-3 max-w-xl text-base text-muted-foreground">
          {description}
        </p>
      ) : null}
      <div className="mt-6 divide-y divide-border/80 border-y border-border/80">
        {items.map((item) => (
          <details key={item.question} className="group">
            <summary className="cursor-pointer list-none py-4 text-sm font-semibold text-foreground marker:content-none focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 [&::-webkit-details-marker]:hidden">
              <span className="flex items-center justify-between gap-3">
                {item.question}
                <ChevronDown
                  aria-hidden
                  className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                />
              </span>
            </summary>
            <p className="pb-4 text-sm leading-relaxed text-muted-foreground">
              {item.answer}
            </p>
          </details>
        ))}
      </div>
    </section>
  );
}
