import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * End-of-page dual CTA — Watermelon cta-1 structure, quiet close.
 * No glow blobs; keep NFA-adjacent framing light.
 */
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
      className={cn("border-t border-border/70 pt-12 pb-4", className)}
      aria-labelledby="end-cta-heading"
    >
      <div className="relative isolate flex flex-col items-center gap-8 overflow-hidden rounded-xl border border-border bg-muted/40 px-8 py-10 text-center shadow-sm md:px-12 md:py-14">
        <div className="max-w-md">
          <h2
            id="end-cta-heading"
            className="font-display text-2xl font-semibold tracking-tight text-foreground sm:text-3xl"
          >
            Ready when the market moves.
          </h2>
          <p className="mx-auto mt-4 text-base text-muted-foreground">
            Open the dash to manage symbols and rules. Keep Telegram for the push
            when something fires — even if the tab is closed.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button
            asChild
            size="lg"
            className="motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
          >
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
      </div>
    </section>
  );
}
