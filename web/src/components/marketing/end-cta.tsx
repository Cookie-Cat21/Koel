import Link from "next/link";

import { FiredCtaLink } from "@/components/marketing/fired-cta";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Quiet dual-CTA band — shadcnblocks cta34 rhythm + Signal Ice fired primary. */
export function EndCta({
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
        "border-t border-border/70 pt-12 pb-4 text-center",
        className,
      )}
      aria-labelledby="end-cta-heading"
    >
      <h2
        id="end-cta-heading"
        className="font-display text-3xl font-semibold tracking-tight text-[var(--ink)] sm:text-4xl"
      >
        Ready when the market moves.
      </h2>
      <p className="mx-auto mt-4 max-w-md text-base text-muted-foreground">
        Open the dash to manage symbols and rules. Keep Telegram for the push
        when something fires — even if the tab is closed.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <FiredCtaLink href={botHref} external={botExternal}>
          {botExternal ? "Open Telegram bot" : "Get started"}
        </FiredCtaLink>
        <Button
          asChild
          variant="outline"
          size="lg"
          className="border-2 border-[var(--ink)] bg-transparent text-[var(--ink)] hover:bg-[var(--ink)] hover:text-white"
        >
          <Link href="/login">Open the dash</Link>
        </Button>
      </div>
    </section>
  );
}
