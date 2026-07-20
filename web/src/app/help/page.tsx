import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { FaqSection } from "@/components/kit/faq-section";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { requirePageSession } from "@/lib/auth/page-session";
import { HELP_TOPICS } from "@/lib/help-content";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Help · koel",
  description:
    "Glossary, how alerts and scores work, and calculation explainers with examples. Not financial advice.",
};

export default async function HelpPage() {
  await requirePageSession();

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/help" />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <PageHeader
          eyebrow="Docs"
          title="Help"
          description="What things mean, how they work, and how koel calculates them — with short examples. Jump to a topic or expand any row."
        />
        <NfaInline className="mt-3" />

        <nav
          aria-label="Help topics"
          className="mt-8 border-y border-border/60 py-5"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Topics
          </p>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {HELP_TOPICS.map((topic) => (
              <li key={topic.id}>
                <a
                  href={`#${topic.id}`}
                  className="text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline"
                >
                  {topic.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="mt-4 flex flex-col gap-16">
          {HELP_TOPICS.map((topic, index) => (
            <section
              key={topic.id}
              id={topic.id}
              className="scroll-mt-24"
              aria-labelledby={`help-topic-${topic.id}`}
            >
              <FaqSection
                eyebrow={`0${index + 1}`.slice(-2)}
                heading={topic.title}
                description={topic.summary}
                headingId={`help-topic-${topic.id}`}
                items={[...topic.items]}
              />
            </section>
          ))}
        </div>

        <p className="mt-14 max-w-xl text-sm text-muted-foreground">
          Still stuck? Use{" "}
          <a
            href="#telegram"
            className="underline underline-offset-4 transition-colors hover:text-foreground"
          >
            Telegram command parity
          </a>{" "}
          above, or open{" "}
          <Link
            href="/health"
            className="underline underline-offset-4 transition-colors hover:text-foreground"
          >
            Health
          </Link>{" "}
          when prices look stale.
        </p>
      </main>
      <NfaFooter />
    </div>
  );
}
