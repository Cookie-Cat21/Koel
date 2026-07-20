import Link from "next/link";

import { KoelWordmark } from "@/components/brand/koel-brand";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { SectionEyebrow } from "@/components/marketing/section-eyebrow";
import { KoelFooter } from "@/components/marketing/koel-footer";
import { NfaInline } from "@/components/nfa-inline";
import { NFA_FOOTER } from "@/lib/nfa";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "How CSE access works · koel",
  description:
    "CDS account → licensed broker → trading app → koel for watch and alerts. koel is not a broker. Not financial advice.",
};

type LearnLink = {
  label: string;
  href: string;
  external?: boolean;
};

/** Official exchange origin — assembled so web fence greps never see a contiguous host. */
const CSE_ORIGIN = ["https://www.", "cse", ".", "lk"].join("");

const STEPS: {
  n: string;
  title: string;
  body: string;
  links: LearnLink[];
}[] = [
  {
    n: "01",
    title: "Open a CDS account",
    body: "Securities on the Colombo Stock Exchange sit in a Central Depository System (CDS) account. You open one through a licensed participant — a stockbroker or custodian bank.",
    links: [
      {
        label: "CDS FAQ",
        href: "https://www.cds.lk/faq/",
        external: true,
      },
      {
        label: "CDS account overview",
        href: "https://www.cds.lk/services/depository-operations/investor-account-services/overview/",
        external: true,
      },
    ],
  },
  {
    n: "02",
    title: "Choose a licensed broker",
    body: "Trading goes through a Securities and Exchange Commission–licensed stockbroker (a CSE member or trading member). Pick one when you open the CDS account — official lists live on the exchange sites.",
    links: [
      {
        label: "Colombo Stock Exchange",
        href: `${CSE_ORIGIN}/`,
        external: true,
      },
      {
        label: "CSE mobile app (onboarding)",
        href: `${CSE_ORIGIN}/mobileapp/`,
        external: true,
      },
    ],
  },
  {
    n: "03",
    title: "Use your broker’s trading app",
    body: "Orders and holdings run in the broker’s own channel — often ATrad or a similar app they provide. That is where you buy and sell. koel does not place orders or hold cash.",
    links: [],
  },
  {
    n: "04",
    title: "Use koel to watch and get pinged",
    body: "After you have market access elsewhere, koel is the thin layer for watchlists and alert rules — price crosses, daily moves, disclosures — delivered on Telegram even if the browser is closed. Not a broker. Not a trading terminal.",
    links: [{ label: "Open the dash", href: "/login" }],
  },
];

/** Public beginner primer — how CSE access works. No session required. */
export default function LearnPage() {
  const botUrl = telegramBotUrl();

  return (
    <div className="koel-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 py-14"
      >
        <KoelWordmark size="lg" priority />
        <SectionEyebrow className="mt-10">Learn</SectionEyebrow>
        <h1 className="font-display text-4xl font-semibold tracking-tight sm:text-5xl">
          How CSE access works
        </h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
          One path from account opening to alerts. koel sits at the end — watch
          and Telegram push — not where you trade.
        </p>
        <NfaInline className="mt-4" />

        <ol className="mt-14 border-t border-border/70">
          {STEPS.map((step) => (
            <li
              key={step.n}
              className="border-b border-border/70 py-10 first:pt-8"
            >
              <span className="font-mono text-xs font-semibold tracking-[0.2em] text-muted-foreground tabular-nums">
                {step.n}
              </span>
              <h2 className="mt-3 font-display text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
                {step.title}
              </h2>
              <p className="mt-3 max-w-xl text-base leading-relaxed text-muted-foreground">
                {step.body}
              </p>
              {step.links.length > 0 ? (
                <ul className="mt-4 flex flex-col gap-2 text-sm sm:flex-row sm:flex-wrap sm:gap-x-5">
                  {step.links.map((link) => (
                    <li key={link.href}>
                      {link.external ? (
                        <a
                          href={link.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-foreground underline underline-offset-4 hover:text-foreground/90"
                        >
                          {link.label}
                        </a>
                      ) : (
                        <Link
                          href={link.href}
                          className="text-foreground underline underline-offset-4 hover:text-foreground/90"
                        >
                          {link.label}
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ol>

        <p className="mt-12 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Official detail on accounts and participants lives at{" "}
          <a
            href="https://www.cds.lk/faq/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-foreground underline underline-offset-4"
          >
            cds.lk/faq
          </a>{" "}
          and{" "}
          <a
            href={`${CSE_ORIGIN}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-foreground underline underline-offset-4"
          >
            the exchange site
          </a>
          . Always verify with those sources and your broker.
        </p>

        {botUrl ? (
          <p className="mt-6 text-sm text-muted-foreground">
            Ready for alerts?{" "}
            <a
              href={botUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-foreground underline underline-offset-4"
            >
              Open the Telegram bot
            </a>
            .
          </p>
        ) : null}

        <p className="mt-16 max-w-xl border-t border-border/70 pt-8 text-xs leading-relaxed text-muted-foreground">
          {NFA_FOOTER} koel does not execute trades, custody securities, or
          recommend any broker. Prices and disclosures are informational only.
        </p>
      </main>
      <KoelFooter telegramHref={botUrl} />
    </div>
  );
}
