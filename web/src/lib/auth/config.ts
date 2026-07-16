/**
 * Dashboard auth env (ADR 001). Fail closed on empty secret when dash APIs run.
 */

import { toSafePositiveInt } from "@/lib/api/safe-int";

export const SESSION_COOKIE = "chime_session";
export const CSRF_COOKIE = "chime_csrf";
export const SESSION_TTL_SECONDS = 12 * 60 * 60; // 12h

/**
 * Cap hostile CSRF header/cookie before compare / browser decode.
 * Mint emits 32-byte base64url (~43 chars). Shared by server + client
 * (client cannot import csrf.ts — that pulls node:crypto).
 */
export const MAX_CSRF_TOKEN_LENGTH = 128;

/**
 * Cap demo Telegram ID allowlist — a multi-KB comma env used to balloon the
 * login ``<select>`` / SSR props (thin dash is not an IAM directory).
 */
export const MAX_DEMO_ALLOWLIST = 64;

/**
 * Cookie Secure/SameSite (ADR 001 / API contract).
 * Secure only in production so local HTTP can still set cookies;
 * SameSite=Lax for same-site dashboard + Telegram-first CSRF story.
 * Keep set + clear paths in lockstep (browser clear must match attrs).
 */
export const COOKIE_SAME_SITE = "lax" as const;

export function cookieSecure(): boolean {
  // Fail closed — non-string NODE_ENV must not soft-match production Secure.
  const raw = process.env.NODE_ENV;
  return typeof raw === "string" && raw === "production";
}

export type DashAuthConfig = {
  demoAuthEnabled: boolean;
  allowlist: ReadonlySet<number>;
  defaultTelegramId: number | null;
  sessionSecret: string;
  /**
   * When true, /login may render the demo allowlist as a ``<select>``.
   * Default off — listing IDs helps attackers (S-11). Enable only for local
   * Cloud Agent demos via ``DASH_DEMO_SHOW_ALLOWLIST=1``.
   */
  showDemoAllowlist: boolean;
  /** Ops telegram IDs allowed to see full /health detail (S-05). */
  opsAllowlist: ReadonlySet<number>;
};

function parseAllowlist(raw: string | undefined): Set<number> {
  if (!raw || !raw.trim()) return new Set();
  const ids = new Set<number>();
  for (const part of raw.split(",")) {
    if (ids.size >= MAX_DEMO_ALLOWLIST) break;
    // Digits-only ≤15 via toSafePositiveInt — bare Number()+isSafeInteger
    // can alias oversized env tokens onto MAX_SAFE_INTEGER.
    const n = toSafePositiveInt(part.trim());
    if (n == null) continue;
    ids.add(n);
  }
  return ids;
}

export function getDashAuthConfig(): DashAuthConfig {
  // Fail closed — non-string mock/hostile env values must not throw on .trim
  // (parity scenariosEnabled typeof guard).
  const secretRaw = process.env.DASH_SESSION_SECRET;
  const secret = typeof secretRaw === "string" ? secretRaw.trim() : "";
  const defaultRaw = process.env.DASH_DEFAULT_TELEGRAM_ID;
  const defaultTelegramId = toSafePositiveInt(
    typeof defaultRaw === "string" ? defaultRaw.trim() : "",
  );
  const demoRaw = process.env.DASH_DEMO_AUTH;
  const allowRaw = process.env.DASH_DEMO_TELEGRAM_IDS;
  const showAllowRaw = process.env.DASH_DEMO_SHOW_ALLOWLIST;
  const opsRaw = process.env.DASH_OPS_TELEGRAM_IDS;

  return {
    demoAuthEnabled: typeof demoRaw === "string" && demoRaw === "1",
    allowlist: parseAllowlist(
      typeof allowRaw === "string" ? allowRaw : undefined,
    ),
    defaultTelegramId,
    sessionSecret: secret,
    showDemoAllowlist:
      typeof showAllowRaw === "string" && showAllowRaw === "1",
    opsAllowlist: parseAllowlist(
      typeof opsRaw === "string" ? opsRaw : undefined,
    ),
  };
}

/**
 * Public allowlist for /login UI only — never trust client for authz.
 * Returns [] unless ``showDemoAllowlist`` is on (S-11).
 */
export function publicDemoAllowlist(cfg: DashAuthConfig): number[] {
  if (!cfg.showDemoAllowlist) return [];
  return Array.from(cfg.allowlist).sort((a, b) => a - b);
}

/** True when telegram_id may see full health / ops telemetry (S-05). */
export function isOpsTelegramId(
  cfg: DashAuthConfig,
  telegramId: number,
): boolean {
  return cfg.opsAllowlist.has(telegramId);
}
