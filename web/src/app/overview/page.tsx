import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { ArmedBadge } from "@/components/kit/status-badge";
import { StatCard } from "@/components/kit/stat-card";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { PriceRefresh } from "@/components/price-refresh";
import { Button } from "@/components/ui/button";
import {
  MAX_STOCK_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import {
  cappedAlertThreshold,
  toFiniteNumber,
} from "@/lib/api/finite-number";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { serverApiGet } from "@/lib/api/server-fetch";
import { isAlertType, normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import { alertTypeLabel, formatNumber, formatPct, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Overview · Chime",
  description:
    "CSE market overview — watchlist, movers, and Telegram-backed alerts.",
};

type WatchItem = {
  symbol: string;
  name: string | null;
  price: number | null;
  change_pct: number | null;
  ts: string | null;
};

type MoverItem = {
  symbol: string;
  name: string | null;
  price: number | null;
  change_pct: number | null;
};

type AlertRule = {
  id: number;
  symbol: string;
  type: string;
  threshold: number | null;
  armed: boolean;
};

type HistoryEvent = {
  id: number;
  symbol: string;
  type: string;
  fired_at: string | null;
  message_text: string | null;
};

function pctTone(pct: number | null): string {
  if (pct == null) return "text-muted-foreground";
  if (pct > 0) return "text-[oklch(0.42_0.09_165)]";
  if (pct < 0) return "text-destructive";
  return "text-muted-foreground";
}

async function readJson(res: Response | null): Promise<unknown> {
  if (!res || !res.ok) return null;
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function parseWatch(body: unknown): WatchItem[] {
  if (!body || typeof body !== "object" || Array.isArray(body)) return [];
  const raw = (body as { items?: unknown }).items;
  if (!Array.isArray(raw)) return [];
  const out: WatchItem[] = [];
  for (const row of raw) {
    if (out.length >= 8) break;
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const symbol = normalizeSymbol(
      typeof r.symbol === "string" ? r.symbol : null,
    );
    if (!symbol) continue;
    out.push({
      symbol,
      name: sanitizeDisclosureText(
        typeof r.name === "string" ? r.name : null,
        MAX_STOCK_NAME_LENGTH,
      ),
      price: toFiniteNumber(r.price),
      change_pct: toFiniteNumber(r.change_pct),
      ts: toIso(r.ts),
    });
  }
  return out;
}

function parseMovers(body: unknown): MoverItem[] {
  if (!body || typeof body !== "object" || Array.isArray(body)) return [];
  const raw = (body as { items?: unknown }).items;
  if (!Array.isArray(raw)) return [];
  const out: MoverItem[] = [];
  for (const row of raw) {
    if (out.length >= 5) break;
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const symbol = normalizeSymbol(
      typeof r.symbol === "string" ? r.symbol : null,
    );
    if (!symbol) continue;
    out.push({
      symbol,
      name: sanitizeDisclosureText(
        typeof r.name === "string" ? r.name : null,
        MAX_STOCK_NAME_LENGTH,
      ),
      price: toFiniteNumber(r.price),
      change_pct: toFiniteNumber(r.change_pct),
    });
  }
  return out;
}

function parseRules(body: unknown): AlertRule[] {
  if (!body || typeof body !== "object" || Array.isArray(body)) return [];
  const raw = (body as { rules?: unknown }).rules;
  if (!Array.isArray(raw)) return [];
  const out: AlertRule[] = [];
  for (const row of raw) {
    if (out.length >= 8) break;
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const id = toSafePositiveInt(r.id);
    if (id == null || !isAlertType(r.type)) continue;
    const symbol = normalizeSymbol(
      typeof r.symbol === "string" ? r.symbol : null,
    );
    if (!symbol) continue;
    out.push({
      id,
      symbol,
      type: r.type,
      threshold: cappedAlertThreshold(toFiniteNumber(r.threshold)),
      armed: r.armed === true,
    });
  }
  return out;
}

function parseHistory(body: unknown): HistoryEvent[] {
  if (!body || typeof body !== "object" || Array.isArray(body)) return [];
  const raw = (body as { events?: unknown }).events;
  if (!Array.isArray(raw)) return [];
  const out: HistoryEvent[] = [];
  for (const row of raw) {
    if (out.length >= 6) break;
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const id = toSafePositiveInt(r.id);
    if (id == null || !isAlertType(r.type)) continue;
    const symbol = normalizeSymbol(
      typeof r.symbol === "string" ? r.symbol : null,
    );
    if (!symbol) continue;
    out.push({
      id,
      symbol,
      type: r.type,
      fired_at: toIso(r.fired_at),
      message_text:
        typeof r.message_text === "string"
          ? sanitizeDisclosureText(r.message_text, 240)
          : null,
    });
  }
  return out;
}

/**
 * Signed-in home — cake layer of the dash.
 * Telegram push stays the cherry (see Alerts / History + bot).
 */
export default async function OverviewPage() {
  await requirePageSession();

  const [watchRes, upRes, downRes, alertsRes, historyRes] = await Promise.all([
    serverApiGet("/api/v1/watchlist"),
    serverApiGet("/api/v1/market/movers?direction=up&limit=5"),
    serverApiGet("/api/v1/market/movers?direction=down&limit=5"),
    serverApiGet("/api/v1/alerts"),
    serverApiGet("/api/v1/alerts/history?limit=6"),
  ]);

  const watch = parseWatch(await readJson(watchRes));
  const gainers = parseMovers(await readJson(upRes));
  const losers = parseMovers(await readJson(downRes));
  const rules = parseRules(await readJson(alertsRes));
  const fires = parseHistory(await readJson(historyRes));
  const armedCount = rules.filter((r) => r.armed).length;

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/overview" />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <PageHeader
          eyebrow="Home"
          title="Overview"
          description="CSE snapshots from Chime’s poller. Set rules here — Telegram is the cherry that pings you when they fire."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <PriceRefresh
                lastSnapshotAt={
                  watch.map((w) => w.ts).filter(Boolean).sort().at(-1) ?? null
                }
              />
              <Button asChild size="sm">
                <Link href="/alerts">New alert</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/market">Browse</Link>
              </Button>
            </div>
          }
        />

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Watching" value={String(watch.length)} hint="On your list" />
          <StatCard
            label="Active rules"
            value={String(rules.length)}
            hint={`${armedCount} armed`}
          />
          <StatCard
            label="Recent fires"
            value={String(fires.length)}
            hint="Latest audit rows"
          />
          <StatCard
            label="Push channel"
            value="Telegram"
            hint="Cherry on top — fires even when this tab is closed"
          />
        </div>

        <div className="mt-10 grid gap-10 lg:grid-cols-2">
          <section aria-labelledby="overview-watch-heading">
            <div className="flex items-end justify-between gap-3">
              <h2
                id="overview-watch-heading"
                className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
              >
                Watchlist
              </h2>
              <Link
                href="/watchlist"
                className="text-xs text-muted-foreground underline-offset-4 hover:underline"
              >
                Open all
              </Link>
            </div>
            {watch.length === 0 ? (
              <EmptyState
                className="mt-4"
                title="Nothing watched yet"
                description="Add CSE symbols to keep prices and disclosures close. Telegram still delivers the push."
                action={
                  <Button asChild size="sm">
                    <Link href="/market">Browse market</Link>
                  </Button>
                }
              />
            ) : (
              <ul className="mt-4 divide-y divide-border/60">
                {watch.map((item) => (
                  <li key={item.symbol} className="flex items-baseline justify-between gap-3 py-3">
                    <Link
                      href={`/symbols/${encodeURIComponent(item.symbol)}`}
                      className="min-w-0 font-mono text-sm font-medium underline-offset-4 hover:underline"
                    >
                      {item.symbol}
                      {item.name ? (
                        <span className="mt-0.5 block truncate font-sans text-xs font-normal text-muted-foreground">
                          {item.name}
                        </span>
                      ) : null}
                    </Link>
                    <div className="shrink-0 text-right">
                      <p className="font-mono text-sm">{formatNumber(item.price)}</p>
                      <p className={`font-mono text-xs ${pctTone(item.change_pct)}`}>
                        {formatPct(item.change_pct)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="overview-alerts-heading">
            <div className="flex items-end justify-between gap-3">
              <h2
                id="overview-alerts-heading"
                className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
              >
                Armed alerts
              </h2>
              <Link
                href="/alerts"
                className="text-xs text-muted-foreground underline-offset-4 hover:underline"
              >
                Manage
              </Link>
            </div>
            {rules.length === 0 ? (
              <EmptyState
                className="mt-4"
                title="No rules yet"
                description="Create a price, move, or disclosure rule. When it matches, Telegram gets the ping."
                action={
                  <Button asChild size="sm">
                    <Link href="/alerts">Create alert</Link>
                  </Button>
                }
              />
            ) : (
              <ul className="mt-4 divide-y divide-border/60">
                {rules.map((rule) => (
                  <li
                    key={rule.id}
                    className="flex flex-wrap items-center justify-between gap-2 py-3"
                  >
                    <div className="min-w-0">
                      <Link
                        href={`/symbols/${encodeURIComponent(rule.symbol)}`}
                        className="font-mono text-sm font-medium underline-offset-4 hover:underline"
                      >
                        {rule.symbol}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {alertTypeLabel(rule.type)}
                        {rule.threshold != null
                          ? ` · ${formatNumber(rule.threshold)}`
                          : ""}
                      </p>
                    </div>
                    <ArmedBadge armed={rule.armed} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <div className="mt-10 grid gap-10 lg:grid-cols-2">
          <MoversColumn
            id="overview-gainers-heading"
            title="Top gainers"
            items={gainers}
            empty="No gainer snapshots yet — run the poller / tick."
          />
          <MoversColumn
            id="overview-losers-heading"
            title="Top losers"
            items={losers}
            empty="No loser snapshots yet — run the poller / tick."
          />
        </div>

        <section className="mt-10" aria-labelledby="overview-fires-heading">
          <div className="flex items-end justify-between gap-3">
            <h2
              id="overview-fires-heading"
              className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
            >
              Recent fires
            </h2>
            <Link
              href="/alerts/history"
              className="text-xs text-muted-foreground underline-offset-4 hover:underline"
            >
              Full history
            </Link>
          </div>
          {fires.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              No fires recorded yet. When a rule matches, Telegram gets the push
              and the audit trail shows up here.
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-border/60">
              {fires.map((ev) => (
                <li key={ev.id} className="py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
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
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {alertTypeLabel(ev.type)}
                    {ev.message_text ? ` — ${ev.message_text}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <NfaInline className="mt-8" />
      </main>
      <NfaFooter />
    </div>
  );
}

function MoversColumn({
  id,
  title,
  items,
  empty,
}: {
  id: string;
  title: string;
  items: MoverItem[];
  empty: string;
}) {
  return (
    <section aria-labelledby={id}>
      <h2
        id={id}
        className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
      >
        {title}
      </h2>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="mt-4 divide-y divide-border/60">
          {items.map((item) => (
            <li
              key={item.symbol}
              className="flex items-baseline justify-between gap-3 py-3"
            >
              <Link
                href={`/symbols/${encodeURIComponent(item.symbol)}`}
                className="min-w-0 font-mono text-sm font-medium underline-offset-4 hover:underline"
              >
                {item.symbol}
                {item.name ? (
                  <span className="mt-0.5 block truncate font-sans text-xs font-normal text-muted-foreground">
                    {item.name}
                  </span>
                ) : null}
              </Link>
              <div className="shrink-0 text-right">
                <p className="font-mono text-sm">{formatNumber(item.price)}</p>
                <p className={`font-mono text-xs ${pctTone(item.change_pct)}`}>
                  {formatPct(item.change_pct)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
