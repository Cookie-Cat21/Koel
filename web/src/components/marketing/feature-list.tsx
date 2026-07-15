import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bell,
  FileText,
  Percent,
  TrendingUp,
} from "lucide-react";

import { cn } from "@/lib/utils";

type Feature = {
  title: string;
  description: string;
  icon: LucideIcon;
};

const DEFAULT_FEATURES: Feature[] = [
  {
    title: "Price above / below",
    description:
      "Set a threshold on a watched symbol. When the poller sees a cross, Telegram gets the ping.",
    icon: TrendingUp,
  },
  {
    title: "Daily % move",
    description:
      "Catch sharp up or down sessions without staring at the board all day.",
    icon: Percent,
  },
  {
    title: "New disclosures",
    description:
      "Company announcements for symbols you watch — with a link back to the source filing.",
    icon: FileText,
  },
  {
    title: "Activity signals",
    description:
      "Unusual volume or board activity on watched names — a nudge when the tape gets loud.",
    icon: Activity,
  },
  {
    title: "Filing EPS / YoY",
    description:
      "When metrics extract is on, alert on EPS levels or year-over-year moves from interim filings.",
    icon: Bell,
  },
];

/**
 * HyperUI “List with content” — rows, not a 3-card SaaS wall.
 * Optional split: sticky heading column on large screens (via page layout).
 */
export function FeatureList({
  features = DEFAULT_FEATURES,
  className,
}: {
  features?: Feature[];
  className?: string;
}) {
  return (
    <ul className={cn("space-y-0 divide-y divide-border/70 border-y border-border/70", className)}>
      {features.map((feature) => {
        const Icon = feature.icon;
        return (
          <li
            key={feature.title}
            className="group flex gap-4 py-5 motion-safe:transition-colors motion-safe:hover:bg-foreground/[0.03]"
          >
            <span
              className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-md border border-border/80 bg-white motion-safe:transition-transform motion-safe:group-hover:scale-105"
              aria-hidden
            >
              <Icon className="size-4 text-[var(--ink)]" />
            </span>
            <div className="min-w-0">
              <p className="font-display text-base font-semibold tracking-tight text-[var(--ink)]">
                {feature.title}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
