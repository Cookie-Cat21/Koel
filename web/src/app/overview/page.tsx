import Link from "next/link";

import { AppetiteStrip } from "@/components/appetite/appetite-strip";
import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { CakeCherryBanner } from "@/components/kit/cake-cherry-banner";
import { ChangeBadge } from "@/components/kit/change-badge";
import {
  IndexStrip,
  type IndexStripBars,
  type IndexStripItem,
  type IndexStripTicks,
} from "@/components/kit/index-strip";
import { MoversBarList } from "@/components/kit/movers-bar-list";
import {
  SectorHeatStrip,
  type SectorHeatItem,
} from "@/components/kit/sector-heat-strip";
import { NotificationList } from "@/components/kit/notification-list";
import { ArmedBadge } from "@/components/kit/status-badge";
import { StatCard } from "@/components/kit/stat-card";
import { MarketSessionChip } from "@/components/market-session-chip";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { PriceRefresh } from "@/components/price-refresh";
import { Button } from "@/components/ui/button";
import {
  deltaVs,
  headlineDay,
  headlineIndex,
  queryAppetiteHistory,
  type AppetiteDay,
} from "@/lib/api/appetite";
import {
  normalizeDailyBar,
  type DailyBarPoint,
} from "@/lib/api/daily-bars";
import { getPool } from "@/lib/db";
import {
  MAX_SECTOR_NAME_LENGTH,
  MAX_STOCK_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import {
  cappedAlertThreshold,
  toFiniteNumber,
} from "@/lib/api/finite-number";
import { INDEX_CODES } from "@/lib/api/indexes";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { serverApiGet } from "@/lib/api/server-fetch";
import { isAlertType, normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import { alertTypeLabel, formatNumber, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Overview · koel",
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

function parseIndexes(body: unknown): IndexStripItem[] {
  if (!body || typeof body !== "object" || Array.isArray(body)) return [];
  const raw = (body as { items?: unknown }).items;
  if (!Array.isArray(raw)) return [];
  const out: IndexStripItem[] = [];
  for (const row of raw) {
    if (out.length >= 8) break;
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const code =
      typeof r.code === "string" && r.code.trim()
        ? r.code.trim().slice(0, 32)
        : null;
    if (!code) continue;
    const name =
      sanitizeDisclosureText(
        typeof r.name === "string" ? r.name : null,
        64,
      ) ?? code;
    out.push({
      code,
      name,
      value: toFiniteNumber(r.value),
      change_pct: toFiniteNumber(r.change_pct),
      ts: toIso(r.ts),
    });
  }
  return out;
}

async function loadIndexDailyPath(): Promise<{
  barsByCode: IndexStripBars;
  ticksByCode: IndexStripTicks;
}> {
  const barsByCode: IndexStripBars = {};
  const ticksByCode: IndexStripTicks = {};
  try {
    const pool = getPool();
    for (const code of INDEX_CODES) {
      const barsRes = await pool.query<{
        trade_date: Date | string;
        open: number | null;
        high: number | null;
        low: number | null;
        price: number;
        volume: number | null;
      }>(
        `
        SELECT trade_date, open, high, low, price, volume
        FROM daily_bars
        WHERE symbol = $1
        ORDER BY trade_date DESC
        LIMIT 260
        `,
        [code],
      );
      const bars: DailyBarPoint[] = [];
      for (const row of barsRes.rows) {
        const b = normalizeDailyBar(row);
        if (b) bars.push(b);
      }
      bars.reverse();
      if (bars.length > 0) barsByCode[code] = bars;

      const tickRes = await pool.query<{
        value: number | string | null;
        ts: Date | string;
      }>(
        `
        SELECT value, ts
        FROM index_snapshots
        WHERE code = $1
        ORDER BY ts DESC
        LIMIT 240
        `,
        [code],
      );
      const ticks: { ts: string | null; price: number | null }[] = [];
      for (const row of [...tickRes.rows].reverse()) {
        const price = toFiniteNumber(row.value);
        if (price == null || price <= 0) continue;
        ticks.push({ ts: toIso(row.ts), price });
      }
      if (ticks.length > 0) ticksByCode[code] = ticks;
    }
  } catch {
    // Charts stay empty — strip still shows latest index values.
  }
  return { barsByCode, ticksByCode };
}

function parseSectors(body: unknown): SectorHeatItem[] {
  if (!body || typeof body !== "object" || Array.isArray(body)) return [];
  const raw = (body as { items?: unknown }).items;
  if (!Array.isArray(raw)) return [];
  const out: SectorHeatItem[] = [];
  for (const row of raw) {
    if (out.length >= 24) break;
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const sectorId = toSafePositiveInt(r.sector_id);
    if (sectorId == null) continue;
    const name =
      sanitizeDisclosureText(
        typeof r.name === "string" ? r.name : null,
        MAX_SECTOR_NAME_LENGTH,
      ) ?? "";
    if (!name) continue;
    out.push({
      sector_id: sectorId,
      name,
      change_pct: toFiniteNumber(r.change_pct),
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

  let appetiteHistory: AppetiteDay[] = [];
  try {
    appetiteHistory = await queryAppetiteHistory(getPool(), {
      limit: 90,
      source: "cse",
    });
  } catch {
    appetiteHistory = [];
  }
  const appetiteLatest = headlineDay(appetiteHistory);
  const appetiteDelta1 = deltaVs(
    appetiteHistory,
    1,
    headlineIndex(appetiteHistory),
  );

  const [
    watchRes,
    upRes,
    downRes,
    alertsRes,
    historyRes,
    indexesRes,
    sectorsRes,
    indexCharts,
  ] = await Promise.all([
    serverApiGet("/api/v1/watchlist"),
    serverApiGet("/api/v1/market/movers?direction=up&limit=5"),
    serverApiGet("/api/v1/market/movers?direction=down&limit=5"),
    serverApiGet("/api/v1/alerts"),
    serverApiGet("/api/v1/alerts/history?limit=6"),
    serverApiGet("/api/v1/indexes"),
    serverApiGet("/api/v1/sectors"),
    loadIndexDailyPath(),
  ]);

  const watch = parseWatch(await readJson(watchRes));
  const gainers = parseMovers(await readJson(upRes));
  const losers = parseMovers(await readJson(downRes));
  const rules = parseRules(await readJson(alertsRes));
  const fires = parseHistory(await readJson(historyRes));
  const indexes = parseIndexes(await readJson(indexesRes));
  const sectors = parseSectors(await readJson(sectorsRes));
  const armedCount = rules.filter((r) => r.armed).length;
  const freshestTs =
    [
      ...watch.map((w) => w.ts),
      ...indexes.map((i) => i.ts),
    ]
      .filter((t): t is string => typeof t === "string" && !!t)
      .sort()
      .at(-1) ?? null;

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
          description="CSE snapshots from koel’s poller. Set rules here — Telegram is the cherry that pings you when they fire."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <MarketSessionChip />
              <PriceRefresh lastSnapshotAt={freshestTs} />
              <Button asChild size="sm">
                <Link href="/alerts">New alert</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/market">Browse</Link>
              </Button>
            </div>
          }
        />

        <CakeCherryBanner />

        <section className="mt-6" aria-labelledby="overview-indexes-heading">
          <h2
            id="overview-indexes-heading"
            className="mb-2 text-sm font-medium tracking-wide text-muted-foreground uppercase"
          >
            Market indexes
          </h2>
          <IndexStrip
            items={indexes}
            barsByCode={indexCharts.barsByCode}
            ticksByCode={indexCharts.ticksByCode}
          />
        </section>

        <AppetiteStrip
          className="mt-4"
          latest={appetiteLatest}
          historyAsc={appetiteHistory}
          delta1={appetiteDelta1}
        />

        {sectors.length > 0 ? (
          <section className="mt-4" aria-labelledby="overview-sectors-heading">
            <h2
              id="overview-sectors-heading"
              className="mb-2 text-sm font-medium tracking-wide text-muted-foreground uppercase"
            >
              Sectors
            </h2>
            <SectorHeatStrip items={sectors} />
          </section>
        ) : null}

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
                  <li
                    key={item.symbol}
                    className="flex items-center justify-between gap-3 py-3"
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
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="font-mono text-sm tabular-nums">
                        {formatNumber(item.price)}
                      </span>
                      <ChangeBadge changePct={item.change_pct} />
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
            {armedCount === 0 ? (
              <EmptyState
                className="mt-4"
                title={rules.length === 0 ? "No rules yet" : "No armed alerts"}
                description={
                  rules.length === 0
                    ? "Create a price, move, or disclosure rule. When it matches, Telegram gets the ping."
                    : "You have rules, but none are armed right now. Open Alerts to re-enable or unmute."
                }
                action={
                  <Button asChild size="sm">
                    <Link href="/alerts">
                      {rules.length === 0 ? "Create alert" : "Manage alerts"}
                    </Link>
                  </Button>
                }
              />
            ) : (
              <ul className="mt-4 divide-y divide-border/60">
                {rules
                  .filter((rule) => rule.armed)
                  .map((rule) => (
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
          <section aria-labelledby="overview-gainers-heading">
            <h2
              id="overview-gainers-heading"
              className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
            >
              Top gainers
            </h2>
            <div className="mt-4">
              <MoversBarList
                items={gainers}
                empty="No gainer snapshots yet — run the poller / tick."
              />
            </div>
          </section>
          <section aria-labelledby="overview-losers-heading">
            <h2
              id="overview-losers-heading"
              className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
            >
              Top losers
            </h2>
            <div className="mt-4">
              <MoversBarList
                items={losers}
                empty="No loser snapshots yet — run the poller / tick."
              />
            </div>
          </section>
        </div>

        <section className="mt-10" aria-labelledby="overview-fires-heading">
          <h2
            id="overview-fires-heading"
            className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
          >
            Recent fires
          </h2>
          <div className="mt-4">
            <NotificationList
              viewAllHref="/alerts/history"
              items={fires.map((ev) => ({
                id: ev.id,
                title: ev.symbol,
                subtitle: [
                  alertTypeLabel(ev.type),
                  ev.message_text ? ev.message_text.slice(0, 80) : null,
                ]
                  .filter(Boolean)
                  .join(" — "),
                time: formatTs(ev.fired_at),
                href: `/symbols/${encodeURIComponent(ev.symbol)}`,
              }))}
            />
          </div>
        </section>

        <NfaInline className="mt-8" />
      </main>
      <NfaFooter />
    </div>
  );
}
