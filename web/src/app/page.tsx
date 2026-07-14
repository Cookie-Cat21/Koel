import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ChimeWordmark } from "@/components/brand/chime-brand";
import { ChatBubble } from "@/components/kit/chat-bubble";
import { FaqSection } from "@/components/kit/faq-section";
import { Steps } from "@/components/kit/steps";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import { getDashAuthConfig, SESSION_COOKIE } from "@/lib/auth/config";
import { verifySessionToken } from "@/lib/auth/session";

const FAQ = [
  {
    question: "Is Chime a CSE Tracker Pro clone?",
    answer:
      "No. Chime is a CSE market dash for browse, watch, and rules — with Telegram push as the cherry when something fires. Portfolio, tax, and heavy TA stay deferred.",
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

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="chime-atmosphere flex min-h-full flex-1 flex-col"
    >
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 py-16 sm:py-20">
        {/* Hero — brand first */}
        <div className="chime-rise">
          <ChimeWordmark size="hero" priority />
        </div>
        <h1 className="chime-rise chime-rise-delay-1 mt-6 max-w-xl text-2xl font-medium leading-snug text-foreground sm:text-3xl">
          CSE on your screen. Telegram when it matters.
        </h1>
        <p className="chime-rise chime-rise-delay-2 mt-4 max-w-md text-base text-muted-foreground sm:text-lg">
          Browse the market, watch symbols, and manage rules in the dash.
          Alerts fire on Telegram — the cherry on top when the tab is closed.
        </p>
        <NfaInline className="chime-rise chime-rise-delay-2 mt-4" />
        <div className="chime-rise chime-rise-delay-3 mt-10 flex flex-wrap items-center gap-3">
          <Button
            asChild
            size="lg"
            className="min-w-36 motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
          >
            <Link href="/login">Open the dash</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>

        {/* Product proof — DaisyUI chat pattern */}
        <section className="chime-rise chime-rise-delay-3 mt-16">
          <p className="relative mb-4 pl-3 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            <span
              aria-hidden
              className="absolute top-1/2 left-0 h-3 w-[3px] -translate-y-1/2 rounded-sm bg-primary"
            />
            The cherry — Telegram
          </p>
          <div className="rounded-xl border border-border bg-card/80 p-5 sm:p-6">
            <ChatBubble
              header="Chime CSE"
              footer="Not financial advice"
            >
              <p className="font-medium">JKH.N0000 crossed above</p>
              <p className="mt-1 font-mono text-2xl font-semibold tabular-nums">
                22.50
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                Last 22.75 · rule #184
              </p>
            </ChatBubble>
          </div>
        </section>

        {/* How it works — DaisyUI steps */}
        <section className="mt-16">
          <p className="relative mb-4 pl-3 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            <span
              aria-hidden
              className="absolute top-1/2 left-0 h-3 w-[3px] -translate-y-1/2 rounded-sm bg-primary"
            />
            How it works
          </p>
          <h2 className="font-display text-2xl font-semibold tracking-tight">
            Dash first. Push when it fires.
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

        {/* FAQ — HyperUI pattern */}
        <FaqSection
          className="mt-16 mb-8"
          eyebrow="FAQ"
          heading="Before you start"
          description="Short answers. The dash is daily; Telegram is the push cherry."
          items={FAQ}
        />
      </div>
      <NfaFooter />
    </main>
  );
}
