import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { NfaFooter } from "@/components/nfa-footer";
import { serverApiGet } from "@/lib/api/server-fetch";
import { requirePageSession } from "@/lib/auth/page-session";
import { alertTypeLabel, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "History · Chime",
  description: "Alert fire history from your Chime rules.",
};

type HistoryPayload = {
  events: {
    id: number;
    rule_id: number;
    symbol: string;
    type: string;
    fired_at: string | null;
    message_sent: boolean;
    message_text: string | null;
    event_key: string;
  }[];
  limit: number;
  offset: number;
};

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
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
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
          <p className="mt-8 text-sm text-muted-foreground">
            Could not load fire history right now.
          </p>
        ) : payload.events.length === 0 ? (
          <p className="mt-8 text-sm text-muted-foreground">
            No fires yet
            {symbolFilter ? ` for ${symbolFilter}` : ""}. When a rule matches,
            it shows up here.
          </p>
        ) : (
          <ul className="mt-8 divide-y divide-border/60">
            {payload.events.map((ev) => (
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
                <p className="text-sm text-foreground">
                  {alertTypeLabel(ev.type)}
                  <span className="text-muted-foreground">
                    {" · "}
                    {ev.message_sent ? "Sent" : "Not sent"}
                  </span>
                </p>
                {ev.message_text ? (
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {ev.message_text}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </main>
      <NfaFooter />
    </div>
  );
}
