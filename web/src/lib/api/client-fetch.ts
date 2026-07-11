import { CSRF_COOKIE } from "@/lib/auth/config";

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
      return decodeURIComponent(trimmed.slice(prefix.length));
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

/**
 * Browser mutation against /api/v1 with credentials + X-CSRF-Token.
 * Login is the only CSRF-exempt mutation — do not use this for demo auth.
 */
export async function apiMutate(
  path: string,
  init: {
    method: "POST" | "DELETE" | "PUT" | "PATCH";
    body?: unknown;
  },
): Promise<{ ok: boolean; status: number; data: unknown }> {
  const csrf = readBrowserCsrf();
  if (!csrf) {
    return {
      ok: false,
      status: 400,
      data: {
        error: { code: "csrf_failed", message: CSRF_FRIENDLY_MESSAGE },
      },
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
