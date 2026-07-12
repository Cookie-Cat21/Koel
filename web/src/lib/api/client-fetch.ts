import { readBoundedResponseText } from "@/lib/api/read-bounded-text";
import { CSRF_COOKIE, MAX_CSRF_TOKEN_LENGTH } from "@/lib/auth/config";
import { redirectToLogin } from "@/lib/auth/session-redirect";

/** Must match server `CSRF_HEADER` / guard double-submit check. */
const CSRF_HEADER = "x-csrf-token";

/** Cap hostile API error.message before toast / inline render. */
export const MAX_API_ERROR_MESSAGE_LENGTH = 300;

/** Abort budget for browser → /api/v1 mutations (parity with SSR bound). */
export const CLIENT_API_TIMEOUT_MS = 15_000;

/** Cap mutation / login JSON before parse — payloads are tiny. */
export const CLIENT_API_BODY_MAX_CHARS = 1_048_576;

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/g;

/** User-facing copy when double-submit CSRF fails (E6-D05). */
export const CSRF_FRIENDLY_MESSAGE =
  "Security check failed — refresh the page and try again.";

/** Read non-HttpOnly CSRF cookie for double-submit mutations. */
export function readBrowserCsrf(): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${CSRF_COOKIE}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      const raw = trimmed.slice(prefix.length);
      // Fail closed — multi-MB forged cookies must not decode / ship.
      if (raw.length > MAX_CSRF_TOKEN_LENGTH) return null;
      // Malformed % sequences must not throw URIError mid-mutation.
      try {
        const decoded = decodeURIComponent(raw);
        if (decoded.length > MAX_CSRF_TOKEN_LENGTH) return null;
        return decoded;
      } catch {
        return null;
      }
    }
  }
  return null;
}

type ApiErrorBody = {
  error?: { code?: string; message?: string };
};

function isCsrfFailed(data: unknown): boolean {
  const body = data as ApiErrorBody | null;
  return body?.error?.code === "csrf_failed";
}

function unauthorizedBody(): { error: { code: string; message: string } } {
  return {
    error: {
      code: "unauthorized",
      message: "Session expired. Sign in again.",
    },
  };
}

/**
 * Browser mutation paths must stay under ``/api/v1/`` — reject absolute /
 * scheme-relative / ``..`` / off-API paths that used to ship X-CSRF-Token to
 * arbitrary same-origin routes (parity with server ``isSafeServerApiPath``).
 */
export function isSafeClientApiPath(path: string): boolean {
  if (!path.startsWith("/") || path.startsWith("//")) return false;
  if (path.includes("://") || path.includes("\\") || path.includes("..")) {
    return false;
  }
  if (/[\u0000-\u001F\u007F]/.test(path)) return false;
  const pathOnly = path.split("?", 1)[0] ?? path;
  return pathOnly === "/api/v1" || pathOnly.startsWith("/api/v1/");
}

/**
 * Browser mutation against /api/v1 with credentials + X-CSRF-Token.
 * Login is the only CSRF-exempt mutation — do not use this for demo auth.
 *
 * Missing CSRF or HTTP 401 → hard-redirect to `/login?expired=1` so soft
 * nav / RSC cache cannot leave a zombie authenticated shell. Pass
 * `authRedirect: false` for logout (caller owns the destination).
 */
export async function apiMutate(
  path: string,
  init: {
    method: "POST" | "DELETE" | "PUT" | "PATCH";
    body?: unknown;
    /** Default true. Set false when the caller handles 401 (e.g. logout). */
    authRedirect?: boolean;
  },
): Promise<{ ok: boolean; status: number; data: unknown }> {
  // Fail closed — absolute / off-/api/v1 paths would leak X-CSRF-Token.
  if (!isSafeClientApiPath(path)) {
    return {
      ok: false,
      status: 400,
      data: {
        error: {
          code: "validation_error",
          message: "apiMutate path must be root-relative /api/v1/*.",
        },
      },
    };
  }

  const authRedirect = init.authRedirect !== false;
  const csrf = readBrowserCsrf();
  if (!csrf) {
    // Session + CSRF share TTL; missing CSRF usually means expiry/clear.
    if (authRedirect) {
      redirectToLogin({ expired: true });
    }
    return {
      ok: false,
      status: 401,
      data: unauthorizedBody(),
    };
  }

  const headers = new Headers();
  headers.set("Accept", "application/json");
  headers.set(CSRF_HEADER, csrf);
  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), CLIENT_API_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(path, {
      method: init.method,
      headers,
      credentials: "same-origin",
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      signal: ctrl.signal,
    });
  } catch {
    return {
      ok: false,
      status: 0,
      data: {
        error: {
          code: "network_error",
          message: "Network error. Try again.",
        },
      },
    };
  } finally {
    clearTimeout(timer);
  }

  // Stream-bound body — missing / understated Content-Length must not let
  // res.text() allocate past the cap (parity SSR + HEALTH_URL + readJsonBody).
  const bounded = await readBoundedResponseText(
    res,
    CLIENT_API_BODY_MAX_CHARS,
  );
  if (!bounded.ok) {
    return {
      ok: false,
      status: 502,
      data: {
        error: {
          code: "degraded",
          message: "Response too large.",
        },
      },
    };
  }

  let data: unknown = null;
  try {
    data = bounded.text ? JSON.parse(bounded.text) : null;
  } catch {
    data = null;
  }

  if (res.status === 401) {
    if (authRedirect) {
      redirectToLogin({ expired: true });
    }
    return { ok: false, status: 401, data: data ?? unauthorizedBody() };
  }

  if (!res.ok && isCsrfFailed(data)) {
    return {
      ok: false,
      status: res.status,
      data: {
        error: { code: "csrf_failed", message: CSRF_FRIENDLY_MESSAGE },
      },
    };
  }

  return { ok: res.ok, status: res.status, data };
}

export function apiErrorMessage(
  data: unknown,
  fallback: string,
): string {
  if (isCsrfFailed(data)) {
    return CSRF_FRIENDLY_MESSAGE;
  }
  const body = data as ApiErrorBody | null;
  const raw = body?.error?.message;
  if (typeof raw !== "string" || !raw.trim()) return fallback;
  const cleaned = raw.replace(CTRL_RE, "").trim();
  if (!cleaned) return fallback;
  return cleaned.length > MAX_API_ERROR_MESSAGE_LENGTH
    ? cleaned.slice(0, MAX_API_ERROR_MESSAGE_LENGTH).trimEnd()
    : cleaned;
}
