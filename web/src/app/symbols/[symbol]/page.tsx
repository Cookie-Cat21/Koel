import Link from "next/link";
import { notFound } from "next/navigation";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import {
  DisclosureCategoryHint,
  DisclosureTimeline,
} from "@/components/kit/disclosure-timeline";
import { DataQualityNotices } from "@/components/kit/data-quality-notices";
import {
  FilingMetricsPanel,
  type FilingMetricComparison,
  type FilingMetricRow,
  type LatestBrief,
} from "@/components/kit/filing-metrics-panel";
import { FilingSnapshotStrip } from "@/components/kit/filing-snapshot-strip";
import { FundamentalsStrip } from "@/components/kit/fundamentals-strip";
import { PeriodReturnsStrip } from "@/components/kit/period-returns-strip";
import { SymbolCompareChart } from "@/components/kit/symbol-compare-chart";
import { TechLabelsStrip } from "@/components/kit/tech-labels-strip";
import { computeFundamentals } from "@/lib/api/fundamentals";
import {
  closesFromBars,
  computePeriodReturns,
} from "@/lib/api/period-returns";
import { barsFromDaily, computeTechLabels } from "@/lib/api/tech-labels";
import {
  buildDataQualityNotices,
  parseFilingQualitySummary,
  type FilingQualitySummary,
} from "@/lib/data-quality";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { OptionalLwcNote } from "@/components/optional-lwc-note";
import { PageHeader } from "@/components/page-header";
import { MarketSessionChip } from "@/components/market-session-chip";
import { PriceRefresh } from "@/components/price-refresh";
import { ExpandablePriceChart } from "@/components/charts/expandable-price-chart";
import {
  dayChangeScopeLabel,
  normalizeDailyBar,
  type ChartRangeKey,
  type DailyBarPoint,
} from "@/lib/api/daily-bars";
import { isMarketSessionOpen } from "@/lib/market-session";
import { finiteSparklinePoints } from "@/lib/sparkline";
import { Button } from "@/components/ui/button";
import {
  WatchButton,
} from "@/components/watchlist-controls";
import {
  safeFilingHref,
  sanitizeDisclosureCategory,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { serverApiGet } from "@/lib/api/server-fetch";
import { normalizeSymbol, normalizeSymbolParam } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import {
  loadDividendEventsForSymbol,
  type DividendEvent,
} from "@/lib/db/dividend-events";
import {
  loadSymbolPageDisclosures,
  loadSymbolPageEquity,
  loadSymbolPageMetrics,
  loadSymbolPageStock,
} from "@/lib/db/symbol-page-data";
import {
  estimateDividendYieldPct,
  formatDividendDate,
} from "@/lib/dividends";
import {
  formatCompactNumber,
  formatNumber,
  formatPct,
  formatTs,
} from "@/lib/format";

export const dynamic = "force-dynamic";

/** Snapshots older than this are treated as stale for empty-copy (E11-D02). */
const STALE_MS = 24 * 60 * 60 * 1000;
/** Cap sparkline points parse — parity with snapshots API max / sparkline bound. */
const MAX_PAGE_SNAPSHOT_POINTS = 200;

/** ECMAScript Date absolute millisecond bound (parity sparkline / toIso). */
const MAX_DATE_MS = 8.64e15;

function isStaleTs(ts: string | null | undefined): boolean {
  // Fail closed — non-strings / out-of-range must not skew the stale banner.
  if (typeof ts !== "string" || !ts) return false;
  const t = Date.parse(ts);
  if (Number.isNaN(t) || Math.abs(t) > MAX_DATE_MS) return false;
  return Date.now() - t > STALE_MS;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol: raw } = await params;
  // Fail closed — never echo hostile / undecodable raw into <title>.
  const symbol = normalizeSymbolParam(raw) ?? "Symbol";
  return {
    title: `${symbol} · koel`,
    description: `Last price and disclosures for ${symbol}.`,
  };
}

type SymbolPayload = {
  symbol: string;
  name: string | null;
  sector: string | null;
  market_cap: number | null;
  last: {
    price: number;
    change: number | null;
    change_pct: number | null;
    volume: number | null;
    ts: string | null;
  } | null;
};

type SnapshotsPayload = {
  points: { ts: string | null; price: number | null; change_pct: number | null }[];
};

type DisclosuresPayload = {
  items: {
    id: number;
    external_id: string;
    title: string;
    category: string | null;
    url: string | null;
    published_at: string | null;
    company_name: string | null;
    pdf_url: string | null;
    brief: string | null;
    brief_status:
      | "pending"
      | "processing"
      | "ready"
      | "failed"
      | "skipped"
      | null;
  }[];
};

/** Fail-closed snapshots JSON — missing/hostile ``points`` must not 500. */
function parseSnapshotsPayload(body: unknown): SnapshotsPayload {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return { points: [] };
  }
  const pointsRaw = (body as { points?: unknown }).points;
  if (!Array.isArray(pointsRaw)) return { points: [] };
  const points: SnapshotsPayload["points"] = [];
  for (const row of pointsRaw) {
    // Cap at API / sparkline max — unbounded points used to allocate before SVG.
    if (points.length >= MAX_PAGE_SNAPSHOT_POINTS) break;
    if (row == null || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    points.push({
      // Fail-closed ISO — no raw overlong / control-laden ts echo.
      ts: toIso(r.ts),
      price: toFiniteNumber(r.price),
      change_pct: toFiniteNumber(r.change_pct),
    });
  }
  return { points };
}

function latestBriefFromDisclosures(discs: DisclosuresPayload): LatestBrief | null {
  const item = discs.items.find(
    (disc) => disc.brief_status === "ready" && Boolean(disc.brief?.trim()),
  );
  if (!item?.brief) return null;
  return { title: item.title, text: item.brief };
}

function emptyMetricsHintFromQuality(
  quality: FilingQualitySummary | null,
  loadFailed: boolean,
): string | null {
  if (loadFailed || !quality) return null;
  if (quality.metrics_ok === 0 && quality.metrics_failed > 0) {
    return `Extract tried ${quality.metrics_failed} filing PDF${quality.metrics_failed === 1 ? "" : "s"} but could not pull reliable numbers (scanned pages or unusual layouts). This is not proof the company has no results — verify against the source PDF.`;
  }
  if (quality.financial_filings === 0) {
    return "No CSE financial-statement filings are stored for this symbol yet. Warrants, prefs, and some thinly listed names often have none — metrics stay empty until those PDFs exist.";
  }
  if (quality.with_pdf === 0 && quality.disclosures > 0) {
    return "Disclosures are stored, but PDF links are still missing. Metrics appear after PDFs are enriched and parsed.";
  }
  if (quality.metrics_attempted === 0 && quality.with_pdf > 0) {
    return "Financial PDFs are on file; metrics extraction is still pending on the drain schedule.";
  }
  return null;
}

function emptyBriefHintFromQuality(
  quality: FilingQualitySummary | null,
  hasReadyBrief: boolean,
): string | null {
  if (hasReadyBrief || !quality) return null;
  if (quality.briefs_failed > 0 && quality.briefs_ready === 0) {
    return "AI brief generation failed for recent filings (model limits or extract issues). The brief drain retries automatically. Not financial advice.";
  }
  if (quality.briefs_pending > 0) {
    return "An AI brief is pending or processing. Free-tier quotas can lag — ready text shows up after the drain finishes. Not financial advice.";
  }
  if (quality.financial_filings === 0) {
    return "No financial-statement filings to summarize yet for this symbol. Briefs need those PDFs first. Not financial advice.";
  }
  return null;
}

function parseCompareSearchParam(raw: unknown): string[] {
  const text = Array.isArray(raw) ? raw[0] : raw;
  if (typeof text !== "string" || !text.trim()) return [];
  const out: string[] = [];
  for (const part of text.split(",")) {
    const symbol = normalizeSymbol(part);
    if (!symbol || out.includes(symbol)) continue;
    out.push(symbol);
    if (out.length >= 3) break; // base + 3 peers = max 4
  }
  return out;
}

export default async function SymbolDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ symbol: string }>;
  searchParams: Promise<{
    category?: string | string[];
    compare?: string | string[];
    expandChart?: string | string[];
    range?: string | string[];
  }>;
}) {
  await requirePageSession();

  const { symbol: raw } = await params;
  const sp = await searchParams;
  const expandRaw = Array.isArray(sp.expandChart)
    ? sp.expandChart[0]
    : sp.expandChart;
  const expandChart =
    expandRaw === "1" || expandRaw === "true" || expandRaw === "yes";
  const rangeRaw = Array.isArray(sp.range) ? sp.range[0] : sp.range;
  const rangeKey = (rangeRaw ?? "").toUpperCase();
  // Default 3M candles (daily path). 1D only when explicitly requested —
  // intraday needs multiple stored ticks and is no longer the hero gate.
  const initialChartRange: ChartRangeKey =
    rangeKey === "1D" ||
    rangeKey === "1M" ||
    rangeKey === "3M" ||
    rangeKey === "6M" ||
    rangeKey === "1Y"
      ? rangeKey
      : "3M";
  // safeDecode — malformed % sequences → notFound (not URIError 500).
  const symbol = normalizeSymbolParam(raw);
  if (!symbol) {
    notFound();
  }
  const categoryRaw = Array.isArray(sp.category)
    ? sp.category[0]
    : sp.category;
  const categoryFilter = sanitizeDisclosureCategory(categoryRaw);
  const comparePeers = parseCompareSearchParam(sp.compare).filter(
    (peer) => peer !== symbol,
  );

  const encoded = encodeURIComponent(symbol);
  const compareQs =
    comparePeers.length > 0
      ? `/api/v1/compare?symbols=${encodeURIComponent(
          [symbol, ...comparePeers].join(","),
        )}&limit=180`
      : null;

  // Stock / disclosures / metrics: read Postgres directly (Vercel Deployment
  // Protection breaks cookie-bearing self-fetch → empty “No disclosures yet”).
  let data: SymbolPayload | null = null;
  let discs: DisclosuresPayload = { items: [] };
  let filingMetrics: FilingMetricRow | null = null;
  let filingComparison: FilingMetricComparison | null = null;
  let latestBrief: LatestBrief | null = null;
  let filingQuality: FilingQualitySummary | null = null;
  let dividendEvents: DividendEvent[] = [];

  const [stockResult, discResult, metricsResult, equityResult, dividendResult, snapRes, compareRes, watchRes, forecastRes, dailyBarsRes, metricsApiRes] =
    await Promise.all([
      loadSymbolPageStock(symbol)
        .then((row) => ({ ok: true as const, row }))
        .catch(() => ({ ok: false as const, row: null })),
      loadSymbolPageDisclosures(symbol, 20)
        .then((items) => ({ ok: true as const, items }))
        .catch(() => ({
          ok: false as const,
          items: [] as Awaited<ReturnType<typeof loadSymbolPageDisclosures>>,
        })),
      loadSymbolPageMetrics(symbol)
        .then((payload) => ({ ok: true as const, payload }))
        .catch(() => ({ ok: false as const, payload: null })),
      loadSymbolPageEquity(symbol)
        .then((row) => ({ ok: true as const, row }))
        .catch(() => ({ ok: false as const, row: null })),
      loadDividendEventsForSymbol(symbol)
        .then((items) => ({ ok: true as const, items }))
        .catch(() => ({ ok: false as const, items: [] as DividendEvent[] })),
      serverApiGet(`/api/v1/symbols/${encoded}/snapshots?limit=180`),
      compareQs ? serverApiGet(compareQs) : Promise.resolve(null),
      serverApiGet("/api/v1/watchlist"),
      serverApiGet(`/api/v1/symbols/${encoded}/forecast`),
      serverApiGet(`/api/v1/symbols/${encoded}/daily-bars?limit=260`),
      // Quality counters for data-quality banners (API includes `quality`).
      serverApiGet(`/api/v1/symbols/${encoded}/metrics`),
    ]);

  const stockLoadFailed = !stockResult.ok;
  const discsFailed = !discResult.ok;
  const metricsFailed = !metricsResult.ok;

  if (!stockLoadFailed && stockResult.ok && stockResult.row == null) {
    notFound();
  }
  if (stockLoadFailed || !stockResult.ok || !stockResult.row) {
    return (
      <Shell>
        <EmptyState
          title={`Couldn’t load ${symbol}`}
          description={
            <>
              koel couldn’t fetch this symbol from Postgres just now. Check
              your connection, then try again — or open it from your{" "}
              <Link href="/watchlist" className="underline underline-offset-4">
                watchlist
              </Link>
              .
            </>
          }
          action={
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link href={`/symbols/${encoded}`}>Try again</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link href="/watchlist">← Watchlist</Link>
              </Button>
            </div>
          }
        />
      </Shell>
    );
  }

  data = {
    symbol: stockResult.row.symbol,
    name: stockResult.row.name,
    sector: stockResult.row.sector,
    market_cap: stockResult.row.market_cap,
    last:
      stockResult.row.last && stockResult.row.last.price != null
        ? {
            price: stockResult.row.last.price,
            change: stockResult.row.last.change,
            change_pct: stockResult.row.last.change_pct,
            volume: stockResult.row.last.volume,
            ts: stockResult.row.last.ts,
          }
        : null,
  };

  if (discResult.ok) {
    discs = { items: discResult.items };
  }
  if (metricsResult.ok && metricsResult.payload) {
    const latest = metricsResult.payload.items[0] ?? null;
    if (latest) {
      filingMetrics = {
        kind: latest.kind,
        entity: latest.entity,
        currency: latest.currency,
        fiscal_period_end: latest.fiscal_period_end,
        eps_basic: latest.eps_basic,
        revenue: latest.revenue,
        profit: latest.profit,
        extract_ok: latest.extract_ok,
      };
      const cmp = latest.comparison;
      filingComparison =
        cmp &&
        (cmp.match_quality === "exact_yoy" ||
          cmp.match_quality === "approx_yoy")
          ? {
              match_quality: cmp.match_quality,
              eps_delta_pct: cmp.eps_delta_pct,
              revenue_delta_pct: cmp.revenue_delta_pct,
              profit_delta_pct: cmp.profit_delta_pct,
            }
          : cmp
            ? {
                match_quality: null,
                eps_delta_pct: cmp.eps_delta_pct,
                revenue_delta_pct: cmp.revenue_delta_pct,
                profit_delta_pct: cmp.profit_delta_pct,
              }
            : null;
    }
    if (metricsResult.payload.brief) {
      latestBrief = {
        title: metricsResult.payload.brief.title,
        text: metricsResult.payload.brief.text,
      };
    }
  }
  latestBrief ??= latestBriefFromDisclosures(discs);

  if (metricsApiRes.ok) {
    try {
      filingQuality = parseFilingQualitySummary(await metricsApiRes.json());
    } catch {
      filingQuality = null;
    }
  }
  if (dividendResult.ok) {
    dividendEvents = dividendResult.items;
  }

  let snaps: SnapshotsPayload = { points: [] };
  let isWatching = false;
  if (watchRes.ok) {
    try {
      const body: unknown = await watchRes.json();
      const items =
        body && typeof body === "object" && !Array.isArray(body)
          ? (body as { items?: unknown }).items
          : null;
      if (Array.isArray(items)) {
        for (const row of items) {
          if (!row || typeof row !== "object" || Array.isArray(row)) continue;
          const rowSym = normalizeSymbol(
            (row as { symbol?: unknown }).symbol,
          );
          if (rowSym === symbol) {
            isWatching = true;
            break;
          }
        }
      }
    } catch {
      isWatching = false;
    }
  }
  let comparePeerSeries: {
    symbol: string;
    points: { ts: string | null; price: number }[];
  }[] = [];
  if (snapRes.ok) {
    try {
      snaps = parseSnapshotsPayload(await snapRes.json());
    } catch {
      snaps = { points: [] };
    }
  }
  if (compareRes?.ok) {
    try {
      const body: unknown = await compareRes.json();
      if (body && typeof body === "object" && !Array.isArray(body)) {
        const rawSeries = (body as { series?: unknown }).series;
        if (Array.isArray(rawSeries)) {
          for (const row of rawSeries) {
            if (!row || typeof row !== "object" || Array.isArray(row)) continue;
            const r = row as Record<string, unknown>;
            const peer = normalizeSymbol(r.symbol);
            if (!peer || peer === symbol) continue;
            const pointsRaw = Array.isArray(r.points) ? r.points : [];
            const points = pointsRaw.flatMap((p) => {
              if (!p || typeof p !== "object" || Array.isArray(p)) return [];
              const point = p as Record<string, unknown>;
              const price = toFiniteNumber(point.price);
              if (price == null) return [];
              return [
                {
                  ts: typeof point.ts === "string" ? point.ts : null,
                  price,
                },
              ];
            });
            comparePeerSeries.push({ symbol: peer, points });
            if (comparePeerSeries.length >= 3) break;
          }
        }
      }
    } catch {
      comparePeerSeries = [];
    }
  }

  const snapsFailed = !snapRes.ok;

  const initialDailyBars: DailyBarPoint[] = [];
  if (dailyBarsRes?.ok) {
    try {
      const body: unknown = await dailyBarsRes.json();
      const raw =
        body != null &&
        typeof body === "object" &&
        !Array.isArray(body) &&
        Array.isArray((body as { bars?: unknown }).bars)
          ? (body as { bars: unknown[] }).bars
          : [];
      for (const row of raw) {
        if (row == null || typeof row !== "object" || Array.isArray(row)) {
          continue;
        }
        const normalized = normalizeDailyBar(
          row as {
            trade_date: unknown;
            open?: unknown;
            high?: unknown;
            low?: unknown;
            price?: unknown;
            close?: unknown;
            volume?: unknown;
          },
        );
        if (normalized) initialDailyBars.push(normalized);
      }
    } catch {
      // leave empty — expand dialog can client-fetch
    }
  }

  const periodReturns = computePeriodReturns(
    closesFromBars(initialDailyBars),
    initialDailyBars,
  );
  const techLabels = computeTechLabels(barsFromDaily(initialDailyBars));
  const quote = data;
  const fundamentals = computeFundamentals({
    equity:
      equityResult.ok && equityResult.row
        ? {
            equity: equityResult.row.equity,
            equity_scale: equityResult.row.equity_scale,
            equity_confidence: equityResult.row.equity_confidence,
            equity_as_of: equityResult.row.equity_as_of,
            equity_currency: equityResult.row.equity_currency,
          }
        : null,
    lastPrice: quote?.last?.price ?? null,
    marketCap: quote?.market_cap ?? null,
    profit: filingMetrics?.profit ?? null,
  });
  const latestDividendEvent =
    dividendEvents.find((event) => event.dps != null) ?? null;
  const dividendYieldPct = estimateDividendYieldPct(
    latestDividendEvent?.dps ?? null,
    quote?.last?.price ?? null,
  );

  const forecastPoints: { ts: string | null; price: number | null }[] = [];
  let forecastConfidence: number | null = null;
  let forecastBand: string | null = null;
  let forecastGate: string | null = null;
  if (forecastRes?.ok) {
    try {
      const body: unknown = await forecastRes.json();
      if (
        body != null &&
        typeof body === "object" &&
        !Array.isArray(body) &&
        Array.isArray((body as { points?: unknown }).points)
      ) {
        const meta = body as {
          confidence?: unknown;
          confidence_band?: unknown;
          gate?: unknown;
          points: unknown[];
        };
        forecastConfidence = toFiniteNumber(meta.confidence);
        forecastBand =
          typeof meta.confidence_band === "string" ? meta.confidence_band : null;
        forecastGate = typeof meta.gate === "string" ? meta.gate : null;
        for (const row of meta.points) {
          if (forecastPoints.length >= 30) break;
          if (row == null || typeof row !== "object" || Array.isArray(row)) {
            continue;
          }
          const r = row as Record<string, unknown>;
          const price = toFiniteNumber(r.price);
          if (price == null) continue;
          forecastPoints.push({
            ts: typeof r.ts === "string" ? r.ts : null,
            price,
          });
        }
      }
    } catch {
      // leave empty — sparkline stays realtime-only
    }
  }

  const sparkPoints = finiteSparklinePoints(snaps.points);
  const marketOpen = isMarketSessionOpen();
  const marketClosed = !marketOpen;
  const ageStale = Boolean(data.last?.ts && isStaleTs(data.last.ts));
  // Age-stale during closed hours is expected quiet — only alarm when open.
  const snapshotStale = ageStale && marketOpen;
  const qualityNotices = buildDataQualityNotices({
    symbol: data.symbol,
    hasLastPrice: Boolean(data.last),
    snapshotStale,
    marketClosed: marketClosed && Boolean(data.last),
    sparkPointCount: sparkPoints.length,
    quality: filingQuality,
    metricsLoadFailed: metricsFailed,
    hasReadyBrief: Boolean(latestBrief),
    hasReadyMetrics: Boolean(filingMetrics?.extract_ok),
  });
  const emptyMetricsHint = emptyMetricsHintFromQuality(
    filingQuality,
    metricsFailed,
  );
  const emptyBriefHint = emptyBriefHintFromQuality(
    filingQuality,
    Boolean(latestBrief),
  );
  const disclosureCategories = Array.from(
    new Set(
      discs.items
        .map((item) => item.category)
        .filter((category): category is string => Boolean(category)),
    ),
  ).sort((a, b) => a.localeCompare(b));
  const visibleDisclosures = categoryFilter
    ? discs.items.filter((item) => item.category === categoryFilter)
    : discs.items;

  return (
    <Shell>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
        <PageHeader
          className="min-w-0 flex-1"
          eyebrow="Symbol"
          title={data.symbol}
          description={
            data.name
              ? `${data.name}${data.sector ? ` · ${data.sector}` : ""}`
              : undefined
          }
        />
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          <MarketSessionChip />
          <PriceRefresh lastSnapshotAt={data.last?.ts ?? null} />
          <WatchButton symbol={data.symbol} watching={isWatching} />
          <Button asChild variant="outline" size="sm">
            <Link href={`/alerts?symbol=${encoded}`}>New alert</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href={`/dividends?symbol=${encoded}`}>Dividends</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href={`/graph?symbol=${encoded}`}>Ownership map</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/people">People</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/watchlist">← Watchlist</Link>
          </Button>
        </div>
      </div>

      <DataQualityNotices notices={qualityNotices} />

      <section
        aria-label="Last price"
        className={`mt-6 overflow-hidden rounded-xl border ${
          snapshotStale
            ? "border-amber-500/40 bg-amber-500/5"
            : marketClosed && data.last
              ? "border-slate-300/70 bg-slate-500/5"
              : "border-border/70"
        }`}
      >
        <div className="flex flex-col gap-5 p-5 sm:p-6">
          <div className="flex min-w-0 flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Last price
                {snapshotStale
                  ? " · stale"
                  : marketClosed && data.last
                    ? " · market closed"
                    : ""}
              </p>
              {data.last ? (
                <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span
                    className={`font-mono text-4xl font-semibold tracking-tight tabular-nums ${
                      snapshotStale || marketClosed
                        ? "text-muted-foreground"
                        : ""
                    }`}
                  >
                    {formatNumber(data.last.price)}
                  </span>
                  <SignedChange
                    change={data.last.change}
                    changePct={data.last.change_pct}
                    asOfTs={data.last.ts}
                  />
                </div>
              ) : (
                <p className="mt-1 text-sm text-muted-foreground">
                  No stored price yet.
                </p>
              )}
              {data.last?.ts ? (
                <p className="mt-1.5 text-xs text-muted-foreground">
                  As of {formatTs(data.last.ts)} (SLT)
                  {snapshotStale
                    ? " — more than a day old; poller may be paused."
                    : marketClosed
                      ? " — last print; session closed until next weekday open."
                      : ""}
                </p>
              ) : null}
            </div>
          </div>

          <div className="min-w-0 w-full">
            {initialDailyBars.length >= 2 || sparkPoints.length >= 2 ? (
              <ExpandablePriceChart
                symbol={data.symbol}
                points={snaps.points}
                forecastPoints={forecastPoints}
                confidence={forecastConfidence}
                confidenceBand={forecastBand}
                gate={forecastGate}
                initialOpen={expandChart}
                initialBars={initialDailyBars}
                initialRange={initialChartRange}
                className="w-full max-w-none"
              />
            ) : snapsFailed ? (
              <p className="text-sm text-muted-foreground" role="status">
                Couldn’t load chart data right now.
              </p>
            ) : (
              <p className="text-sm text-muted-foreground" role="status">
                No daily path history yet. After path-backfill lands, candles
                show here.
              </p>
            )}
            <OptionalLwcNote
              enabled={process.env.NEXT_PUBLIC_KOEL_LWC === "1"}
            />
          </div>
        </div>
        {data.last ? (
          <dl
            className={`grid grid-cols-2 gap-px border-t border-border/60 bg-border/40 ${
              data.market_cap != null ? "sm:grid-cols-3" : ""
            }`}
          >
            <Stat
              label="Prev close"
              value={
                data.last.change == null
                  ? "—"
                  : formatNumber(data.last.price - data.last.change)
              }
              mono
            />
            <Stat
              label="Volume"
              value={
                data.last.volume == null
                  ? "—"
                  : formatNumber(Math.round(data.last.volume), 0)
              }
              mono
            />
            {data.market_cap != null ? (
              <Stat
                label="Market cap"
                value={formatCompactNumber(data.market_cap)}
                mono
                className="col-span-2 sm:col-span-1"
              />
            ) : null}
          </dl>
        ) : null}
        <PeriodReturnsStrip returns={periodReturns} />
        <TechLabelsStrip labels={techLabels} />
        <FilingSnapshotStrip
          epsBasic={filingMetrics?.eps_basic ?? null}
          currency={filingMetrics?.currency ?? null}
          comparison={filingComparison}
        />
        <FundamentalsStrip labels={fundamentals} />
        {latestDividendEvent?.dps != null ? (
          <DividendYieldStrip
            symbol={data.symbol}
            dps={latestDividendEvent.dps}
            yieldPct={dividendYieldPct}
            xd={latestDividendEvent.d_xd}
            pay={latestDividendEvent.d_pay}
          />
        ) : null}
      </section>

      {!data.last ? (
        <EmptyState
          className="mt-4"
          title="No snapshot yet"
          description={
            <>
              koel hasn’t stored a price tick for {data.symbol}. During
              market hours (09:30–14:30 SLT, weekdays) the poller writes
              snapshots here. Outside those hours this stays empty until the
              next session. Not financial advice.
            </>
          }
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/alerts">Set an alert</Link>
            </Button>
          }
        />
      ) : null}
      {data.last && marketClosed ? (
        <EmptyState
          className="mt-4"
          title="Market closed"
          description={
            <>
              CSE cash session is closed (09:30–14:30 SLT, weekdays). Last
              print was {formatTs(data.last.ts)} (SLT). Fresh ticks resume
              next session if this symbol is watched. Not financial advice.
            </>
          }
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/watchlist">Back to watchlist</Link>
            </Button>
          }
        />
      ) : null}
      {data.last && snapshotStale ? (
        <EmptyState
          className="mt-4"
          title="Snapshot looks stale"
          description={
            <>
              Last tick was {formatTs(data.last.ts)} (SLT) — more than a day
              ago while the session is open. The poller may be paused or this
              symbol wasn’t watched. Not financial advice.
            </>
          }
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/watchlist">Back to watchlist</Link>
            </Button>
          }
        />
      ) : null}
      <NfaInline className="mt-3" />

      <SymbolCompareChart
        baseSymbol={data.symbol}
        initialPoints={snaps.points}
        initialPeerSeries={comparePeerSeries}
      />

      <FilingMetricsPanel
        metrics={filingMetrics}
        comparison={filingComparison}
        latestBrief={latestBrief}
        loadFailed={metricsFailed}
        emptyMetricsHint={emptyMetricsHint}
        emptyBriefHint={emptyBriefHint}
      />

      <section
        className="mt-8 border-t border-border/60 pt-6"
        aria-labelledby="disclosures-heading"
      >
        <h2
          id="disclosures-heading"
          className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
        >
          Disclosures
        </h2>
        {!discsFailed && disclosureCategories.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <DisclosureCategoryHint
              href={`/symbols/${encoded}`}
              label="All"
              selected={!categoryFilter}
            />
            {disclosureCategories.map((category) => (
              <DisclosureCategoryHint
                key={category}
                href={`/symbols/${encoded}?category=${encodeURIComponent(category)}`}
                label={category}
                selected={categoryFilter === category}
              />
            ))}
          </div>
        ) : null}
        {discsFailed ? (
          <EmptyState
            className="mt-4"
            title="Couldn’t load disclosures"
            description={
              <>
                koel couldn’t read stored filings for{" "}
                <code className="font-mono text-xs">{data.symbol}</code> just
                now. Check your connection, then try again — this is not an
                empty list.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link href={`/symbols/${encoded}`}>Try again</Link>
              </Button>
            }
          />
        ) : visibleDisclosures.length === 0 ? (
          <EmptyState
            className="mt-4"
            title={categoryFilter ? `No ${categoryFilter} disclosures` : "No disclosures yet"}
            description={
              <>
                Nothing stored for{" "}
                <code className="font-mono text-xs">{data.symbol}</code>. When
                the poller sees a new CSE announcement, it lists here with a
                link to the source. Or set{" "}
                <code className="font-mono text-xs">
                  /alert {data.symbol} disclosure
                </code>{" "}
                in Telegram to get pinged.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link
                  href={`/alerts?symbol=${encodeURIComponent(data.symbol)}&type=disclosure`}
                >
                  Alert on disclosures
                </Link>
              </Button>
            }
          />
        ) : (
          <>
            <DisclosureTimeline
              items={visibleDisclosures.map((item) => ({
                id: item.id,
                title: item.title,
                published_at: item.published_at,
                url: safeFilingHref(item.pdf_url, item.url),
                category: item.category,
                brief: item.brief,
                brief_status: item.brief_status,
              }))}
              className="mt-5"
            />
            <NfaInline className="mt-3" />
          </>
        )}
      </section>
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border/70 bg-background/95 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-lg backdrop-blur md:hidden">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
          <WatchButton symbol={data.symbol} watching={isWatching} />
          <Button asChild className="flex-1" size="sm">
            <Link href={`/alerts?symbol=${encoded}`}>New alert</Link>
          </Button>
        </div>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 pt-8 pb-24 sm:px-6 sm:pt-10 md:pb-10"
      >
        {children}
      </main>
      <NfaFooter />
    </div>
  );
}

/** Label/value cell inside the quote card's hairline-divided stat strip. */
function Stat({
  label,
  value,
  className,
  mono,
}: {
  label: string;
  value: string;
  className?: string;
  mono?: boolean;
}) {
  return (
    <div className={`min-w-0 bg-background px-4 py-3 ${className ?? ""}`}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={`mt-0.5 truncate text-lg font-medium tabular-nums ${mono ? "font-mono" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}

function DividendYieldStrip({
  symbol,
  dps,
  yieldPct,
  xd,
  pay,
}: {
  symbol: string;
  dps: number;
  yieldPct: number | null;
  xd: string | null;
  pay: string | null;
}) {
  return (
    <div
      className="flex flex-wrap items-center gap-2 border-t border-border/50 px-5 py-3 sm:px-6"
      aria-label="Dividend event yield"
    >
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Dividend
      </span>
      <span className="text-xs text-muted-foreground">
        DPS{" "}
        <span className="font-mono tabular-nums text-foreground">
          {formatNumber(dps)} LKR
        </span>
      </span>
      <span className="text-xs text-muted-foreground">
        Event yield{" "}
        <span className="font-mono tabular-nums text-foreground">
          {yieldPct != null ? formatPct(yieldPct) : "—"}
        </span>
      </span>
      {xd ? (
        <span className="text-xs text-muted-foreground">
          XD{" "}
          <span className="font-mono tabular-nums text-foreground">
            {formatDividendDate(xd)}
          </span>
        </span>
      ) : null}
      {pay ? (
        <span className="text-xs text-muted-foreground">
          Pay{" "}
          <span className="font-mono tabular-nums text-foreground">
            {formatDividendDate(pay)}
          </span>
        </span>
      ) : null}
      <Link
        href={`/dividends?symbol=${encodeURIComponent(symbol)}`}
        className="text-xs text-muted-foreground underline-offset-4 hover:underline"
      >
        Calculator
      </Link>
      <Link
        href={`/alerts?symbol=${encodeURIComponent(symbol)}&type=xd_soon`}
        className="text-xs text-muted-foreground underline-offset-4 hover:underline"
      >
        XD alert
      </Link>
    </div>
  );
}

/** Inline signed change next to the big price — `+0.50 (+2.35%)`, colored. */
function SignedChange({
  change,
  changePct,
  asOfTs,
}: {
  change: number | null;
  changePct: number | null;
  /** Snapshot stamp — drives today vs prior-session scope label. */
  asOfTs: string | null;
}) {
  const direction =
    changePct != null && changePct > 0
      ? "up"
      : changePct != null && changePct < 0
        ? "down"
        : change != null && change > 0
          ? "up"
          : change != null && change < 0
            ? "down"
            : "flat";
  const tone =
    direction === "up"
      ? "text-emerald-700 dark:text-emerald-400"
      : direction === "down"
        ? "text-rose-700 dark:text-rose-400"
        : "text-muted-foreground";
  const changeLabel =
    change == null
      ? null
      : `${change > 0 ? "+" : ""}${formatNumber(change)}`;
  const pctLabel = changePct == null ? null : formatPct(changePct);
  if (changeLabel == null && pctLabel == null) return null;
  const scope = dayChangeScopeLabel(asOfTs);
  return (
    <span className={`font-mono text-lg font-medium tabular-nums ${tone}`}>
      <span className="sr-only">
        {direction === "up" ? "up " : direction === "down" ? "down " : ""}
      </span>
      {changeLabel ?? ""}
      {pctLabel ? `${changeLabel != null ? " " : ""}(${pctLabel})` : ""}
      <span
        className="ml-1.5 font-sans text-xs font-normal text-muted-foreground"
        title={
          scope === "today"
            ? "Change vs previous close for today's session"
            : "Change vs previous close for that session (market may be closed)"
        }
      >
        {scope}
      </span>
    </span>
  );
}
