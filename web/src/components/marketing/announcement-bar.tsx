"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, X } from "lucide-react";

import { Button } from "@/components/ui/button";

const STORAGE_KEY = "koel_announce_dismissed_v1";

/**
 * Watermelon announcement-8 — quiet muted bar + dismiss.
 * Market-hours / Telegram push copy (not cookie/promo chrome).
 */
export function AnnouncementBar({
  message = "Market hours 09:30–14:30 SLT · Telegram push even if the tab is closed.",
  href = "/#how-it-works",
  linkLabel = "How it works",
}: {
  message?: string;
  href?: string;
  linkLabel?: string;
}) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    try {
      if (sessionStorage.getItem(STORAGE_KEY) === "1") {
        const t = window.setTimeout(() => setDismissed(true), 0);
        return () => window.clearTimeout(t);
      }
    } catch {
      /* private mode */
    }
  }, []);

  function dismiss() {
    try {
      sessionStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    setDismissed(true);
  }

  if (dismissed) return null;

  return (
    <div
      id="koel-announce"
      role="region"
      aria-label="Announcement"
      className="border-b border-border/70 bg-muted"
    >
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-4 py-2 sm:px-6">
        <p className="flex flex-1 flex-wrap items-center justify-center gap-x-1 gap-y-0.5 text-center text-xs text-muted-foreground sm:text-sm">
          <span>{message}</span>
          <Link
            href={href}
            className="group inline-flex items-center text-foreground underline underline-offset-4 hover:text-foreground/90"
          >
            {linkLabel}
            <ArrowUpRight className="ml-0.5 size-3.5 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </Link>
        </p>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          data-announce-dismiss
          onClick={dismiss}
          aria-label="Dismiss announcement"
          className="shrink-0 text-muted-foreground hover:text-foreground"
        >
          <X className="size-3.5" aria-hidden />
        </Button>
      </div>
    </div>
  );
}
