import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { HelpLink } from "@/components/help-link";
import { EventTimeline, type EventTimelineItem } from "@/components/kit/event-timeline";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { serverApiGet } from "@/lib/api/server-fetch";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Events · koel",
  description: "Upcoming XD dates and recent results filings for your watchlist.",
};

type EventsPayload = {
  xd?: {
    id: string;
    at: string | null;
    symbol: string;
    title: string;
    badge: string;
    href: string;
  }[];
  results?: {
    id: string;
    at: string | null;
    symbol: string;
    title: string;
    badge: string;
    href: string;
  }[];
};

export default async function EventsPage() {
  await requirePageSession();
  const res = await serverApiGet("/api/v1/events");
  let xdItems: EventTimelineItem[] = [];
  let resultItems: EventTimelineItem[] = [];
  if (res.ok) {
    try {
      const body = (await res.json()) as EventsPayload;
      xdItems = (body.xd ?? []).map((row) => ({
        id: row.id,
        at: row.at ? formatTs(row.at) : null,
        title: `${row.symbol} — ${row.title}`,
        href: row.href,
        badge: row.badge,
        emphasis: "empty" as const,
      }));
      resultItems = (body.results ?? []).map((row) => ({
        id: row.id,
        at: row.at ? formatTs(row.at) : null,
        title: `${row.symbol} — ${row.title}`,
        href: row.href,
        badge: row.badge,
        emphasis: "live" as const,
      }));
    } catch {
      /* empty */
    }
  }

  const empty = xdItems.length === 0 && resultItems.length === 0;

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/events" />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <PageHeader
          eyebrow="Calendar"
          title="Events"
          description="Ex-dividend dates ahead and recent results filings on your watchlist."
          action={<HelpLink topic="dividends">Dividends help</HelpLink>}
        />
        <p className="mt-2 text-sm text-muted-foreground">
          <NfaInline /> Dates from CSE disclosures koel already stores.
        </p>

        {empty ? (
          <EmptyState
            title="No events on file"
            description="Add watches and wait for dividend or results disclosures to land."
            action={
              <Button asChild variant="outline">
                <Link href="/watchlist">Open watchlist</Link>
              </Button>
            }
          />
        ) : (
          <div className="mt-8 grid gap-10 lg:grid-cols-2">
            <section>
              <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                Upcoming XD
              </h2>
              <div className="mt-4">
                <EventTimeline
                  items={xdItems}
                  empty={
                    <p className="text-sm text-muted-foreground">
                      No XD dates in the next 60 days.
                    </p>
                  }
                />
              </div>
            </section>
            <section>
              <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                Results day (recent)
              </h2>
              <div className="mt-4">
                <EventTimeline
                  items={resultItems}
                  empty={
                    <p className="text-sm text-muted-foreground">
                      No results-tagged filings in the last 45 days.
                    </p>
                  }
                />
              </div>
            </section>
          </div>
        )}
      </main>
      <NfaFooter />
    </div>
  );
}
