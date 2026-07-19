/**
 * Market index codes persisted by the poller (``index_snapshots`` / ``daily_bars``).
 * Dashboard never calls cse.lk — charts read Postgres only.
 */

/** Canonical poller codes → display + daily_bars symbol. */
export const INDEX_CODES = ["ASPI", "SNP_SL20"] as const;
export type IndexCode = (typeof INDEX_CODES)[number];

const INDEX_CODE_SET = new Set<string>(INDEX_CODES);

export function isIndexCode(raw: unknown): raw is IndexCode {
  return typeof raw === "string" && INDEX_CODE_SET.has(raw);
}

/** Fail-closed path segment for index APIs. */
export function normalizeIndexCodeParam(raw: unknown): IndexCode | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim().toUpperCase();
  // Accept URL-decoded SNP_SL20; reject anything else.
  if (isIndexCode(trimmed)) return trimmed;
  return null;
}
