import Link from "next/link";

import { ChimeWordmark } from "@/components/brand/chime-brand";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { SiteFooter } from "@/components/marketing/site-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "Pricing · Chime",
  description: "Chime CSE alerts — free via Telegram for v1. No payments yet.",
};

/** HyperUI 2-tier stub — no checkout (payments fence). */
export default function PricingPage() {
  const botUrl = telegramBotUrl();

  return (
    <div className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 py-14"
      >
        <ChimeWordmark size="lg" priority />
        <h1 className="mt-8 font-display text-4xl font-semibold tracking-tight sm:text-5xl">
          Pricing
        </h1>
        <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground">
          v1 is free while we prove Telegram-first CSE alerts. Payments are not
          wired — and not in scope until the product earns it.
        </p>
        <NfaInline className="mt-4" />

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          <article className="rounded-lg border border-foreground bg-card/70 p-6">
            <p className="text-xs font-semibold tracking-[0.18em] text-primary uppercase">
              Now
            </p>
            <h2 className="mt-2 font-display text-2xl font-semibold">Free</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Telegram bot + thin dash for watchlist, rules, and fire history.
            </p>
            <ul className="mt-6 space-y-2 text-sm text-foreground">
              <li>Price / move / disclosure alerts</li>
              <li>Filing EPS / YoY when flags are on</li>
              <li>No credit card · no checkout</li>
            </ul>
            <Button asChild className="mt-8 w-full" size="lg">
              <Link href="/login">Open the dash</Link>
            </Button>
          </article>

          <article className="rounded-lg border border-border/70 bg-card/40 p-6">
            <p className="text-xs font-semibold tracking-[0.18em] text-muted-foreground uppercase">
              Later
            </p>
            <h2 className="mt-2 font-display text-2xl font-semibold text-muted-foreground">
              Paid tiers
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Higher quotas, team seats, or delivery extras — only if users ask.
              Not available yet.
            </p>
            <ul className="mt-6 space-y-2 text-sm text-muted-foreground">
              <li>No Stripe / payments in v1</li>
              <li>No fake “Pro” upsell on the dash</li>
              <li>Telegram stays the primary surface</li>
            </ul>
            <Button
              type="button"
              variant="outline"
              className="mt-8 w-full"
              size="lg"
              disabled
            >
              Coming later
            </Button>
          </article>
        </div>

        {botUrl ? (
          <p className="mt-10 text-center text-sm text-muted-foreground">
            Prefer chat?{" "}
            <a
              href={botUrl}
              className="underline underline-offset-4"
              target="_blank"
              rel="noopener noreferrer"
            >
              Open the Telegram bot
            </a>
            .
          </p>
        ) : null}
      </main>
      <SiteFooter telegramHref={botUrl} />
    </div>
  );
}
