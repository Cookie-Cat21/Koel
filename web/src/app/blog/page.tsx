import { KoelWordmark } from "@/components/brand/koel-brand";
import { BlogList } from "@/components/marketing/blog-list";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { KoelFooter } from "@/components/marketing/koel-footer";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "Blog · koel",
  description:
    "Ops notes and CSE endpoint changes — koel product journal.",
};

/** Watermelon blog-1 stub — empty until real posts land. */
export default function BlogPage() {
  const botUrl = telegramBotUrl();

  return (
    <div className="koel-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-14"
      >
        <KoelWordmark size="lg" priority />
        <BlogList
          className="mt-10"
          heading="Notes from the wire"
          description="Short ops notes — CSE endpoint changes, poller status, product fence. Not investment tips."
          ctaText="Home"
          ctaHref="/"
          posts={[]}
        />
      </main>
      <KoelFooter telegramHref={botUrl} />
    </div>
  );
}
