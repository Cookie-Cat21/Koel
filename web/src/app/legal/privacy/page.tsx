import { ChimeWordmark } from "@/components/brand/chime-brand";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { SiteFooter } from "@/components/marketing/site-footer";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "Privacy · Chime",
  description: "Chime privacy stub — public CSE data, Telegram identity.",
};

export default function PrivacyPage() {
  const botUrl = telegramBotUrl();
  return (
    <div className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-3xl flex-1 px-6 py-14"
      >
        <ChimeWordmark size="lg" priority />
        <h1 className="mt-8 font-display text-4xl font-semibold tracking-tight sm:text-5xl">
          Privacy
        </h1>
        <div className="mt-8 max-w-2xl space-y-5 text-base leading-relaxed text-muted-foreground">
          <p>
            Chime stores your Telegram user id (when you sign in), watchlist
            symbols, alert rules, and delivery logs needed to send pushes. We
            use publicly available CSE market data — we do not scrape competitor
            products.
          </p>
          <p>
            We do not sell personal data. Demo dash access is for allowlisted
            Telegram ids only. Contact the operator if you need data removed.
          </p>
          <p className="text-sm">
            This is a v1 stub, not formal legal counsel. Replace before a public
            launch with counsel-reviewed copy.
          </p>
        </div>
      </main>
      <SiteFooter telegramHref={botUrl} />
    </div>
  );
}
