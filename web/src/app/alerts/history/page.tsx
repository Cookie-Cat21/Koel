import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import { serverApiGet } from "@/lib/api/server-fetch";
import { requirePageSession } from "@/lib/auth/page-session";
import { alertTypeLabel, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "History · Chime",
  description: "Alert fire history from your Chime rules.",
};

type DeliveryStatus = "sent" | "retrying" | "dead_lettered";

type HistoryPayload = {
  events: {
    id: number;
    rule_id: number;
    symbol: string;
    type: string;
    fired_at: string | null;
    message_sent: boolean;
    dead_lettered: boolean;
    attempt_count: number;
    delivery_status: DeliveryStatus;
    message_text: string | null;
    event_key: string;
  }[];
  limit: number;
  offset: number;
};

function pluralizeAttempts(count: number): string {
  return `${count} ${count === 1 ? "attempt" : "attempts"}`;
}

function deliveryBadgeClassName(status: DeliveryStatus): string {
  switch (status) {
    case "sent":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "retrying":
      return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
    case "dead_lettered":
      return "border-destructive/30 bg-destructive/10 text-destructive";
  }
}

function deliveryCopy(event: HistoryPayload["events"][number]): {
  label: string;
  description: string;
} {
  switch (event.delivery_status) {
    case "sent":
      return {
        label: "Sent",
        description: "Telegram delivery recorded.",
      };
    case "retrying":
      return {
        label: "Retrying",
        description:
          event.attempt_count > 0
            ? `Telegram delivery is still retrying after ${pluralizeAttempts(event.attempt_count)}.`
            : "Telegram delivery is queued for retry.",
      };
    case "dead_lettered":
      return {
        label: "Dead-lettered",
        description:
          event.attempt_count > 0
            ? `Retries stopped after ${pluralizeAttempts(event.attempt_count)}.`
            : "Retries stopped for this delivery row.",
      };
  }
}

export default async function AlertHistoryPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string; limit?: string }>;
}) {
  await requirePageSession();
  const sp = await searchParams;
  const symbolFilter = sp.symbol?.trim().toUpperCase() || "";
  const limitRaw = Number(sp.limit);
  const limit =
    Number.isSafeInteger(limitRaw) && limitRaw >= 1
      ? Math.min(limitRaw, 200)
      : 50;

  const qs = new URLSearchParams();
  qs.set("limit", String(limit));
  if (symbolFilter) qs.set("symbol", symbolFilter);

  const res = await serverApiGet(`/api/v1/alerts/history?${qs.toString()}`);
  const payload: HistoryPayload | null = res.ok
    ? ((await res.json()) as HistoryPayload)
    : null;

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/alerts/history" />
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          History
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          When your rules fire, Telegram gets the push. This list is the audit
          trail from Postgres.
        </p>

        <form
          method="get"
          className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-sm">
            <span className="text-muted-foreground">Symbol filter</span>
            <input
              name="symbol"
              defaultValue={symbolFilter}
              placeholder="e.g. JKH.N0000"
              className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </label>
          <button
            type="submit"
            className="inline-flex h-10 shrink-0 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Apply
          </button>
        </form>

        {!payload ? (
          <EmptyState
            title="Couldn’t load alert history"
            description={
              <>
                Chime couldn’t read alert fire history from Postgres just now.
                This is a load error, not an empty history. Retry the request —
                Telegram pushes still fire when rules match.
              </>
            }
            action={
              <Button asChild variant="outline">
                <Link href="/alerts/history">Retry loading history</Link>
              </Button>
            }
          />
        ) : payload.events.length === 0 ? (
          <EmptyState
            title={
              symbolFilter
                ? `No recorded fires for ${symbolFilter}`
                : "No alert fires recorded yet"
            }
            description={
              symbolFilter ? (
                <>
                  The history request succeeded, but no recorded fires match{" "}
                  <code className="font-mono text-xs">{symbolFilter}</code>.
                  Clear the filter, or wait until a rule for that symbol matches
                  — Telegram gets the push and this audit trail records it.
                </>
              ) : (
                <>
                  The history request succeeded, but there are no recorded fire
                  events yet. When a rule matches, Telegram gets the push and
                  the fire shows up here. Create a price, move, or disclosure
                  alert on{" "}
                  <Link
                    href="/alerts"
                    className="underline underline-offset-4"
                  >
                    Alerts
                  </Link>
                  , or use{" "}
                  <code className="font-mono text-xs">
                    /alert SYMBOL above PRICE
                  </code>{" "}
                  in Telegram.
                </>
              )
            }
            action={
              symbolFilter ? (
                <Button asChild variant="outline">
                  <Link href="/alerts/history">Clear filter</Link>
                </Button>
              ) : (
                <Button asChild variant="outline">
                  <Link href="/alerts">Create an alert</Link>
                </Button>
              )
            }
          />
        ) : (
          <ul className="mt-8 divide-y divide-border/60">
            {payload.events.map((ev) => {
              const delivery = deliveryCopy(ev);

              return (
                <li key={ev.id} className="flex flex-col gap-1 py-4 first:pt-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <Link
                      href={`/symbols/${encodeURIComponent(ev.symbol)}`}
                      className="font-mono text-sm font-medium underline-offset-4 hover:underline"
                    >
                      {ev.symbol}
                    </Link>
                    <time className="text-xs text-muted-foreground">
                      {formatTs(ev.fired_at)}
                    </time>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-foreground">
                    <span>{alertTypeLabel(ev.type)}</span>
                    <span
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${deliveryBadgeClassName(ev.delivery_status)}`}
                    >
                      {delivery.label}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {delivery.description}
                  </p>
                  {ev.message_text ? (
                    <p className="text-sm text-muted-foreground line-clamp-3">
                      {ev.message_text}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}

        <NfaInline className="mt-8" />
      </main>
      <NfaFooter />
    </div>
  );
}
