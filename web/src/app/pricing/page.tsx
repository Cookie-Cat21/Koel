import { KoelWordmark } from "@/components/brand/koel-brand";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { PricingPlans } from "@/components/marketing/pricing-plans";
import { KoelFooter } from "@/components/marketing/koel-footer";
import { NfaInline } from "@/components/nfa-inline";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "Pricing · koel",
  description: "koel CSE alerts — free via Telegram for v1. No payments yet.",
};

/** Watermelon pricing-1 adapted — Free / Later, no checkout. */
export default function PricingPage() {
  const botUrl = telegramBotUrl();

  return (
    <div className="koel-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-6 py-14"
      >
        <KoelWordmark size="lg" priority />
        <h1 className="mt-8 font-display text-4xl font-semibold tracking-tight sm:text-5xl">
          Pricing
        </h1>
        <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground">
          v1 is free while we prove Telegram-first CSE alerts. Payments are not
          wired — and not in scope until the product earns it.
        </p>
        <NfaInline className="mt-4" />

        <PricingPlans
          className="mt-12"
          plans={[
            {
              id: "free",
              title: "Free",
              description:
                "Telegram bot + thin dash for watchlist, rules, and fire history.",
              price: "LKR 0",
              features: [
                "Price / move / disclosure alerts",
                "Filing EPS / YoY when flags are on",
                "No credit card · no checkout",
              ],
              buttonText: "Open the dash",
              buttonHref: "/login",
              isPopular: true,
            },
            {
              id: "later",
              title: "Paid tiers",
              description:
                "Higher quotas, team seats, or delivery extras — only if users ask. Not available yet.",
              price: "—",
              features: [
                "No Stripe / payments in v1",
                "No fake “Pro” upsell on the dash",
                "Telegram stays the primary surface",
              ],
              buttonText: "Coming later",
              buttonDisabled: true,
            },
          ]}
        />

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
      <KoelFooter telegramHref={botUrl} />
    </div>
  );
}
