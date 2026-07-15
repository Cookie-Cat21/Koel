import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ChimeWordmark } from "@/components/brand/chime-brand";
import { ChatBubble } from "@/components/kit/chat-bubble";
import { FaqSection } from "@/components/kit/faq-section";
import { Steps } from "@/components/kit/steps";
import { AnnouncementBar } from "@/components/marketing/announcement-bar";
import { EndCta } from "@/components/marketing/end-cta";
import { FeatureList } from "@/components/marketing/feature-list";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { SiteFooter } from "@/components/marketing/site-footer";
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
 * Brand landing — dash is the cake; Telegram push is the cherry.
 * Signed-in users land on Overview.
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
      <AnnouncementBar />
      <MarketingNav />
      <main id="main-content" tabIndex={-1} className="flex flex-1 flex-col">
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 py-14 sm:py-20">
          {/* Hero — brand first; keep first viewport lean */}
          <div className="chime-rise">
            <ChimeWordmark size="hero" priority />
          </div>
          <h1 className="chime-rise chime-rise-delay-1 mt-8 max-w-xl font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl sm:leading-[1.15]">
            CSE alerts on Telegram. Dash when you need to manage.
          </h1>
          <p className="chime-rise chime-rise-delay-2 mt-5 max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg">
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

          {/* Product proof */}
          <section className="chime-rise chime-rise-delay-3 mt-16">
            <p className="relative mb-4 pl-3 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              <span
                aria-hidden
                className="absolute top-1/2 left-0 h-3 w-[3px] -translate-y-1/2 rounded-sm bg-primary"
              />
              The cherry — Telegram
            </p>
            <ChatBubble header="Chime CSE" footer="Not financial advice">
              <p className="font-medium">JKH.N0000 crossed above</p>
              <p className="mt-1 font-mono text-2xl font-semibold tabular-nums">
                22.50
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                Last 22.75 · rule #184
              </p>
            </ChatBubble>
          </section>

          {/* How it works */}
          <section id="how-it-works" className="mt-16 scroll-mt-36">
            <p className="relative mb-4 pl-3 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              <span
                aria-hidden
                className="absolute top-1/2 left-0 h-3 w-[3px] -translate-y-1/2 rounded-sm bg-primary"
              />
              How it works
            </p>
            <h2 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">
              Set it once. Get pinged when it matters.
            </h2>
            <div className="mt-8">
              <Steps
                steps={[
                  { label: "Browse & watch CSE symbols", status: "complete" },
                  { label: "Set rules in the dash", status: "complete" },
                  { label: "Telegram pings on fire", status: "active" },
                ]}
              />
            </div>
          </section>

          {/* What you can alert on */}
          <section className="mt-16" aria-labelledby="alerts-heading">
            <p className="relative mb-4 pl-3 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              <span
                aria-hidden
                className="absolute top-1/2 left-0 h-3 w-[3px] -translate-y-1/2 rounded-sm bg-primary"
              />
              Alerts
            </p>
            <h2
              id="alerts-heading"
              className="font-display text-2xl font-semibold tracking-tight sm:text-3xl"
            >
              What you can watch for
            </h2>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              Public CSE data only. Not a screener, not a trading terminal —
              just the conditions you care about.
            </p>
            <FeatureList className="mt-8" />
          </section>

          <FaqSection
            className="mt-16"
            eyebrow="FAQ"
            heading="Before you start"
            description="Short answers. The dash is daily; Telegram is the push cherry."
            items={FAQ}
          />

          <EndCta telegramHref={botUrl} className="mt-16" />
        </div>
      </main>
      <SiteFooter telegramHref={botUrl} />
    </div>
  );
}
