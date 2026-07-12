import { CSRF_COOKIE } from "@/lib/auth/config";
import { redirectToLogin } from "@/lib/auth/session-redirect";

/** Must match server `CSRF_HEADER` / guard double-submit check. */
const CSRF_HEADER = "x-csrf-token";

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
      // Malformed % sequences must not throw URIError mid-mutation.
      try {
        return decodeURIComponent(trimmed.slice(prefix.length));
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

  const res = await fetch(path, {
    method: init.method,
    headers,
    credentials: "same-origin",
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  let data: unknown = null;
  try {
    data = await res.json();
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
  return body?.error?.message ?? fallback;
}
