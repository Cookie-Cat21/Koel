import {
  buildDataQualityNotices,
  parseFilingQualitySummary,
} from "../src/lib/data-quality";

const q = parseFilingQualitySummary({
  quality: {
    metrics_attempted: 2,
    metrics_ok: 0,
    metrics_failed: 2,
    disclosures: 3,
    with_pdf: 2,
    financial_filings: 2,
    briefs_ready: 0,
    briefs_pending: 1,
    briefs_failed: 0,
  },
});

const notices = buildDataQualityNotices({
  symbol: "MAL.X0000",
  hasLastPrice: true,
  snapshotStale: false,
  sparkPointCount: 2,
  quality: q,
  hasReadyBrief: false,
  hasReadyMetrics: false,
});
const ids = notices.map((n) => n.id);

if (!ids.includes("extract-failed")) {
  throw new Error(`missing extract-failed: ${ids.join(",")}`);
}
if (!ids.includes("thin-ticks")) {
  throw new Error(`missing thin-ticks: ${ids.join(",")}`);
}
if (!ids.includes("brief-pending")) {
  throw new Error(`missing brief-pending: ${ids.join(",")}`);
}

const healthy = buildDataQualityNotices({
  symbol: "COMB.N0000",
  hasLastPrice: true,
  snapshotStale: false,
  sparkPointCount: 120,
  quality: {
    metrics_attempted: 4,
    metrics_ok: 4,
    metrics_failed: 0,
    disclosures: 10,
    with_pdf: 8,
    financial_filings: 6,
    briefs_ready: 2,
    briefs_pending: 0,
    briefs_failed: 0,
  },
  hasReadyBrief: true,
  hasReadyMetrics: true,
});
if (healthy.length !== 0) {
  throw new Error(`healthy should be empty: ${JSON.stringify(healthy)}`);
}

const noFin = buildDataQualityNotices({
  symbol: "FOO.N0000",
  hasLastPrice: true,
  snapshotStale: false,
  sparkPointCount: 40,
  quality: {
    metrics_attempted: 0,
    metrics_ok: 0,
    metrics_failed: 0,
    disclosures: 5,
    with_pdf: 0,
    financial_filings: 0,
    briefs_ready: 0,
    briefs_pending: 0,
    briefs_failed: 0,
  },
  hasReadyBrief: false,
  hasReadyMetrics: false,
});
if (!noFin.some((n) => n.id === "no-financial-filings")) {
  throw new Error(`missing no-financial-filings: ${noFin.map((n) => n.id)}`);
}

console.log("data-quality smoke ok", ids.join(","));
