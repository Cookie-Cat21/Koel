import Link from "next/link";

import {
  AlertCreateForm,
  CancelAlertButton,
  MuteAlertButton,
  TestFireButton,
} from "@/components/alert-controls";
import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { HelpLink } from "@/components/help-link";
import { ArmedBadge } from "@/components/kit/status-badge";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { serverApiGet } from "@/lib/api/server-fetch";
import { sanitizeDisclosureCategory } from "@/lib/api/disclosure-safe";
import {
  cappedAlertThreshold,
  toFiniteNumber,
} from "@/lib/api/finite-number";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { isAlertType, normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import {
  alertTypeBotHint,
  alertTypeLabel,
  formatNumber,
  formatTs,
} from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Alerts · koel",
  description: "Active alert rules for your koel watchlist.",
};

function isActivelyMuted(mutedUntil: string | null): boolean {
  if (!mutedUntil) return false;
  const t = Date.parse(mutedUntil);
  return Number.isFinite(t) && t > Date.now();
}

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
    muted_until: string | null;
  }[];
};

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string; type?: string }>;
}) {
  await requirePageSession();
  const sp = await searchParams;
  // Drop invalid / hostile filter params — same SYMBOL_RE as the API.
  const symbolFilter = normalizeSymbol(sp.symbol ?? "") ?? "";
  const typeFilter = isAlertType(sp.type) ? sp.type : null;

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
          // Fail closed — only CSE SYMBOL_RE rows (not sanitize-only junk).
          const symbol = normalizeSymbol(
            typeof r.symbol === "string" ? r.symbol : null,
          );
          if (!symbol) continue;
          const threshold = cappedAlertThreshold(toFiniteNumber(r.threshold));
          rules.push({
            id,
            symbol,
            type: r.type,
            threshold,
            category: sanitizeDisclosureCategory(
              typeof r.category === "string" ? r.category : null,
            ),
            // Strict === true — Boolean("false") used to show Armed wrongly.
            active: r.active === true,
            armed: r.armed === true,
            created_at: toIso(r.created_at),
            muted_until: toIso(r.muted_until),
          });
          // Cap parser — hostile / uncapped API JSON must not balloon SSR.
          if (rules.length >= 500) break;
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
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <PageHeader
          eyebrow="Rules"
          title="Alerts"
          description="Active rules only. Create a price, move, or disclosure alert here; koel adds the symbol to your watchlist and sends the push on Telegram."
          action={<HelpLink topic="alerts">How alerts work</HelpLink>}
        />

        <form
          method="get"
          className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <Label htmlFor="alerts_symbol_filter">Symbol filter</Label>
            <Input
              id="alerts_symbol_filter"
              name="symbol"
              defaultValue={symbolFilter}
              placeholder="e.g. JKH.N0000"
              className="h-10 font-mono"
              autoComplete="off"
            />
          </div>
          <Button type="submit" className="h-10 shrink-0">
            Apply
          </Button>
          {symbolFilter ? (
            <Button asChild variant="outline" className="h-10 shrink-0">
              <Link href="/alerts">Clear</Link>
            </Button>
          ) : null}
        </form>

        <AlertCreateForm
          initialSymbol={symbolFilter}
          initialType={typeFilter}
        />
        <p className="mt-3 text-xs text-muted-foreground">
          Quiet hours / digest:{" "}
          <Link href="/settings" className="underline underline-offset-4">
            Settings
          </Link>
          . Mute / test fire / cancel:{" "}
          <HelpLink topic="alerts" variant="text">
            how alerts work
          </HelpLink>
          . Delivery statuses:{" "}
          <HelpLink topic="alert-history" variant="text">
            history help
          </HelpLink>
          . Filing EPS/YoY rules need metrics flags to live-fire. Alert types:{" "}
          <HelpLink topic="alert-types" variant="text">
            alert types help
          </HelpLink>
          .
        </p>

        {!payload ? (
          <EmptyState
            title="Couldn’t load alerts"
            description={
              <>
                koel couldn’t fetch your rules right now. Refresh in a moment,
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
                  disclosure rule.{" "}
                  <Link
                    href="/market"
                    className="rounded-sm underline underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                  >
                    Browse
                  </Link>{" "}
                  to pick a CSE ticker, or use{" "}
                  <code className="font-mono text-xs">
                    /alert SYMBOL above PRICE
                  </code>{" "}
                  in Telegram — koel pushes when it fires. Unsure about
                  crossing vs armed?{" "}
                  <HelpLink topic="alerts" variant="text">
                    Read Help
                  </HelpLink>
                  .
                </>
              )
            }
            action={
              symbolFilter ? (
                <div className="flex flex-wrap gap-2">
                  <Button asChild>
                    <a href="#alert_symbol">Create an alert</a>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href="/alerts">Clear filter</Link>
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <Button asChild>
                    <a href="#alert_symbol">Create an alert</a>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href="/market">Browse</Link>
                  </Button>
                </div>
              )
            }
          />
        ) : (
          <ul className="mt-8 divide-y divide-border/60">
            {payload.rules.map((rule) => {
              const hint = alertTypeBotHint(rule.type);
              return (
                <li
                  key={rule.id}
                  className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/symbols/${encodeURIComponent(rule.symbol)}`}
                        className="font-mono text-sm font-medium underline-offset-4 hover:underline"
                      >
                        {rule.symbol}
                      </Link>
                      <ArmedBadge armed={rule.armed} />
                      {isActivelyMuted(rule.muted_until) ? (
                        <Badge
                          variant="outline"
                          className="border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
                        >
                          Muted
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      #{rule.id} · {alertTypeLabel(rule.type)}
                      {rule.threshold != null
                        ? ` · ${formatNumber(rule.threshold)}`
                        : ""}
                      {rule.category ? ` · ${rule.category}` : ""}
                    </p>
                    {hint ? (
                      <p className="mt-1 font-mono text-xs text-muted-foreground">
                        {hint}
                      </p>
                    ) : null}
                    <p className="mt-1 text-xs text-muted-foreground">
                      Created {formatTs(rule.created_at)}
                      {isActivelyMuted(rule.muted_until)
                        ? ` · muted until ${formatTs(rule.muted_until)}`
                        : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <TestFireButton ruleId={rule.id} />
                    <MuteAlertButton
                      ruleId={rule.id}
                      mutedUntil={rule.muted_until}
                    />
                    <CancelAlertButton ruleId={rule.id} />
                  </div>
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
