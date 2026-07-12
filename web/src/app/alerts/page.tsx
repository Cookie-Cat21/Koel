import Link from "next/link";

import {
  AlertCreateForm,
  CancelAlertButton,
} from "@/components/alert-controls";
import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import { serverApiGet } from "@/lib/api/server-fetch";
import {
  MAX_HISTORY_SYMBOL_LENGTH,
  sanitizeDisclosureCategory,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { isAlertType, normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import { alertTypeLabel, formatNumber, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Alerts · Chime",
  description: "Active alert rules for your Chime watchlist.",
};

type AlertsPayload = {
  rules: {
    id: number;
    symbol: string;
    type: string;
    threshold: number | null;
    category: string | null;
    active: boolean;
    armed: boolean;
    created_at: string | null;
  }[];
};

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string }>;
}) {
  await requirePageSession();
  const sp = await searchParams;
  // Drop invalid / hostile filter params — same SYMBOL_RE as the API.
  const symbolFilter = normalizeSymbol(sp.symbol ?? "") ?? "";

  const qs = new URLSearchParams();
  if (symbolFilter) qs.set("symbol", symbolFilter);
  const path =
    qs.size > 0 ? `/api/v1/alerts?${qs.toString()}` : "/api/v1/alerts";

  const res = await serverApiGet(path);
  let payload: AlertsPayload | null = null;
  if (res.ok) {
    try {
      const body: unknown = await res.json();
      const rulesRaw =
        body && typeof body === "object" && !Array.isArray(body)
          ? (body as { rules?: unknown }).rules
          : null;
      if (Array.isArray(rulesRaw)) {
        const rules: AlertsPayload["rules"] = [];
        for (const row of rulesRaw) {
          if (row == null || typeof row !== "object" || Array.isArray(row)) {
            continue;
          }
          const r = row as Record<string, unknown>;
          const id = toSafePositiveInt(r.id);
          if (id == null) continue;
          if (!isAlertType(r.type)) continue;
          const symbol =
            sanitizeDisclosureText(
              typeof r.symbol === "string" ? r.symbol : null,
              MAX_HISTORY_SYMBOL_LENGTH,
            ) ?? "";
          if (!symbol) continue;
          const threshold =
            typeof r.threshold === "number" && Number.isFinite(r.threshold)
              ? r.threshold
              : null;
          rules.push({
            id,
            symbol,
            type: r.type,
            threshold,
            category: sanitizeDisclosureCategory(
              typeof r.category === "string" ? r.category : null,
            ),
            active: Boolean(r.active),
            armed: Boolean(r.armed),
            created_at: toIso(r.created_at),
          });
        }
        payload = { rules };
      }
    } catch {
      payload = null;
    }
  }

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/alerts" />
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          Alerts
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Active rules only. Create a price, move, or disclosure alert here;
          Chime adds the symbol to your watchlist and sends the push on
          Telegram.
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
          {symbolFilter ? (
            <Button asChild variant="outline" className="h-10 shrink-0">
              <Link href="/alerts">Clear</Link>
            </Button>
          ) : null}
        </form>

        <AlertCreateForm />

        {!payload ? (
          <EmptyState
            title="Couldn’t load alerts"
            description={
              <>
                Chime couldn’t fetch your rules right now. Refresh in a moment,
                or set alerts with{" "}
                <code className="font-mono text-xs">
                  /alert SYMBOL above PRICE
                </code>{" "}
                in Telegram.
              </>
            }
            action={
              <Button asChild variant="outline">
                <Link href="/alerts">Try again</Link>
              </Button>
            }
          />
        ) : payload.rules.length === 0 ? (
          <EmptyState
            title={
              symbolFilter
                ? `No active rules for ${symbolFilter}`
                : "No active rules yet"
            }
            description={
              symbolFilter ? (
                <>
                  No matching rules for{" "}
                  <code className="font-mono text-xs">{symbolFilter}</code>.
                  Clear the filter, or use the create form above to add a rule
                  for this symbol.
                </>
              ) : (
                <>
                  Use the create form above to add a price cross, daily move, or
                  disclosure rule. Telegram gets the push when it fires. Same
                  command path:{" "}
                  <code className="font-mono text-xs">
                    /alert SYMBOL above PRICE
                  </code>
                  .
                </>
              )
            }
            action={
              symbolFilter ? (
                <Button asChild variant="outline">
                  <Link href="/alerts">Clear filter</Link>
                </Button>
              ) : (
                <Button asChild>
                  <a href="#alert_symbol">Create an alert</a>
                </Button>
              )
            }
          />
        ) : (
          <ul className="mt-8 divide-y divide-border/60">
            {payload.rules.map((rule) => (
              <li
                key={rule.id}
                className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
              >
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/symbols/${encodeURIComponent(rule.symbol)}`}
                    className="font-mono text-sm font-medium underline-offset-4 hover:underline"
                  >
                    {rule.symbol}
                  </Link>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    #{rule.id} · {alertTypeLabel(rule.type)}
                    {rule.threshold != null
                      ? ` · ${formatNumber(rule.threshold)}`
                      : ""}
                    {rule.category ? ` · ${rule.category}` : ""}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {rule.armed ? "Armed" : "Disarmed"} ·{" "}
                    {formatTs(rule.created_at)}
                  </p>
                </div>
                <CancelAlertButton ruleId={rule.id} />
              </li>
            ))}
          </ul>
        )}

        <NfaInline className="mt-8" />
      </main>
      <NfaFooter />
    </div>
  );
}
