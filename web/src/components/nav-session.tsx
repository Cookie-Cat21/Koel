"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  apiErrorMessage,
  apiMutate,
  CLIENT_API_TIMEOUT_MS,
} from "@/lib/api/client-fetch";
import { readBoundedResponseText } from "@/lib/api/read-bounded-text";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { toIso } from "@/lib/api/time";
import { MAX_CSRF_TOKEN_LENGTH } from "@/lib/auth/config";
import { redirectToLogin } from "@/lib/auth/session-redirect";

type MePayload = {
  id: number;
  telegram_id: number;
  created_at: string;
  csrf_token?: string;
};

/** Cap /me JSON before parse — payload is tiny (ids + csrf). */
const MAX_ME_BODY_CHARS = 4_096;

/**
 * Fail-closed /me parse — digits-only SafeInteger ids. Hostile JSON must not
 * mint a chip with precision-lost telegram_id aliases. Timestamps via toIso;
 * CSRF material length-capped (parity with cookie decode).
 */
function parseMePayload(body: unknown): MePayload | null {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const r = body as Record<string, unknown>;
  const id = toSafePositiveInt(r.id);
  const telegram_id = toSafePositiveInt(r.telegram_id);
  if (id == null || telegram_id == null) return null;
  const created_at = toIso(r.created_at);
  if (!created_at) return null;
  let csrf_token: string | undefined;
  if (typeof r.csrf_token === "string" && r.csrf_token) {
    if (r.csrf_token.length <= MAX_CSRF_TOKEN_LENGTH) {
      csrf_token = r.csrf_token;
    }
  }
  return {
    id,
    telegram_id,
    created_at,
    csrf_token,
  };
}

function chipLabel(me: MePayload): string {
  return String(me.telegram_id);
}

export function NavSession({ compact = false }: { compact?: boolean }) {
  const [me, setMe] = useState<MePayload | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), CLIENT_API_TIMEOUT_MS);
    (async () => {
      try {
        const res = await fetch("/api/v1/me", {
          method: "GET",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          cache: "no-store",
          signal: ctrl.signal,
        });
        if (res.status === 401) {
          // Expired/invalid session while shell still mounted — leave cleanly.
          if (!cancelled) redirectToLogin({ expired: true });
          return;
        }
        if (!res.ok) return;
        // Stream-bound body — missing / understated Content-Length must not
        // let res.text() allocate past the cap.
        const bounded = await readBoundedResponseText(res, MAX_ME_BODY_CHARS);
        if (!bounded.ok) return;
        let parsed: unknown = null;
        try {
          parsed = bounded.text ? JSON.parse(bounded.text) : null;
        } catch {
          return;
        }
        const data = parseMePayload(parsed);
        if (!cancelled && data) setMe(data);
      } catch {
        /* chip stays empty (network / abort) */
      }
    })();
    return () => {
      cancelled = true;
      ctrl.abort();
      clearTimeout(timer);
    };
  }, []);

  async function onLogout() {
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate("/api/v1/auth/logout", {
        method: "POST",
        authRedirect: false,
      });
      // 401 = already unauthenticated — still leave cleanly.
      if (!ok && status !== 401) {
        console.error(apiErrorMessage(data, "Logout failed."));
        setPending(false);
        return;
      }
      setMe(null);
      redirectToLogin();
    } catch {
      setPending(false);
    }
  }

  async function onLogoutAll() {
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate("/api/v1/auth/logout-all", {
        method: "POST",
        authRedirect: false,
      });
      if (!ok && status !== 401) {
        console.error(apiErrorMessage(data, "Logout all failed."));
        setPending(false);
        return;
      }
      setMe(null);
      redirectToLogin();
    } catch {
      setPending(false);
    }
  }

  if (!me) {
    return (
      <div
        className={
          compact
            ? "h-8 w-24 animate-pulse rounded-md bg-muted/60"
            : "hidden h-8 w-28 animate-pulse rounded-md bg-muted/60 sm:block"
        }
        aria-hidden
      />
    );
  }

  return (
    <div
      className={
        compact
          ? "flex items-center justify-between gap-3"
          : "hidden items-center gap-2 sm:flex"
      }
    >
      <span
        className="max-w-[10rem] truncate font-mono text-xs text-muted-foreground"
        title={`Telegram ${me.telegram_id} · user ${me.id}`}
        data-testid="nav-user-chip"
      >
        {chipLabel(me)}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={pending}
        onClick={() => void onLogoutAll()}
        className="shrink-0"
        title="Sign out every device"
      >
        All devices
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={pending}
        onClick={() => void onLogout()}
        className="shrink-0"
      >
        {pending ? "Signing out…" : "Log out"}
      </Button>
    </div>
  );
}
