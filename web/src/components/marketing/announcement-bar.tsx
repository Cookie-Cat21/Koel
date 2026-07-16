"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

const STORAGE_KEY = "chime_announce_dismissed_v1";

/**
 * Dismissible top bar — HyperUI / shadcnblocks banner pattern.
 * Renders visible by default (SSR + first paint); only hides after a prior dismiss.
 */
export function AnnouncementBar({
  message = "CSE alerts on Telegram — manage watchlist & rules in the dash.",
}: {
  message?: string;
}) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const root = document.getElementById("chime-announce");
    if (!root) return;

    try {
      if (sessionStorage.getItem(STORAGE_KEY) === "1") {
        const t = window.setTimeout(() => setDismissed(true), 0);
        return () => window.clearTimeout(t);
      }
    } catch {
      /* private mode */
    }

    const btn = root.querySelector<HTMLButtonElement>(
      "[data-announce-dismiss]",
    );
    if (!btn) return;
    const onDismiss = () => {
      try {
        sessionStorage.setItem(STORAGE_KEY, "1");
      } catch {
        /* ignore */
      }
      setDismissed(true);
      root.remove();
    };
    btn.addEventListener("click", onDismiss);
    return () => btn.removeEventListener("click", onDismiss);
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
      id="chime-announce"
      role="region"
      aria-label="Announcement"
      className="border-b border-border/70 bg-foreground text-background"
    >
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-2 sm:px-6">
        <p className="text-xs leading-snug sm:text-sm">
          {message}{" "}
          <Link
            href="/#how-it-works"
            className="underline underline-offset-2 hover:text-background/90"
          >
            How it works
          </Link>
        </p>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          data-announce-dismiss
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
