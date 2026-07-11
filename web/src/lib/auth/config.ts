/**
 * Dashboard auth env (ADR 001). Fail closed on empty secret when dash APIs run.
 */

export const SESSION_COOKIE = "chime_session";
export const CSRF_COOKIE = "chime_csrf";
export const SESSION_TTL_SECONDS = 12 * 60 * 60; // 12h

export type DashAuthConfig = {
  demoAuthEnabled: boolean;
  allowlist: ReadonlySet<number>;
  defaultTelegramId: number | null;
  sessionSecret: string;
};

function parseAllowlist(raw: string | undefined): Set<number> {
  if (!raw || !raw.trim()) return new Set();
  const ids = new Set<number>();
  for (const part of raw.split(",")) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    if (!/^-?\d+$/.test(trimmed)) continue;
    const n = Number(trimmed);
    if (!Number.isSafeInteger(n) || n <= 0) continue;
    ids.add(n);
  }
  return ids;
}

export function getDashAuthConfig(): DashAuthConfig {
  const secret = (process.env.DASH_SESSION_SECRET ?? "").trim();
  const defaultRaw = (process.env.DASH_DEFAULT_TELEGRAM_ID ?? "").trim();
  let defaultTelegramId: number | null = null;
  if (defaultRaw && /^-?\d+$/.test(defaultRaw)) {
    const n = Number(defaultRaw);
    if (Number.isSafeInteger(n) && n > 0) defaultTelegramId = n;
  }

  return {
    demoAuthEnabled: process.env.DASH_DEMO_AUTH === "1",
    allowlist: parseAllowlist(process.env.DASH_DEMO_TELEGRAM_IDS),
    defaultTelegramId,
    sessionSecret: secret,
  };
}

/** Public allowlist for /login UI only — never trust client for authz. */
export function publicDemoAllowlist(cfg: DashAuthConfig): number[] {
  return Array.from(cfg.allowlist).sort((a, b) => a - b);
}
