import Link from "next/link";

import { FiredCtaLink } from "@/components/marketing/fired-cta";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * HyperUI CTA rhythm — ink block + fired primary.
 * No logo cloud / device frame.
 */
export function MidCta({
  telegramHref,
  className,
}: {
  telegramHref: string | null;
  className?: string;
}) {
  const botHref = telegramHref ?? "/login";
  const botExternal = Boolean(telegramHref);

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-xl bg-[var(--ink)] px-6 py-8 text-white sm:px-10 sm:py-12",
        className,
      )}
      aria-labelledby="mid-cta-heading"
    >
      <div
        aria-hidden
        className="absolute top-0 left-0 h-full w-1.5 bg-[var(--fired)]"
      />
      <div className="relative flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-md pl-2">
          <p className="text-xs font-semibold tracking-[0.18em] text-white/55 uppercase">
            Primary surface
          </p>
          <h2
            id="mid-cta-heading"
            className="mt-3 font-display text-2xl font-semibold tracking-tight sm:text-3xl"
          >
            Alerts fire on Telegram.
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-white/70 sm:text-base">
            The dash is for watchlist and rules. When something crosses, you get
            the ping — even if this tab is closed.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-3 pl-2 sm:pl-0">
          <FiredCtaLink href={botHref} external={botExternal}>
            {botExternal ? "Open Telegram bot" : "Get started"}
          </FiredCtaLink>
          <Button
            asChild
            size="lg"
            variant="outline"
            className="border-white/35 bg-transparent text-white hover:bg-white/10 hover:text-white"
          >
            <Link href="/login">Open the dash</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
