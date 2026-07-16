import Link from "next/link";
import { notFound } from "next/navigation";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { ChangeBadge } from "@/components/kit/change-badge";
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
import { SymbolCompareChart } from "@/components/kit/symbol-compare-chart";
import {
  buildDataQualityNotices,
  parseFilingQualitySummary,
  type FilingQualitySummary,
} from "@/lib/data-quality";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { OptionalLwcNote } from "@/components/optional-lwc-note";
import { PageHeader } from "@/components/page-header";
import { PriceRefresh } from "@/components/price-refresh";
import { Sparkline } from "@/components/sparkline";
import { finiteSparklinePoints } from "@/lib/sparkline";
import { Button } from "@/components/ui/button";
import {
  WatchButton,
} from "@/components/watchlist-controls";
import {
  MAX_DISCLOSURE_CATEGORY_LENGTH,
  MAX_DISCLOSURE_COMPANY_LENGTH,
  MAX_DISCLOSURE_EXTERNAL_ID_LENGTH,
  MAX_DISCLOSURE_TITLE_LENGTH,
  MAX_STOCK_NAME_LENGTH,
  MAX_STOCK_SECTOR_LENGTH,
  normalizeBriefStatus,
  safeAnnouncementUrl,
  safeFilingHref,
  safePdfUrl,
  sanitizeBriefText,
  sanitizeDisclosureCategory,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { serverApiGet } from "@/lib/api/server-fetch";
import { normalizeSymbol, normalizeSymbolParam } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import { Suspense } from "react";

import { SparklineTicksControl } from "@/components/kit/sparkline-ticks-control";
import { formatNumber, formatTs } from "@/lib/format";
import {
  DEFAULT_SPARKLINE_TICKS,
  parseSparklineTicks,
} from "@/lib/sparkline-ticks";

export const dynamic = "force-dynamic";

/** Snapshots older than this are treated as stale for empty-copy (E11-D02). */
const STALE_MS = 24 * 60 * 60 * 1000;
/** Cap sparkline points parse — parity with snapshots API max / sparkline bound. */
const MAX_PAGE_SNAPSHOT_POINTS = 500;
/** Cap disclosures parse — parity with disclosures API max 100. */
const MAX_PAGE_DISCLOSURES = 100;
/** Short filing metric labels; never echo arbitrary long extraction text. */
const MAX_METRIC_KIND_LENGTH = 32;
const MAX_METRIC_ENTITY_LENGTH = 128;
const MAX_METRIC_CURRENCY_LENGTH = 16;

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
    title: `${symbol} · Chime`,
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

/** Fail-closed symbol JSON — never cast the body to SymbolPayload. */
function parseSymbolPayload(body: unknown): SymbolPayload | null {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const r = body as Record<string, unknown>;
  // Fail closed — only CSE SYMBOL_RE (no sanitize length-cap fallback).
  const symbol = normalizeSymbol(r.symbol);
  if (!symbol) return null;
  let last: SymbolPayload["last"] = null;
  if (r.last != null && typeof r.last === "object" && !Array.isArray(r.last)) {
    const L = r.last as Record<string, unknown>;
    const price = toFiniteNumber(L.price);
    // Require a finite price — null-only last stubs confuse the quote strip.
    if (price != null) {
      last = {
        price,
        change: toFiniteNumber(L.change),
        change_pct: toFiniteNumber(L.change_pct),
        volume: toFiniteNumber(L.volume),
        // Fail-closed ISO — no raw overlong / control-laden ts echo.
        ts: toIso(L.ts),
      };
    }
  }
  return {
    symbol,
    name: sanitizeDisclosureText(
      typeof r.name === "string" ? r.name : null,
      MAX_STOCK_NAME_LENGTH,
    ),
    sector: sanitizeDisclosureText(
      typeof r.sector === "string" ? r.sector : null,
      MAX_STOCK_SECTOR_LENGTH,
    ),
    market_cap: toFiniteNumber(r.market_cap),
    last,
  };
}

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

/** Fail-closed disclosures JSON — SafeInteger ids + sanitized text/urls. */
function parseDisclosuresPayload(body: unknown): DisclosuresPayload {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return { items: [] };
  }
  const itemsRaw = (body as { items?: unknown }).items;
  if (!Array.isArray(itemsRaw)) return { items: [] };
  const items: DisclosuresPayload["items"] = [];
  for (const row of itemsRaw) {
    if (items.length >= MAX_PAGE_DISCLOSURES) break;
    if (row == null || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const id = toSafePositiveInt(r.id);
    if (id == null) continue;
    const title =
      sanitizeDisclosureText(
        typeof r.title === "string" ? r.title : null,
        MAX_DISCLOSURE_TITLE_LENGTH,
      ) ?? "";
    if (!title) continue;
    const external_id =
      sanitizeDisclosureText(
        typeof r.external_id === "string" ? r.external_id : null,
        MAX_DISCLOSURE_EXTERNAL_ID_LENGTH,
      ) ?? "";
    const brief_status = normalizeBriefStatus(
      typeof r.brief_status === "string" ? r.brief_status : null,
    );
    const publishedRaw = r.published_at;
    // Parse-time allowlist — never soft-accept raw javascript:/data: hrefs
    // or brief text before render (defense in depth vs API shape drift).
    const url =
      typeof r.url === "string" ? safeAnnouncementUrl(r.url) : null;
    const pdf_url =
      typeof r.pdf_url === "string" ? safePdfUrl(r.pdf_url) : null;
    const briefRaw = typeof r.brief === "string" ? r.brief : null;
    items.push({
      id,
      external_id,
      title,
      category: sanitizeDisclosureText(
        typeof r.category === "string" ? r.category : null,
        MAX_DISCLOSURE_CATEGORY_LENGTH,
      ),
      url,
      // Fail-closed ISO — no raw overlong / control-laden ts echo.
      published_at: toIso(publishedRaw),
      company_name: sanitizeDisclosureText(
        typeof r.company_name === "string" ? r.company_name : null,
        MAX_DISCLOSURE_COMPANY_LENGTH,
      ),
      pdf_url,
      brief: sanitizeBriefText(briefRaw, brief_status),
      brief_status,
    });
  }
  return { items };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === "object" && !Array.isArray(value);
}

function firstRecord(value: unknown): Record<string, unknown> | null {
  if (isRecord(value)) return value;
  if (!Array.isArray(value)) return null;
  for (const item of value) {
    if (isRecord(item)) return item;
  }
  return null;
}

function normalizeMetricText(raw: unknown, maxLen: number): string | null {
  return sanitizeDisclosureText(typeof raw === "string" ? raw : null, maxLen);
}

function parseMetricRow(raw: unknown): FilingMetricRow | null {
  if (!isRecord(raw)) return null;
  const eps_basic = toFiniteNumber(raw.eps_basic);
  const revenue = toFiniteNumber(raw.revenue);
  const profit = toFiniteNumber(raw.profit ?? raw.profit_after_tax);
  const hasMetric = eps_basic != null || revenue != null || profit != null;
  if (!hasMetric && raw.extract_ok !== true) return null;

  return {
    kind: normalizeMetricText(raw.kind, MAX_METRIC_KIND_LENGTH),
    entity: normalizeMetricText(raw.entity, MAX_METRIC_ENTITY_LENGTH),
    currency: normalizeMetricText(raw.currency, MAX_METRIC_CURRENCY_LENGTH),
    fiscal_period_end: toIso(raw.fiscal_period_end),
    eps_basic,
    revenue,
    profit,
    extract_ok: raw.extract_ok === true,
  };
}

function parseMetricComparison(raw: unknown): FilingMetricComparison | null {
  if (!isRecord(raw)) return null;
  const matchRaw =
    typeof raw.match_quality === "string" ? raw.match_quality : null;
  const match_quality =
    matchRaw === "exact_yoy" || matchRaw === "approx_yoy" ? matchRaw : null;
  return {
    match_quality,
    eps_delta_pct: toFiniteNumber(raw.eps_delta_pct),
    revenue_delta_pct: toFiniteNumber(raw.revenue_delta_pct),
    profit_delta_pct: toFiniteNumber(raw.profit_delta_pct),
  };
}

function parseMetricsPayload(body: unknown): {
  metrics: FilingMetricRow | null;
  comparison: FilingMetricComparison | null;
} {
  if (!isRecord(body)) return { metrics: null, comparison: null };
  const latestRaw =
    body.latest ??
    body.metric ??
    body.filing_metric ??
    body.item ??
    firstRecord(body.items) ??
    firstRecord(body.metrics);
  const latest = isRecord(latestRaw) ? latestRaw : null;
  const metrics = parseMetricRow(latest ?? body);
  const comparisonRaw =
    (latest && latest.comparison) ??
    body.comparison ??
    body.latest_comparison ??
    body.filing_comparison;
  return {
    metrics,
    comparison: parseMetricComparison(comparisonRaw),
  };
}

function parseLatestBriefPayload(body: unknown): LatestBrief | null {
  if (!isRecord(body)) return null;
  const candidateRaw =
    (isRecord(body.brief) && body.brief) ||
    (isRecord(body.latest_brief) && body.latest_brief) ||
    (isRecord(body.item) && body.item) ||
    body;
  const candidate = isRecord(candidateRaw) ? candidateRaw : null;
  if (!candidate) return null;

  const statusRaw = candidate.status ?? candidate.brief_status;
  const status =
    typeof statusRaw === "string" ? normalizeBriefStatus(statusRaw) : null;
  if (statusRaw != null && status !== "ready") return null;

  const title = sanitizeDisclosureText(
    typeof candidate.title === "string"
      ? candidate.title
      : typeof candidate.disclosure_title === "string"
        ? candidate.disclosure_title
        : null,
    MAX_DISCLOSURE_TITLE_LENGTH,
  );
  const textRaw = candidate.text ?? candidate.brief;
  const text = sanitizeBriefText(textRaw, "ready");
  if (!title || !text) return null;
  return { title, text };
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
    ticks?: string | string[];
  }>;
}) {
  await requirePageSession();

  const { symbol: raw } = await params;
  const sp = await searchParams;
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
  const tickLimit = parseSparklineTicks(sp.ticks);

  const encoded = encodeURIComponent(symbol);
  const compareQs =
    comparePeers.length > 0
      ? `/api/v1/compare?symbols=${encodeURIComponent(
          [symbol, ...comparePeers].join(","),
        )}&limit=${tickLimit}`
      : null;
  const [symRes, snapRes, discRes, metricsRes, briefRes, compareRes, watchRes] =
    await Promise.all([
      serverApiGet(`/api/v1/symbols/${encoded}`),
      serverApiGet(
        `/api/v1/symbols/${encoded}/snapshots?limit=${tickLimit}`,
      ),
      serverApiGet(`/api/v1/symbols/${encoded}/disclosures?limit=20`),
      serverApiGet(`/api/v1/symbols/${encoded}/metrics`),
      serverApiGet(`/api/v1/symbols/${encoded}/brief`),
      compareQs ? serverApiGet(compareQs) : Promise.resolve(null),
      serverApiGet("/api/v1/watchlist"),
    ]);

  if (symRes.status === 404) {
    notFound();
  }
  if (!symRes.ok) {
    return (
      <Shell>
        <EmptyState
          title={`Couldn’t load ${symbol}`}
          description={
            <>
              Chime couldn’t fetch this symbol from Postgres just now. Check
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

  let data: SymbolPayload | null = null;
  try {
    data = parseSymbolPayload(await symRes.json());
  } catch {
    data = null;
  }
  if (!data) {
    return (
      <Shell>
        <EmptyState
          title={`Couldn’t load ${symbol}`}
          description="Chime got an unexpected symbol payload. Retry in a moment."
          action={
            <Button asChild variant="outline">
              <Link href={`/symbols/${encoded}`}>Try again</Link>
            </Button>
          }
        />
      </Shell>
    );
  }

  let snaps: SnapshotsPayload = { points: [] };
  let discs: DisclosuresPayload = { items: [] };
  let filingMetrics: FilingMetricRow | null = null;
  let filingComparison: FilingMetricComparison | null = null;
  let latestBrief: LatestBrief | null = null;
  let filingQuality: FilingQualitySummary | null = null;
  const metricsFailed = !metricsRes.ok;
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
        const raw = (body as { series?: unknown }).series;
        if (Array.isArray(raw)) {
          for (const row of raw) {
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
  if (discRes.ok) {
    try {
      discs = parseDisclosuresPayload(await discRes.json());
    } catch {
      discs = { items: [] };
    }
  }
  if (metricsRes.ok) {
    try {
      const metricsBody: unknown = await metricsRes.json();
      const parsed = parseMetricsPayload(metricsBody);
      filingMetrics = parsed.metrics;
      filingComparison = parsed.comparison;
      latestBrief = parseLatestBriefPayload(metricsBody);
      filingQuality = parseFilingQualitySummary(metricsBody);
    } catch {
      filingMetrics = null;
      filingComparison = null;
      latestBrief = null;
      filingQuality = null;
    }
  }
  if (!latestBrief && briefRes.ok) {
    try {
      latestBrief = parseLatestBriefPayload(await briefRes.json());
    } catch {
      latestBrief = null;
    }
  }
  latestBrief ??= latestBriefFromDisclosures(discs);

  const snapsFailed = !snapRes.ok;
  const discsFailed = !discRes.ok;

  const sparkPoints = finiteSparklinePoints(snaps.points);
  const snapshotStale = Boolean(data.last?.ts && isStaleTs(data.last.ts));
  const qualityNotices = buildDataQualityNotices({
    symbol: data.symbol,
    hasLastPrice: Boolean(data.last),
    snapshotStale,
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
          <PriceRefresh lastSnapshotAt={data.last?.ts ?? null} />
          <WatchButton symbol={data.symbol} watching={isWatching} />
          <Button asChild variant="outline" size="sm">
            <Link href={`/alerts?symbol=${encoded}`}>New alert</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/watchlist">← Watchlist</Link>
          </Button>
        </div>
      </div>

      <DataQualityNotices notices={qualityNotices} />

      <section
        className={`mt-6 rounded-lg border p-4 ${
          snapshotStale
            ? "border-amber-500/40 bg-amber-500/5"
            : "border-border/70"
        }`}
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Last price
              {snapshotStale ? " · stale" : ""}
            </p>
            {data.last ? (
              <div className="mt-1 flex flex-wrap items-center gap-3">
                <span
                  className={`font-mono text-3xl font-semibold tracking-tight tabular-nums ${
                    snapshotStale ? "text-muted-foreground" : ""
                  }`}
                >
                  {formatNumber(data.last.price)}
                </span>
                <ChangeBadge changePct={data.last.change_pct} />
              </div>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">
                No stored price yet.
              </p>
            )}
            {data.last?.ts ? (
              <p className="mt-1 text-xs text-muted-foreground">
                As of {formatTs(data.last.ts)} (SLT)
                {snapshotStale
                  ? " — more than a day old; poller may be paused."
                  : ""}
              </p>
            ) : null}
          </div>
          <div className="min-h-20 min-w-0 flex-1 md:max-w-sm">
            <Suspense
              fallback={
                <p className="mb-2 text-xs text-muted-foreground">
                  Ticks {tickLimit === DEFAULT_SPARKLINE_TICKS ? "" : tickLimit}
                </p>
              }
            >
              <SparklineTicksControl value={tickLimit} className="mb-2" />
            </Suspense>
            {snapsFailed ? (
              <p className="text-sm text-muted-foreground" role="status">
                Couldn’t load recent ticks right now.
              </p>
            ) : sparkPoints.length < 2 ? (
              <p className="text-sm text-muted-foreground">
                Need two stored ticks for a sparkline.
              </p>
            ) : (
              <Sparkline points={snaps.points} />
            )}
            <OptionalLwcNote
              enabled={process.env.NEXT_PUBLIC_CHIME_LWC === "1"}
            />
          </div>
        </div>
      </section>

      <section className="mt-8 border-t border-border/60 pt-6">
        <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          Last snapshot
        </h2>
        {data.last ? (
          <div
            className={`mt-3 grid grid-cols-2 gap-4 ${
              data.market_cap != null ? "sm:grid-cols-5" : "sm:grid-cols-4"
            }`}
          >
            <Stat label="Price" value={formatNumber(data.last.price)} mono />
            <Stat
              label="Change"
              value={formatNumber(data.last.change)}
              mono
            />
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">Change %</p>
              <div className="mt-1">
                <ChangeBadge changePct={data.last.change_pct} />
              </div>
            </div>
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
                value={formatNumber(data.market_cap)}
                mono
              />
            ) : null}
          </div>
        ) : (
          <EmptyState
            className="mt-4"
            title="No snapshot yet"
            description={
              <>
                Chime hasn’t stored a price tick for {data.symbol}. During
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
        )}
        {data.last && isStaleTs(data.last.ts) ? (
          <EmptyState
            className="mt-4"
            title="Snapshot looks stale"
            description={
              <>
                Last tick was {formatTs(data.last.ts)} (SLT) — more than a day
                ago. If market hours have passed without a refresh, the poller
                may be paused or this symbol wasn’t watched. Not financial
                advice.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link href="/watchlist">Back to watchlist</Link>
              </Button>
            }
          />
        ) : null}
        {data.last?.ts && !isStaleTs(data.last.ts) ? (
          <p className="mt-3 text-xs text-muted-foreground">
            As of {formatTs(data.last.ts)} (SLT)
          </p>
        ) : null}
        <NfaInline className="mt-2" />
      </section>

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
                Chime couldn’t read stored filings for{" "}
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
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={`mt-0.5 truncate text-lg font-medium sm:text-xl ${mono ? "font-mono" : ""} ${className ?? ""}`}
      >
        {value}
      </p>
    </div>
  );
}
