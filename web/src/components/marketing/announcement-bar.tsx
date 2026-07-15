"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

const STORAGE_KEY = "chime_announce_dismissed_v1";

/** Dismissible top bar — HyperUI / shadcnblocks banner pattern. */
export function AnnouncementBar({
  message = "CSE alerts on Telegram — manage watchlist & rules in the dash.",
}: {
  message?: string;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (sessionStorage.getItem(STORAGE_KEY) === "1") return;
    } catch {
      /* private mode — still show */
    }
    // Defer so we don't sync-setState in the effect body (lint + hydration).
    const t = window.setTimeout(() => setVisible(true), 0);
    return () => window.clearTimeout(t);
  }, []);

  function dismiss() {
    try {
      sessionStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    setVisible(false);
  }

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
