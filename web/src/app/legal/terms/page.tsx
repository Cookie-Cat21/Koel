import { ChimeWordmark } from "@/components/brand/chime-brand";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { SiteFooter } from "@/components/marketing/site-footer";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "Terms · Chime",
  description: "Chime terms stub — informational tool, not investment advice.",
};

export default function TermsPage() {
  const botUrl = telegramBotUrl();
  return (
    <div className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-3xl flex-1 px-6 py-14"
      >
        <ChimeWordmark size="md" className="opacity-90" />
        <h1 className="mt-6 font-display text-3xl font-semibold tracking-tight">
          Terms
        </h1>
        <div className="mt-6 space-y-4 text-sm leading-relaxed text-muted-foreground">
          <p>
            Chime is an information tool for Colombo Stock Exchange alerts. It
            is not investment advice, not a broker, and not a solicitation to
            deal in securities. You are responsible for verifying prices and
            filings.
          </p>
          <p>
            Service may be interrupted when upstream CSE endpoints change,
            during outages, or while the poller is outside market hours. Alerts
            can be delayed or missed — do not rely on Chime as your only risk
            control.
          </p>
          <p className="text-xs">
            This is a v1 stub, not formal legal counsel. Replace before a public
            launch with counsel-reviewed copy.
          </p>
        </div>
      </main>
      <SiteFooter telegramHref={botUrl} />
    </div>
  );
}
