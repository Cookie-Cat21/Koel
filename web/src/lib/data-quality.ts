/**
 * User-facing data-quality notices for symbol pages.
 * Pure helpers — no I/O. Keeps “why is this empty?” honest and actionable.
 */

export type DataQualityTone = "info" | "warning" | "danger";

export type DataQualityNotice = {
  id: string;
  tone: DataQualityTone;
  title: string;
  description: string;
};

export type FilingQualitySummary = {
  metrics_attempted: number;
  metrics_ok: number;
  metrics_failed: number;
  disclosures: number;
  with_pdf: number;
  financial_filings: number;
  briefs_ready: number;
  briefs_pending: number;
  briefs_failed: number;
};

export type BuildDataQualityNoticesInput = {
  symbol: string;
  hasLastPrice: boolean;
  snapshotStale: boolean;
  sparkPointCount: number;
  /** Caps how many banners we show (highest priority first). */
  maxNotices?: number;
  quality: FilingQualitySummary | null;
  /** True when metrics API failed (distinct from empty quality). */
  metricsLoadFailed?: boolean;
  /** True when a ready brief is already rendered on the page. */
  hasReadyBrief?: boolean;
  /** True when a successful metric row is already rendered. */
  hasReadyMetrics?: boolean;
};

/** Fewer stored ticks than this → “thin history” notice. */
export const THIN_SPARKLINE_POINTS = 8;

const EMPTY_QUALITY: FilingQualitySummary = {
  metrics_attempted: 0,
  metrics_ok: 0,
  metrics_failed: 0,
  disclosures: 0,
  with_pdf: 0,
  financial_filings: 0,
  briefs_ready: 0,
  briefs_pending: 0,
  briefs_failed: 0,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === "object" && !Array.isArray(value);
}

function nonNeg(raw: unknown): number {
  if (typeof raw === "number" && Number.isSafeInteger(raw) && raw >= 0) {
    return raw;
  }
  if (typeof raw === "string" && /^\d{1,15}$/.test(raw.trim())) {
    const n = Number(raw.trim());
    if (Number.isSafeInteger(n) && n >= 0) return n;
  }
  return 0;
}

/** Fail-closed parse of metrics API ``quality`` object. */
export function parseFilingQualitySummary(
  body: unknown,
): FilingQualitySummary | null {
  if (!isRecord(body)) return null;
  const raw = isRecord(body.quality) ? body.quality : null;
  if (!raw) return null;
  return {
    metrics_attempted: nonNeg(raw.metrics_attempted),
    metrics_ok: nonNeg(raw.metrics_ok),
    metrics_failed: nonNeg(raw.metrics_failed),
    disclosures: nonNeg(raw.disclosures),
    with_pdf: nonNeg(raw.with_pdf),
    financial_filings: nonNeg(raw.financial_filings),
    briefs_ready: nonNeg(raw.briefs_ready),
    briefs_pending: nonNeg(raw.briefs_pending),
    briefs_failed: nonNeg(raw.briefs_failed),
  };
}

/**
 * Build prioritized notices. Order matters — price/freshness first, then
 * filings/metrics/briefs. Caps at ``maxNotices`` (default 4).
 */
export function buildDataQualityNotices(
  input: BuildDataQualityNoticesInput,
): DataQualityNotice[] {
  const symbol = input.symbol.trim() || "this symbol";
  const q = input.quality ?? EMPTY_QUALITY;
  const max = Math.max(1, Math.min(input.maxNotices ?? 4, 8));
  const notices: DataQualityNotice[] = [];

  if (input.metricsLoadFailed) {
    notices.push({
      id: "metrics-load-failed",
      tone: "danger",
      title: "Filing metrics unavailable right now",
      description:
        "Chime couldn’t load stored filing metrics for this symbol. Retry in a moment — this is a temporary load error, not proof that no filings exist.",
    });
  }

  if (!input.hasLastPrice) {
    notices.push({
      id: "no-price",
      tone: "warning",
      title: "No stored price yet",
      description: `Chime has not stored a price tick for ${symbol}. Snapshots appear during market hours (09:30–14:30 SLT, weekdays) once the symbol is watched. Not financial advice.`,
    });
  } else if (input.snapshotStale) {
    notices.push({
      id: "stale-price",
      tone: "warning",
      title: "Price snapshot looks stale",
      description:
        "The last tick is more than a day old. The poller may be paused outside market hours, or this symbol may not be on an active watchlist. Not financial advice.",
    });
  }

  if (
    input.hasLastPrice &&
    input.sparkPointCount > 0 &&
    input.sparkPointCount < THIN_SPARKLINE_POINTS
  ) {
    notices.push({
      id: "thin-ticks",
      tone: "info",
      title: "Thin price history",
      description: `Only ${input.sparkPointCount} stored tick${input.sparkPointCount === 1 ? "" : "s"} so far — the chart will look sparse until more polls land. Illiquid or newly watched symbols often look like this.`,
    });
  }

  if (!input.metricsLoadFailed) {
    if (q.disclosures === 0) {
      notices.push({
        id: "no-disclosures",
        tone: "warning",
        title: "No disclosures stored yet",
        description: `Chime has not ingested CSE announcements for ${symbol}. Filing metrics and AI briefs need those disclosures first.`,
      });
    } else if (q.financial_filings === 0) {
      notices.push({
        id: "no-financial-filings",
        tone: "warning",
        title: "No financial-statement filings yet",
        description:
          "Announcements may exist, but Chime has not found CSE financial-statement PDFs for this symbol. Metrics and YoY need those filings — warrants, prefs, and thinly listed names often have none.",
      });
    } else if (q.with_pdf === 0) {
      notices.push({
        id: "no-pdfs",
        tone: "info",
        title: "Filings without PDF links yet",
        description:
          "Disclosures are stored, but PDF URLs are still missing. Metrics extraction waits until a PDF link is enriched.",
      });
    }

    if (q.metrics_ok === 0 && q.metrics_failed > 0) {
      notices.push({
        id: "extract-failed",
        tone: "warning",
        title: "Filing metrics could not be extracted",
        description: `Chime tried ${q.metrics_failed} filing PDF${q.metrics_failed === 1 ? "" : "s"} for ${symbol}, but could not mark a clean extract (scanned pages, unusual layouts, or non-LKR summary tables). Any numbers shown still need verification against the source PDF — this is not proof the issuer has no results.`,
      });
    } else if (
      q.metrics_ok === 0 &&
      q.metrics_attempted === 0 &&
      q.financial_filings > 0 &&
      q.with_pdf > 0 &&
      !input.hasReadyMetrics
    ) {
      notices.push({
        id: "metrics-pending",
        tone: "info",
        title: "Metrics extraction still pending",
        description:
          "Financial PDFs are on file, but numbers have not been extracted yet. The metrics drain catches these up on a schedule.",
      });
    } else if (q.metrics_failed > 0 && q.metrics_ok > 0) {
      notices.push({
        id: "partial-extract",
        tone: "info",
        title: "Some filing extracts failed",
        description: `${q.metrics_ok} filing${q.metrics_ok === 1 ? "" : "s"} extracted cleanly; ${q.metrics_failed} failed. Shown figures still need verification against the source PDF.`,
      });
    }
  }

  if (!input.hasReadyBrief) {
    if (q.briefs_failed > 0 && q.briefs_ready === 0 && q.briefs_pending === 0) {
      notices.push({
        id: "brief-failed",
        tone: "warning",
        title: "AI brief failed for recent filings",
        description:
          "Brief generation did not complete for this symbol’s filings (model limits or extract issues). Chime will retry on the brief drain — this is not investment advice.",
      });
    } else if (q.briefs_pending > 0) {
      notices.push({
        id: "brief-pending",
        tone: "info",
        title: "AI brief still in the queue",
        description:
          "A filing brief is pending or processing. Free-tier AI quotas can lag — ready summaries show up after the drain finishes. Not financial advice.",
      });
    } else if (q.metrics_ok > 0 || input.hasReadyMetrics) {
      notices.push({
        id: "brief-missing",
        tone: "info",
        title: "No ready AI brief yet",
        description:
          "Metrics exist, but no ready brief is stored. Briefs are generated after financial PDFs are summarized and may lag on rate limits. Not financial advice.",
      });
    }
  }

  return notices.slice(0, max);
}
