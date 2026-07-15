import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Quiet dual-CTA band — shadcnblocks cta34 rhythm, Chime tokens. */
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
        className="font-display text-2xl font-semibold tracking-tight text-foreground"
      >
        Ready when the market moves.
      </h2>
      <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground">
        Open the dash to manage symbols and rules. Keep Telegram for the push
        when something fires — even if the tab is closed.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button asChild size="lg">
          {botExternal ? (
            <a href={botHref} target="_blank" rel="noopener noreferrer">
              Open Telegram bot
            </a>
          ) : (
            <Link href={botHref}>Get started</Link>
          )}
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link href="/login">Open the dash</Link>
        </Button>
      </div>
    </section>
  );
}
