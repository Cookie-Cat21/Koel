import { AppNav } from "@/components/app-nav";
import { DividendCalculator } from "@/components/dividends/dividend-calculator";
import { HelpLink } from "@/components/help-link";
import { FaqSection } from "@/components/kit/faq-section";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { normalizeSymbol } from "@/lib/api/symbol";
import { requirePageSession } from "@/lib/auth/page-session";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Dividends · koel",
  description:
    "Estimate CSE dividend cash from DPS and shares, and review dividend disclosures. Not financial advice.",
};

const FAQ = [
  {
    question: "Does the market close when a company pays a dividend?",
    answer:
      "No. The CSE stays on its normal session. On the ex-dividend (XD) day that stock usually still trades — new buyers simply do not receive that dividend. Payment day is when cash is scheduled, not a market holiday.",
  },
  {
    question: "Where do XD and payment dates come from?",
    answer:
      "From CSE dividend disclosures koel already stored (title and filing brief when present). If the company posted “dates to be notified,” we show that honestly until a later filing fills them in. We do not use third-party broker calendars.",
  },
  {
    question: "Are my share quantities saved?",
    answer:
      "No. Shares stay in this browser session for the estimate only — koel does not keep a portfolio or cost basis here. Alerts and watchlists remain the persistence model.",
  },
  {
    question: "Is this investment advice?",
    answer:
      "No. Estimates are informational only and not an invitation to deal in securities. Always verify the CSE announcement before acting.",
  },
] as const;

export default async function DividendsPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string | string[] }>;
}) {
  await requirePageSession();
  const sp = await searchParams;
  const raw = Array.isArray(sp.symbol) ? sp.symbol[0] : sp.symbol;
  const initialSymbol = normalizeSymbol(raw) ?? "";

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/dividends" />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <PageHeader
          eyebrow="Tools"
          title="Dividend calculator"
          description="Estimate cash across session-only symbol rows from DPS × shares, optionally apply a rough WHT estimate, and review stored CSE dividend events."
          action={<HelpLink topic="dividends">Dividend help</HelpLink>}
        />
        <NfaInline className="mt-3" />

        <section className="mt-8" aria-label="Dividend calculator">
          <DividendCalculator initialSymbol={initialSymbol} />
        </section>

        <FaqSection
          className="mt-14 border-t border-border/60 pt-12"
          eyebrow="FAQ"
          heading="How dividends work here"
          description="Short answers so the calculator stays honest about CSE timing."
          items={[...FAQ]}
        />
      </main>
      <NfaFooter />
    </div>
  );
}
