"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiErrorMessage, apiMutate } from "@/lib/api/client-fetch";

type MePayload = {
  id: number;
  telegram_id: number;
  created_at: string;
  csrf_token?: string;
};

function chipLabel(me: MePayload): string {
  if (me.telegram_id != null && Number.isFinite(me.telegram_id)) {
    return String(me.telegram_id);
  }
  return `user ${me.id}`;
}

export function NavSession({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
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
        if (!res.ok) return;
        const data = (await res.json()) as MePayload;
        if (!cancelled) setMe(data);
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
      const { ok, data } = await apiMutate("/api/v1/auth/logout", {
        method: "POST",
      });
      if (!ok) {
        console.error(apiErrorMessage(data, "Logout failed."));
        setPending(false);
        return;
      }
      router.replace("/login");
      router.refresh();
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
