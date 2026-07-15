"use client";

import { useCallback, useSyncExternalStore } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

const STORAGE_KEY = "chime_announce_dismissed_v1";

const listeners = new Set<() => void>();

function subscribe(onStoreChange: () => void) {
  listeners.add(onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
  };
}

function getSnapshot() {
  try {
    if (sessionStorage.getItem(STORAGE_KEY) === "1") return false;
  } catch {
    /* private mode — show bar */
  }
  return true;
}

function getServerSnapshot() {
  return false;
}

function notify() {
  for (const listener of listeners) listener();
}

/** Dismissible top bar — HyperUI / shadcnblocks banner pattern. */
export function AnnouncementBar({
  message = "CSE alerts on Telegram — manage watchlist & rules in the dash.",
}: {
  message?: string;
}) {
  const visible = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );

  const dismiss = useCallback(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    notify();
  }, []);

  if (!visible) return null;

  return (
    <div
      role="region"
      aria-label="Announcement"
      className="border-b border-border/70 bg-foreground text-background"
    >
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-2 sm:px-6">
        <p className="text-xs leading-snug sm:text-sm">{message}</p>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          onClick={dismiss}
          aria-label="Dismiss announcement"
          className="shrink-0 text-background hover:bg-background/15 hover:text-background"
        >
          <X className="size-3.5" aria-hidden />
        </Button>
      </div>
    </div>
  );
}
