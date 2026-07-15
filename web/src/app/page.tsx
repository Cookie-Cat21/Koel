import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ChimeWordmark } from "@/components/brand/chime-brand";
import { FaqSection } from "@/components/kit/faq-section";
import { EndCta } from "@/components/marketing/end-cta";
import { FeatureList } from "@/components/marketing/feature-list";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MidCta } from "@/components/marketing/mid-cta";
import { SectionEyebrow } from "@/components/marketing/section-eyebrow";
import { SiteFooter } from "@/components/marketing/site-footer";
import { TelegramProof } from "@/components/marketing/telegram-proof";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import { getDashAuthConfig, SESSION_COOKIE } from "@/lib/auth/config";
import { verifySessionToken } from "@/lib/auth/session";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "Chime — CSE alerts on Telegram",
  description:
    "Telegram-first Colombo Stock Exchange alerts. Watch symbols, set rules in a thin dash, get pinged when something fires.",
};

const FAQ = [
  {
    question: "Is Chime a CSE Tracker Pro clone?",
    answer:
      "No. Chime is Telegram-first CSE alerting with a thin management dash. Portfolio, tax, screener, and heavy TA stay out of scope.",
  },
  {
    question: "Where do alerts fire?",
    answer:
      "On Telegram. Manage symbols and rules in the dash; when a rule matches, you get the ping even if the browser is closed.",
  },
  {
    question: "Is this financial advice?",
    answer:
      "No. Prices and disclosures are informational only. Always verify filings and make your own decisions.",
  },
  {
    question: "What can I alert on?",
    answer:
      "Price above/below, daily % move, disclosures, activity signals, and (when enabled) EPS / YoY filing metrics.",
  },
  {
    question: "Do I need to keep the dash open?",
    answer:
      "No. The dash is for setup and review. Push delivery is the point — Telegram carries the alert.",
  },
];

/**
 * Option A — wide left-rail hero + below-fold full-width proof band.
 * No announcement bar, no in-hero side proof panel.
 */
export default async function HomePage() {
  const cfg = getDashAuthConfig();
  const jar = await cookies();
  const raw = jar.get(SESSION_COOKIE)?.value;
  const session =
    raw && cfg.sessionSecret
      ? verifySessionToken(raw, cfg.sessionSecret)
      : null;

  if (session) {
    redirect("/overview");
  }

  const botUrl = telegramBotUrl();

  return (
    <div className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main id="main-content" tabIndex={-1} className="flex flex-1 flex-col">
        {/* Hero — fills first viewport; proof stays below the fold */}
        <section className="mx-auto flex min-h-[calc(100svh-3.5rem)] w-full max-w-5xl flex-col justify-center px-6 py-16 sm:py-20">
          <div className="max-w-xl lg:max-w-2xl">
            <div className="chime-rise">
              <ChimeWordmark size="hero" priority />
            </div>
            <h1 className="chime-rise chime-rise-delay-1 mt-10 font-display text-4xl font-semibold tracking-tight text-foreground sm:text-5xl sm:leading-[1.08]">
              CSE alerts on Telegram.
              <span className="mt-2 block text-muted-foreground">
                Dash when you need to manage.
              </span>
            </h1>
            <p className="chime-rise chime-rise-delay-2 mt-6 max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg">
              Watch symbols, set price / move / disclosure rules, and get pinged
              the moment something fires — even with the tab closed.
            </p>
            <NfaInline className="chime-rise chime-rise-delay-2 mt-4" />
            <div className="chime-rise chime-rise-delay-3 mt-10 flex flex-wrap items-center gap-3">
              <Button
                asChild
                size="lg"
                className="min-w-36 motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
              >
                {botUrl ? (
                  <a href={botUrl} target="_blank" rel="noopener noreferrer">
                    Open Telegram bot
                  </a>
                ) : (
                  <Link href="/login">Get started</Link>
                )}
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link href="/login">Open the dash</Link>
              </Button>
            </div>
          </div>
        </section>

        {/* Proof — phone hard-cut flush with the band’s bottom colour edge */}
        <section
          aria-labelledby="proof-heading"
          className="overflow-hidden border-y border-border/70 bg-foreground/[0.03]"
        >
          <div className="mx-auto grid w-full max-w-5xl lg:grid-cols-12 lg:items-stretch lg:gap-12">
            <div className="px-6 py-14 sm:py-16 lg:col-span-5">
              <SectionEyebrow>The cherry — Telegram</SectionEyebrow>
              <h2
                id="proof-heading"
                className="font-display text-2xl font-semibold tracking-tight sm:text-3xl"
              >
                The ping is the product.
              </h2>
              <p className="mt-4 max-w-sm text-base leading-relaxed text-muted-foreground">
                Rules live in a thin dash. Delivery is Telegram — so you hear
                the cross without keeping a browser tab open.
              </p>
            </div>

            {/* Clip box: height = left column on lg; phone hangs past and is cut */}
            <div className="relative h-[290px] overflow-hidden sm:h-[320px] lg:col-span-7 lg:h-full lg:min-h-0">
              <div className="absolute top-5 left-1/2 -translate-x-1/2 lg:top-8 lg:right-4 lg:left-auto lg:translate-x-0">
                <TelegramProof />
              </div>
            </div>
          </div>
        </section>

        <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-16 sm:py-20">
          <HowItWorks />

          <section className="mt-20" aria-labelledby="alerts-heading">
            <SectionEyebrow>Alerts</SectionEyebrow>
            <h2
              id="alerts-heading"
              className="max-w-xl font-display text-2xl font-semibold tracking-tight sm:text-3xl"
            >
              What you can watch for
            </h2>
            <p className="mt-3 max-w-xl text-base text-muted-foreground">
              Public CSE data only. Not a screener, not a trading terminal —
              just the conditions you care about.
            </p>
            <FeatureList className="mt-10" />
          </section>

          <MidCta telegramHref={botUrl} className="mt-20" />

          <FaqSection
            className="mt-20"
            eyebrow="FAQ"
            heading="Before you start"
            description="Short answers. The dash is daily; Telegram is the push cherry."
            items={FAQ}
          />

          <EndCta telegramHref={botUrl} className="mt-20" />
        </div>
      </main>
      <SiteFooter telegramHref={botUrl} />
    </div>
  );
}
