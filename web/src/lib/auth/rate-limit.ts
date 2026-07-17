/**
 * Best-effort in-memory sliding-window rate limit for auth routes (S-04).
 *
 * Vercel multi-instance: each isolate has its own map — still stops casual
 * hammering; not a global quota. Do not use for billing / hard security SLAs.
 */

export type RateLimitResult =
  | { ok: true }
  | { ok: false; retryAfterSec: number };

type Bucket = { timestamps: number[] };

const buckets = new Map<string, Bucket>();

/** Cap map size so hostile unique keys cannot grow forever. */
const MAX_BUCKETS = 4096;

export type RateLimitOptions = {
  /** Max events in the window. */
  limit: number;
  /** Window length in milliseconds. */
  windowMs: number;
  /** Optional clock for tests. */
  now?: () => number;
};

/**
 * Record one hit for ``key``. Returns ok:false when over limit.
 * Prunes expired timestamps; evicts oldest keys if map grows too large.
 */
export function hitRateLimit(
  key: string,
  options: RateLimitOptions,
): RateLimitResult {
  if (typeof key !== "string" || !key || key.length > 256) {
    return { ok: false, retryAfterSec: 60 };
  }
  const limit = Math.max(1, Math.floor(options.limit));
  const windowMs = Math.max(1_000, Math.floor(options.windowMs));
  const now = (options.now ?? Date.now)();
  const cutoff = now - windowMs;

  let bucket = buckets.get(key);
  if (!bucket) {
    if (buckets.size >= MAX_BUCKETS) {
      // Evict arbitrary oldest insertion (Map iteration order).
      const first = buckets.keys().next().value;
      if (typeof first === "string") buckets.delete(first);
    }
    bucket = { timestamps: [] };
    buckets.set(key, bucket);
  }

  bucket.timestamps = bucket.timestamps.filter((t) => t > cutoff);
  if (bucket.timestamps.length >= limit) {
    const oldest = bucket.timestamps[0] ?? now;
    const retryAfterSec = Math.max(
      1,
      Math.ceil((oldest + windowMs - now) / 1000),
    );
    return { ok: false, retryAfterSec };
  }
  bucket.timestamps.push(now);
  return { ok: true };
}

/** Test helper — clear all buckets. */
export function resetRateLimitBuckets(): void {
  buckets.clear();
}

/** Client IP for rate keys — prefers first X-Forwarded-For hop. */
export function clientIpFromRequest(request: Request): string {
  const xff = request.headers.get("x-forwarded-for");
  if (typeof xff === "string" && xff.trim()) {
    const first = xff.split(",")[0]?.trim();
    if (first && first.length <= 128) return first;
  }
  const realIp = request.headers.get("x-real-ip");
  if (typeof realIp === "string" && realIp.trim()) {
    return realIp.trim().slice(0, 128);
  }
  return "unknown";
}
