import type { LucideIcon } from "lucide-react";
import {
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
    title: "Filing EPS / YoY",
    description:
      "When metrics extract is on, alert on EPS levels or year-over-year moves from interim filings.",
    icon: Bell,
  },
];

/** HyperUI feature-list pattern — rows, not a 3-card SaaS wall. */
export function FeatureList({
  features = DEFAULT_FEATURES,
  className,
}: {
  features?: Feature[];
  className?: string;
}) {
  return (
    <ul className={cn("divide-y divide-border/70 border-y border-border/70", className)}>
      {features.map((feature) => {
        const Icon = feature.icon;
        return (
          <li key={feature.title} className="flex gap-4 py-5">
            <span
              className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md border border-border/70 bg-card/60"
              aria-hidden
            >
              <Icon className="size-4 text-foreground" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">
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
