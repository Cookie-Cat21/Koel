import { cn } from "@/lib/utils";

export type FaqItem = { question: string; answer: string };

/** HyperUI FAQ pattern — native details (no extra accordion dep). */
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
      <h2 className="font-display text-2xl font-semibold tracking-tight text-foreground">
        {heading}
      </h2>
      {description ? (
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">{description}</p>
      ) : null}
      <div className="mt-6 divide-y divide-border rounded-xl border border-border bg-card">
        {items.map((item) => (
          <details key={item.question} className="group px-4 sm:px-5">
            <summary className="cursor-pointer list-none py-4 text-sm font-semibold text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
              <span className="flex items-center justify-between gap-3">
                {item.question}
                <span
                  aria-hidden
                  className="text-muted-foreground transition-transform group-open:rotate-180"
                >
                  ▾
                </span>
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
