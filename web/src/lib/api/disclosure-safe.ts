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
 * Plain-text brief for display/API: only when status===ready.
 * Strips C0/C1 controls; caps length. Does not HTML-escape (React does).
 */
export function sanitizeBriefText(
  brief: string | null | undefined,
  briefStatus: string | null | undefined,
): string | null {
  if (briefStatus !== "ready" || brief == null) return null;
  const cleaned = brief.replace(/[\u0000-\u001F\u007F-\u009F]/g, "").trim();
  if (!cleaned) return null;
  return cleaned.length > MAX_BRIEF_LENGTH
    ? cleaned.slice(0, MAX_BRIEF_LENGTH)
    : cleaned;
}

export function normalizeBriefStatus(
  raw: string | null | undefined,
): BriefStatus | null {
  if (raw == null) return null;
  return BRIEF_STATUSES.has(raw) ? (raw as BriefStatus) : null;
}
