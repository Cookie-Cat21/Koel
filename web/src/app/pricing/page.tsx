import Link from "next/link";

import { QuiverlyWordmark } from "@/components/brand/quiverly-brand";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { QuiverlyFooter } from "@/components/marketing/quiverly-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "Pricing · Quiverly",
  description:
    "Quiverly CSE alerts — Free via Telegram, Pro capacity (bank transfer), optional Brief. Not financial advice.",
};

const PRO_WAITLIST_MAILTO =
  "mailto:hello@quiverly.app?subject=Quiverly%20Pro%20%E2%80%94%20bank%20transfer%20waitlist";

/** Phase B tiers — Free / Pro / optional Brief. No PayHere checkout yet. */
export default function PricingPage() {
  const botUrl = telegramBotUrl();
  const freeCtaHref = botUrl ?? "/login";
  const freeCtaExternal = Boolean(botUrl);

  return (
    <div className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-14"
      >
        <QuiverlyWordmark size="lg" priority />
        <h1 className="mt-8 font-display text-4xl font-semibold tracking-tight sm:text-5xl">
          Pricing
        </h1>
        <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground">
          Start free on Telegram. Pro raises watch and alert capacity when you
          outgrow the free caps — paid via bank transfer for now (no card
          checkout).
        </p>
        <NfaInline className="mt-4" />

        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          <article className="rounded-lg border border-foreground bg-card/70 p-6">
            <p className="text-xs font-semibold tracking-[0.18em] text-primary uppercase">
              Free
            </p>
            <h2 className="mt-2 font-display text-2xl font-semibold">Free</h2>
            <p className="mt-1 font-mono text-lg tabular-nums">Rs 0</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Telegram-first CSE alerts plus the thin dash to manage rules.
            </p>
            <ul className="mt-6 space-y-2 text-sm text-foreground">
              <li>~5 watches · ~3 active rules</li>
              <li>Price / move / disclosure alerts</li>
              <li>Standard delivery · short fire history</li>
            </ul>
            <Button asChild className="mt-8 w-full" size="lg">
              {freeCtaExternal ? (
                <a href={freeCtaHref} target="_blank" rel="noopener noreferrer">
                  Open Telegram bot
                </a>
              ) : (
                <Link href={freeCtaHref}>Open the dash</Link>
              )}
            </Button>
          </article>

          <article className="rounded-lg border border-border/70 bg-card/70 p-6">
            <p className="text-xs font-semibold tracking-[0.18em] text-muted-foreground uppercase">
              Pro
            </p>
            <h2 className="mt-2 font-display text-2xl font-semibold">Pro</h2>
            <p className="mt-1 font-mono text-lg tabular-nums">
              Rs 490<span className="text-sm font-sans">/mo</span>
            </p>
            <p className="text-sm text-muted-foreground">
              or Rs 4,900/yr
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Higher caps, quiet hours / digest, and longer history — never
              “better tips.”
            </p>
            <ul className="mt-6 space-y-2 text-sm text-foreground">
              <li>Higher watch + alert quotas</li>
              <li>Priority queue · 90d fire history</li>
              <li>Quiet hours &amp; digest controls</li>
            </ul>
            <Button asChild className="mt-8 w-full" size="lg" variant="outline">
              <Link href="/pricing/bank-transfer">
                Pay by bank transfer
              </Link>
            </Button>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Manual transfer + admin activate.{" "}
              <a href={PRO_WAITLIST_MAILTO} className="underline underline-offset-2">
                Or email waitlist
              </a>
              . No PayHere yet.
            </p>
          </article>

          <article className="rounded-lg border border-border/70 bg-card/40 p-6">
            <p className="text-xs font-semibold tracking-[0.18em] text-muted-foreground uppercase">
              Optional
            </p>
            <h2 className="mt-2 font-display text-2xl font-semibold">Brief</h2>
            <p className="mt-1 font-mono text-lg tabular-nums">
              Rs 1,490<span className="text-sm font-sans">/mo</span>
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Metered AI disclosure briefs on top of Free or Pro. Always NFA.
            </p>
            <ul className="mt-6 space-y-2 text-sm text-muted-foreground">
              <li>Filing summaries when flags + key are on</li>
              <li>Same Postgres truth as the dash</li>
              <li>Not investment advice</li>
            </ul>
            <Button asChild className="mt-8 w-full" size="lg" variant="outline">
              <a href={PRO_WAITLIST_MAILTO}>
                Coming soon — waitlist
              </a>
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
        ) : (
          <p className="mt-10 text-center text-sm text-muted-foreground">
            Prefer the dash?{" "}
            <Link href="/login" className="underline underline-offset-4">
              Sign in
            </Link>
            .
          </p>
        )}
      </main>
      <QuiverlyFooter telegramHref={botUrl} />
    </div>
  );
}
