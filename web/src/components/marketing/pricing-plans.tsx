import Link from "next/link";
import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type PricingPlan = {
  id: string;
  title: string;
  description: string;
  price: string;
  priceSuffix?: string;
  features: string[];
  buttonText: string;
  buttonHref?: string;
  buttonDisabled?: boolean;
  isPopular?: boolean;
};

/**
 * Watermelon pricing-1 — plan cards.
 * koel: 2-tier Free / Later, no checkout, Check from lucide (not react-icons).
 */
export function PricingPlans({
  plans,
  className,
}: {
  plans: PricingPlan[];
  className?: string;
}) {
  return (
    <div className={cn("mx-auto w-full max-w-4xl", className)}>
      <div className="rounded-xl border border-border bg-muted/40 p-2 shadow-sm md:p-3">
        <div
          className={cn(
            "grid grid-cols-1 gap-2",
            plans.length >= 3 ? "lg:grid-cols-3" : "sm:grid-cols-2",
          )}
        >
          {plans.map((plan) => (
            <article
              key={plan.id}
              className={cn(
                "relative flex flex-col rounded-lg p-6 transition-colors sm:p-8",
                plan.isPopular
                  ? "border border-border bg-background shadow-sm"
                  : "bg-transparent hover:bg-background/50",
              )}
            >
              {plan.isPopular ? (
                <div className="absolute top-6 right-6">
                  <Badge className="rounded-md px-3 py-1 text-xs font-semibold">
                    Now
                  </Badge>
                </div>
              ) : null}

              <div className="mb-6">
                <h3 className="font-display text-2xl font-semibold tracking-tight text-foreground">
                  {plan.title}
                </h3>
                <p className="mt-2 min-h-[40px] pr-8 text-sm text-muted-foreground">
                  {plan.description}
                </p>
              </div>

              <div className="mb-6 flex items-baseline gap-2">
                <span className="font-display text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
                  {plan.price}
                </span>
                {plan.priceSuffix ? (
                  <span className="text-sm font-medium text-muted-foreground">
                    {plan.priceSuffix}
                  </span>
                ) : null}
              </div>

              <div className="mb-8 h-px bg-border" />

              <ul className="mb-8 flex flex-1 flex-col gap-3">
                {plan.features.map((feature) => (
                  <li
                    key={feature}
                    className="flex items-start gap-2 text-sm text-foreground"
                  >
                    <Check
                      className="mt-0.5 size-4 shrink-0 text-foreground"
                      aria-hidden
                    />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              {plan.buttonDisabled || !plan.buttonHref ? (
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  className="w-full"
                  disabled
                >
                  {plan.buttonText}
                </Button>
              ) : (
                <Button asChild size="lg" className="w-full">
                  <Link href={plan.buttonHref}>{plan.buttonText}</Link>
                </Button>
              )}
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
