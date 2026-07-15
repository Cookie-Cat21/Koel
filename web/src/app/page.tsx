import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ChimeWordmark } from "@/components/brand/chime-brand";
import { FaqSection } from "@/components/kit/faq-section";
import { Steps } from "@/components/kit/steps";
import { AnnouncementBar } from "@/components/marketing/announcement-bar";
import { EndCta } from "@/components/marketing/end-cta";
import { FeatureList } from "@/components/marketing/feature-list";
import { FiredCtaLink } from "@/components/marketing/fired-cta";
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
  title: "Chime — CSE moves. You hear it.",
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
 * Signal Ice landing — interruption identity (blood red), Telegram proof.
 * Kit steals: Cult split structure, HyperUI list/CTA, Daisy chat — no shaders.
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
  const primaryHref = botUrl ?? "/login";

  return (
    <div className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <AnnouncementBar />
      <MarketingNav />
      <main id="main-content" tabIndex={-1} className="flex flex-1 flex-col">
        {/* Cult split hero — brand one-liner + fired CTA + proof */}
        <section className="mx-auto grid w-full max-w-5xl gap-10 px-6 py-14 sm:py-16 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:items-center lg:gap-14 lg:py-24">
          <div>
            <div className="chime-rise">
              <ChimeWordmark size="hero" priority />
            </div>
            <h1 className="chime-rise chime-rise-delay-1 mt-8 max-w-xl font-display text-4xl font-semibold tracking-tight text-[var(--ink)] sm:text-5xl sm:leading-[1.05] lg:text-6xl">
              CSE moves. You hear it.
            </h1>
            <p className="chime-rise chime-rise-delay-2 mt-5 max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg">
              Telegram-first CSE alerts. Set price, move, and disclosure rules
              in a thin dash — get pinged the moment something fires, even with
              the tab closed.
            </p>
            <NfaInline className="chime-rise chime-rise-delay-2 mt-4" />
            <div className="chime-rise chime-rise-delay-3 mt-10 flex flex-wrap items-center gap-3">
              <FiredCtaLink href={primaryHref} external={Boolean(botUrl)}>
                {botUrl ? "Open Telegram bot" : "Get started"}
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
          </div>

          <div className="chime-rise chime-rise-delay-3">
            <SectionEyebrow accent="fired" className="lg:mb-5">
              The cherry — Telegram
            </SectionEyebrow>
            <TelegramProof />
          </div>
        </section>

        <section
          id="how-it-works"
          className="scroll-mt-36 border-y border-border/60 bg-[var(--ink)]/[0.03]"
        >
          <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
            <SectionEyebrow accent="fired">How it works</SectionEyebrow>
            <h2 className="max-w-xl font-display text-3xl font-semibold tracking-tight text-[var(--ink)] sm:text-4xl">
              Set it once. Get pinged when it matters.
            </h2>
            <p className="mt-3 max-w-lg text-base text-muted-foreground">
              Three moves. No portfolio tracker. No terminal to keep open.
            </p>
            <div className="mt-10">
              <Steps
                steps={[
                  { label: "Browse & watch CSE symbols", status: "complete" },
                  { label: "Set rules in the dash", status: "complete" },
                  { label: "Telegram pings on fire", status: "active" },
                ]}
              />
            </div>
          </div>
        </section>

        {/* HyperUI list-with-content: heading column + rows */}
        <section
          className="mx-auto grid w-full max-w-5xl gap-10 px-6 py-16 sm:py-20 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-14"
          aria-labelledby="alerts-heading"
        >
          <div className="lg:sticky lg:top-28 lg:self-start">
            <SectionEyebrow accent="fired">Alerts</SectionEyebrow>
            <h2
              id="alerts-heading"
              className="font-display text-3xl font-semibold tracking-tight text-[var(--ink)] sm:text-4xl"
            >
              What you can watch for
            </h2>
            <p className="mt-3 max-w-sm text-base text-muted-foreground">
              Public CSE data only. Not a screener, not a trading terminal —
              just the conditions you care about.
            </p>
          </div>
          <FeatureList />
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 pb-4">
          <MidCta telegramHref={botUrl} />
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-16 sm:py-20">
          <FaqSection
            eyebrow="FAQ"
            heading="Before you start"
            description="Short answers. The dash is daily; Telegram is the push cherry."
            items={FAQ}
          />
          <EndCta telegramHref={botUrl} className="mt-16" />
        </section>
      </main>
      <SiteFooter telegramHref={botUrl} />
    </div>
  );
}
