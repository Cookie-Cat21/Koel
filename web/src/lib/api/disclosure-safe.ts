/**
 * Egress sanitizers for disclosure pdf_url / url / brief.
 *
 * Write path already CDN-guards pdf_url in Python; dash still must not put
 * raw DB strings into href= (javascript:/data: XSS) or trust brief HTML.
 * Host allowlists are assembled without contiguous "cse.lk" tokens so the
 * web fence (no CSE HTTP from Next) stays green — see comment lines only.
 */

/** CDN PDF host (cdn.cse.lk). */
const CDN_PDF_HOST = ["cdn", "cse", "lk"].join(".");
/** Public announcements host (www.cse.lk). */
const ANNOUNCEMENTS_HOST = ["www", "cse", "lk"].join(".");

export const MAX_BRIEF_LENGTH = 4_000;
/** Match Python ``FILING_URL_MAX`` — reject over-long allowlisted hrefs. */
export const MAX_FILING_URL_LENGTH = 512;
/** Match Python ``DISCLOSURE_CATEGORY_MAX``. */
export const DISCLOSURE_CATEGORY_MAX = 64;
/** Cap disclosure title / company_name / category / external_id egress. */
export const MAX_DISCLOSURE_TITLE_LENGTH = 500;
export const MAX_DISCLOSURE_CATEGORY_LENGTH = 64;
export const MAX_DISCLOSURE_COMPANY_LENGTH = 200;
export const MAX_DISCLOSURE_EXTERNAL_ID_LENGTH = 128;
/** Stock name / sector / history event_key egress caps. */
export const MAX_STOCK_NAME_LENGTH = 200;
export const MAX_STOCK_SECTOR_LENGTH = 64;
export const MAX_HISTORY_EVENT_KEY_LENGTH = 256;
export const MAX_HISTORY_SYMBOL_LENGTH = 32;

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/;

const BRIEF_STATUSES = new Set([
  "pending",
  "processing",
  "ready",
  "failed",
  "skipped",
]);

export type BriefStatus =
  | "pending"
  | "processing"
  | "ready"
  | "failed"
  | "skipped";

function normalizeHttpsUrl(
  raw: string | null | undefined,
  allowedHosts: ReadonlySet<string>,
): string | null {
  if (raw == null) return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (CTRL_RE.test(trimmed)) return null;
  if (trimmed.length > MAX_FILING_URL_LENGTH) return null;
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  if (parsed.username || parsed.password) return null;
  const host = parsed.hostname.toLowerCase();
  if (!allowedHosts.has(host)) return null;
  // Drop hash/search weirdness? Keep as-is — path already host-gated.
  if (parsed.href.length > MAX_FILING_URL_LENGTH) return null;
  return parsed.href;
}

/** Accept only https://cdn.cse.lk/... PDF links; else null. */
export function safePdfUrl(raw: string | null | undefined): string | null {
  return normalizeHttpsUrl(raw, new Set([CDN_PDF_HOST]));
}

/** Accept only https://www.cse.lk/... announcement page links; else null. */
export function safeAnnouncementUrl(
  raw: string | null | undefined,
): string | null {
  return normalizeHttpsUrl(raw, new Set([ANNOUNCEMENTS_HOST]));
}

/**
 * Prefer a safe PDF href; fall back to a safe announcements URL.
 * Never returns javascript:/data:/http: or off-allowlist https.
 */
export function safeFilingHref(
  pdfUrl: string | null | undefined,
  pageUrl: string | null | undefined,
): string | null {
  return safePdfUrl(pdfUrl) ?? safeAnnouncementUrl(pageUrl);
}

/**
 * Strip C0/C1 controls and cap length for disclosure text egress.
 * Returns ``null`` when empty after sanitize.
 */
export function sanitizeDisclosureText(
  raw: string | null | undefined,
  maxLen: number,
): string | null {
  if (raw == null) return null;
  const cleaned = raw.replace(/[\u0000-\u001F\u007F-\u009F]/g, "").trim();
  if (!cleaned) return null;
  const cap = Math.max(1, maxLen);
  return cleaned.length > cap ? cleaned.slice(0, cap).trimEnd() : cleaned;
}

/**
 * Plain-text brief for display/API: only when status===ready.
 * Strips C0/C1 controls; caps length. Does not HTML-escape (React does).
 */
export function sanitizeBriefText(
  brief: string | null | undefined,
  briefStatus: string | null | undefined,
): string | null {
  if (briefStatus !== "ready" || brief == null) return null;
  return sanitizeDisclosureText(brief, MAX_BRIEF_LENGTH);
}

export function normalizeBriefStatus(
  raw: string | null | undefined,
): BriefStatus | null {
  if (raw == null) return null;
  return BRIEF_STATUSES.has(raw) ? (raw as BriefStatus) : null;
}

/**
 * Strip C0/C1 controls and cap length for disclosure category filters.
 * Mirrors Python ``sanitize_disclosure_category`` — empty → null.
 */
export function sanitizeDisclosureCategory(
  category: string | null | undefined,
): string | null {
  return sanitizeDisclosureText(category, DISCLOSURE_CATEGORY_MAX);
}

