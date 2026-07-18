import { cn } from "@/lib/utils";

export type StepStatus = "pending" | "active" | "complete";

/** DaisyUI-style steps — how koel works (Ceyfi port). */
export function Steps({
  steps,
  className,
}: {
  steps: { label: string; status?: StepStatus }[];
  className?: string;
}) {
  return (
    <ol className={cn("flex w-full flex-col gap-0 sm:flex-row sm:items-start", className)}>
      {steps.map((step, index) => {
        const status = step.status ?? "pending";
        const isLast = index === steps.length - 1;
        const done = status === "complete" || status === "active";
        return (
          <li
            key={step.label}
            className="relative flex min-w-0 flex-1 flex-row items-start gap-3 pb-6 sm:flex-col sm:items-center sm:pb-0 sm:text-center"
          >
            {!isLast ? (
              <span
                aria-hidden
                className={cn(
                  "absolute left-4 top-8 h-[calc(100%-1.5rem)] w-0.5 -translate-x-1/2 sm:left-[calc(50%+1rem)] sm:top-4 sm:h-0.5 sm:w-[calc(100%-2rem)] sm:translate-y-0",
                  done ? "bg-foreground" : "bg-border",
                )}
              />
            ) : null}
            <span
              className={cn(
                "relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold",
                status === "pending" &&
                  "border-border bg-muted text-muted-foreground",
                status === "active" &&
                  "border-foreground bg-foreground text-background",
                status === "complete" &&
                  "border-foreground bg-foreground text-background",
              )}
            >
              {status === "complete" ? "✓" : String(index + 1)}
            </span>
            <span
              className={cn(
                "pt-1.5 text-xs font-medium leading-snug sm:mt-2 sm:pt-0",
                status === "pending"
                  ? "text-muted-foreground"
                  : "text-foreground",
              )}
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
