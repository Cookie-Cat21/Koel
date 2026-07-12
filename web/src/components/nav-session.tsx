"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiErrorMessage, apiMutate } from "@/lib/api/client-fetch";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { redirectToLogin } from "@/lib/auth/session-redirect";

type MePayload = {
  id: number;
  telegram_id: number;
  created_at: string;
  csrf_token?: string;
};

/**
 * Fail-closed /me parse — digits-only SafeInteger ids. Hostile JSON must not
 * mint a chip with precision-lost telegram_id aliases.
 */
function parseMePayload(body: unknown): MePayload | null {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const r = body as Record<string, unknown>;
  const id = toSafePositiveInt(r.id);
  const telegram_id = toSafePositiveInt(r.telegram_id);
  if (id == null || telegram_id == null) return null;
  const created_at =
    typeof r.created_at === "string" && r.created_at ? r.created_at : "";
  if (!created_at) return null;
  return {
    id,
    telegram_id,
    created_at,
    csrf_token: typeof r.csrf_token === "string" ? r.csrf_token : undefined,
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
    (async () => {
      try {
        const res = await fetch("/api/v1/me", {
          method: "GET",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (res.status === 401) {
          // Expired/invalid session while shell still mounted — leave cleanly.
          if (!cancelled) redirectToLogin({ expired: true });
          return;
        }
        if (!res.ok) return;
        const data = parseMePayload(await res.json());
        if (!cancelled && data) setMe(data);
      } catch {
        /* chip stays empty */
      }
    })();
    return () => {
      cancelled = true;
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
        variant="outline"
        size="sm"
        disabled={pending}
        onClick={onLogout}
        className="shrink-0"
      >
        {pending ? "Signing out…" : "Log out"}
      </Button>
    </div>
  );
}
