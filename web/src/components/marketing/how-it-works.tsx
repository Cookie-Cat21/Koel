import { cn } from "@/lib/utils";

import { SectionEyebrow } from "@/components/marketing/section-eyebrow";

const STEPS = [
  {
    n: "01",
    title: "Watch CSE symbols",
    body: "Add the names you care about. koel only polls what you watch.",
  },
  {
    n: "02",
    title: "Set rules in the dash",
    body: "Price above/below, daily % move, disclosures, activity — thin setup, not a terminal.",
  },
  {
    n: "03",
    title: "Get the Telegram ping",
    body: "When a rule fires, the bot messages you — even if this tab is closed.",
  },
] as const;

/** HyperUI empty-state rhythm — numbered steps, not a progress tracker. */
export function HowItWorks({ className }: { className?: string }) {
  return (
    <section
      id="how-it-works"
      className={cn("scroll-mt-28", className)}
      aria-labelledby="how-it-works-heading"
    >
      <SectionEyebrow>How it works</SectionEyebrow>
      <h2
        id="how-it-works-heading"
        className="max-w-xl font-display text-2xl font-semibold tracking-tight sm:text-3xl"
      >
        Set it once. Get pinged when it matters.
      </h2>
      <p className="mt-3 max-w-lg text-base text-muted-foreground">
        Three steps. Telegram is the delivery surface; the dash is just where you
        manage the rules.
      </p>

      <ol className="mt-10 grid gap-0 border-t border-border/70 sm:grid-cols-3">
        {STEPS.map((step, index) => (
          <li
            key={step.n}
            className={cn(
              "relative flex flex-col border-border/70 py-8 sm:px-6 sm:py-10",
              index > 0 && "border-t sm:border-t-0 sm:border-l",
              index === 0 && "sm:pl-0",
              index === STEPS.length - 1 && "sm:pr-0",
            )}
          >
            <span className="font-mono text-xs font-semibold tracking-[0.2em] text-muted-foreground tabular-nums">
              {step.n}
            </span>
            <h3 className="mt-4 font-display text-lg font-semibold tracking-tight text-foreground">
              {step.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              {step.body}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
