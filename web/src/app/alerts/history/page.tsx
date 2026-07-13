import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import {
  MAX_HISTORY_EVENT_KEY_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toNonNegativeSafeInt, toSafePositiveInt } from "@/lib/api/safe-int";
import { serverApiGet } from "@/lib/api/server-fetch";
import { isAlertType, normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import { alertTypeLabel, formatTs } from "@/lib/format";

/** Soft-cap OFFSET — keep in sync with history API ``MAX_HISTORY_OFFSET``. */
const MAX_HISTORY_OFFSET = 10_000;
/** Parity with history API max page size. */
const MAX_PAGE_HISTORY_EVENTS = 200;

export const dynamic = "force-dynamic";

export const metadata = {
  title: "History · Chime",
  description: "Alert fire history from your Chime rules.",
};

type DeliveryStatus =
  | "sent"
  | "retrying"
  | "dead_lettered"
  | "delivered_unmarked";

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

/**
 * Cap attempt labels in fire-history copy (parity Python dead-letter notify).
 * ``toNonNegativeSafeInt`` still admits 15-digit SafeIntegers that balloon
 * ``Retries stopped after N attempts`` UI text.
 */
const MAX_ATTEMPT_COUNT_DISPLAY = 1_000_000;

function cappedAttemptCount(raw: unknown): number {
  const n =
    typeof raw === "number" && Number.isSafeInteger(raw) && raw >= 0 ? raw : 0;
  return n > MAX_ATTEMPT_COUNT_DISPLAY ? MAX_ATTEMPT_COUNT_DISPLAY : n;
}

function pluralizeAttempts(count: number): string {
  const n = cappedAttemptCount(count);
  return `${n} ${n === 1 ? "attempt" : "attempts"}`;
}

function deliveryBadgeClassName(status: DeliveryStatus): string {
  switch (status) {
    case "sent":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "delivered_unmarked":
      return "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300";
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
    case "delivered_unmarked":
      return {
        label: "Delivered (unmarked)",
        description:
          "Telegram accepted the message, but the durable sent flag was not recorded.",
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
  searchParams: Promise<{ symbol?: string; limit?: string; offset?: string }>;
}) {
  await requirePageSession();
  const sp = await searchParams;
  // Drop invalid / hostile filter params — same SYMBOL_RE as the API.
  const symbolFilter = normalizeSymbol(sp.symbol ?? "") ?? "";
  // Digits-only SafeInteger — Number("1e2") / precision-loss must not pass.
  const limitParsed = toSafePositiveInt(sp.limit ?? "");
  const limit =
    limitParsed != null ? Math.min(limitParsed, 200) : 50;
  // Soft-cap OFFSET like the API — reject sci-notation / float trunc.
  const offsetParsed = toNonNegativeSafeInt(sp.offset ?? "", -1);
  const offset =
    offsetParsed < 0 ? 0 : Math.min(offsetParsed, MAX_HISTORY_OFFSET);

  const qs = new URLSearchParams();
  qs.set("limit", String(limit));
  qs.set("offset", String(offset));
  if (symbolFilter) qs.set("symbol", symbolFilter);

  const res = await serverApiGet(`/api/v1/alerts/history?${qs.toString()}`);
  let payload: HistoryPayload | null = null;
  if (res.ok) {
    try {
      const body: unknown = await res.json();
      const eventsRaw =
        body && typeof body === "object" && !Array.isArray(body)
          ? (body as { events?: unknown }).events
          : null;
      if (Array.isArray(eventsRaw)) {
        const events: HistoryPayload["events"] = [];
        for (const row of eventsRaw) {
          if (events.length >= MAX_PAGE_HISTORY_EVENTS) break;
          if (row == null || typeof row !== "object" || Array.isArray(row)) {
            continue;
          }
          const r = row as Record<string, unknown>;
          const id = toSafePositiveInt(r.id);
          const rule_id = toSafePositiveInt(r.rule_id);
          if (id == null || rule_id == null) continue;
          if (!isAlertType(r.type)) continue;
          // Fail closed — only CSE SYMBOL_RE rows (not sanitize-only junk).
          const symbol = normalizeSymbol(
            typeof r.symbol === "string" ? r.symbol : null,
          );
          if (!symbol) continue;
          const statusRaw =
            typeof r.delivery_status === "string" ? r.delivery_status : "";
          const delivery_status: DeliveryStatus | null =
            statusRaw === "sent" ||
            statusRaw === "retrying" ||
            statusRaw === "dead_lettered" ||
            statusRaw === "delivered_unmarked"
              ? statusRaw
              : null;
          if (!delivery_status) continue;
          const attempt_count = cappedAttemptCount(
            toNonNegativeSafeInt(r.attempt_count, 0),
          );
          const event_key =
            sanitizeDisclosureText(
              typeof r.event_key === "string" ? r.event_key : null,
              MAX_HISTORY_EVENT_KEY_LENGTH,
            ) ?? "";
          const message_text =
            typeof r.message_text === "string"
              ? sanitizeDisclosureText(r.message_text, 4_000)
              : null;
          events.push({
            id,
            rule_id,
            symbol,
            type: r.type,
            fired_at: toIso(r.fired_at),
            // Strict === true — Boolean("false") must not invent sent/DL flags.
            message_sent: r.message_sent === true,
            dead_lettered: r.dead_lettered === true,
            attempt_count,
            delivery_status,
            message_text,
            event_key,
          });
        }
        const limitOut = toNonNegativeSafeInt(
          body && typeof body === "object" && !Array.isArray(body)
            ? (body as { limit?: unknown }).limit
            : limit,
          limit,
        );
        const offsetOut = toNonNegativeSafeInt(
          body && typeof body === "object" && !Array.isArray(body)
            ? (body as { offset?: unknown }).offset
            : offset,
          offset,
        );
        payload = {
          events,
          limit: Math.min(Math.max(limitOut, 1), 200),
          offset: Math.min(offsetOut, MAX_HISTORY_OFFSET),
        };
      }
    } catch {
      payload = null;
    }
  }

  function historyHref(nextOffset: number): string {
    const next = new URLSearchParams();
    next.set("limit", String(limit));
    if (nextOffset > 0) next.set("offset", String(nextOffset));
    if (symbolFilter) next.set("symbol", symbolFilter);
    const q = next.toString();
    return q ? `/alerts/history?${q}` : "/alerts/history";
  }

  const pageLimit = payload?.limit ?? limit;
  const pageOffset = payload?.offset ?? offset;
  const hasPrev = pageOffset > 0;
  const prevOffset = Math.max(0, pageOffset - pageLimit);
  const nextOffset = Math.min(pageOffset + pageLimit, MAX_HISTORY_OFFSET);
  const hasNext =
    payload != null &&
    payload.events.length >= pageLimit &&
    nextOffset > pageOffset;

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
          {/* New filter resets OFFSET; preserve limit across Apply. */}
          <input type="hidden" name="limit" value={limit} />
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

        {payload && payload.events.length > 0 && (hasPrev || hasNext) ? (
          <nav
            className="mt-6 flex items-center justify-between gap-3 text-sm"
            aria-label="Fire history pages"
          >
            {hasPrev ? (
              <Link
                href={historyHref(prevOffset)}
                rel="prev"
                aria-label="Previous page of fire history"
                className="rounded-sm underline underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                Previous
              </Link>
            ) : (
              <span
                aria-disabled="true"
                className="text-muted-foreground"
              >
                Previous
              </span>
            )}
            {hasNext ? (
              <Link
                href={historyHref(nextOffset)}
                rel="next"
                aria-label="Next page of fire history"
                className="rounded-sm underline underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                Next
              </Link>
            ) : (
              <span
                aria-disabled="true"
                className="text-muted-foreground"
              >
                Next
              </span>
            )}
          </nav>
        ) : null}

        <NfaInline className="mt-8" />
      </main>
      <NfaFooter />
    </div>
  );
}
