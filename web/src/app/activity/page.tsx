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
  title: "Activity · koel",
  description:
    "Watchlist timeline — Telegram fires, disclosures, and upcoming XD dates.",
};

type ActivityPayload = {
  items?: {
    id: string;
    kind: string;
    at: string | null;
    symbol: string | null;
    title: string;
    href: string | null;
    badge: string | null;
    meta: string | null;
  }[];
};

export default async function ActivityPage() {
  await requirePageSession();
  const res = await serverApiGet("/api/v1/activity?limit=50");
  let items: EventTimelineItem[] = [];
  if (res.ok) {
    try {
      const body = (await res.json()) as ActivityPayload;
      if (Array.isArray(body.items)) {
        items = body.items.map((row) => ({
          id: row.id,
          at: row.at ? formatTs(row.at) : null,
          title: row.symbol ? `${row.symbol} — ${row.title}` : row.title,
          href: row.href,
          badge: row.badge,
          meta: row.meta,
          emphasis:
            row.kind === "fire"
              ? "live"
              : row.kind === "xd"
                ? "empty"
                : "default",
        }));
      }
    } catch {
      items = [];
    }
  }

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/activity" />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <PageHeader
          eyebrow="Watchlist"
          title="Activity"
          description="Fires, filings, and XD dates for symbols you watch — one timeline, Postgres facts only."
          action={<HelpLink topic="alerts">Alerts help</HelpLink>}
        />
        <p className="mt-2 text-sm text-muted-foreground">
          <NfaInline /> Research feed, not tips.
        </p>

        {items.length === 0 ? (
          <EmptyState
            title="No activity yet"
            description="Watch symbols and arm alerts — fires and disclosures will land here."
            action={
              <Button asChild variant="outline">
                <Link href="/watchlist">Open watchlist</Link>
              </Button>
            }
          />
        ) : (
          <div className="mt-8 max-w-2xl">
            <EventTimeline items={items} />
          </div>
        )}
      </main>
      <NfaFooter />
    </div>
  );
}
