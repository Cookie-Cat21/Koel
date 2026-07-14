"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

const STORAGE_KEY = "chime_cake_cherry_banner_dismissed_v1";

/**
 * Dismissible product framing — Tremor banner-04 pattern.
 * Cake = dash; cherry = Telegram push.
 */
export function CakeCherryBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (window.localStorage.getItem(STORAGE_KEY) === "1") return;
    } catch {
      /* private mode */
    }
    const showTimer = window.setTimeout(() => setVisible(true), 0);
    return () => {
      window.clearTimeout(showTimer);
    };
  }, []);

  function dismiss() {
    setVisible(false);
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
  }

  if (!visible) return null;

  return (
    <div
      role="status"
      className="relative mb-6 rounded-xl border border-border bg-muted/40 px-4 py-3 pr-12 text-sm text-muted-foreground"
    >
      <p>
        <span className="font-medium text-foreground">Dash is the cake.</span>{" "}
        Browse and manage rules here.{" "}
        <span className="font-medium text-foreground">Telegram is the cherry</span>{" "}
        — you get the ping when a rule fires, even with this tab closed.{" "}
        <Link
          href="/alerts"
          className="underline underline-offset-4 hover:text-foreground"
        >
          Set an alert
        </Link>
        .
      </p>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        className="absolute top-2 right-2"
        onClick={dismiss}
        aria-label="Dismiss banner"
      >
        <X className="size-3.5" />
      </Button>
    </div>
  );
}
