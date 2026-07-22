"use client";

import { useEffect, useState } from "react";

import { Label } from "@/components/ui/label";

/**
 * Shows a Postgres-built sample of the public channel close summary (W7).
 */
export function ChannelPreviewCard() {
  const [preview, setPreview] = useState<string | null>(null);
  const [configured, setConfigured] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/v1/channel/preview", {
          credentials: "same-origin",
        });
        if (!res.ok) {
          if (!cancelled) setError("Could not load channel preview.");
          return;
        }
        const data = (await res.json()) as {
          preview?: string;
          configured?: boolean;
        };
        if (cancelled) return;
        setPreview(typeof data.preview === "string" ? data.preview : null);
        setConfigured(Boolean(data.configured));
      } catch {
        if (!cancelled) setError("Network error loading preview.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="rounded-lg border border-border/70 p-4 sm:p-5">
      <Label>Public channel preview</Label>
      <p className="mt-1 text-sm text-muted-foreground">
        Open/close posts go to Telegram when{" "}
        <code className="text-xs">TELEGRAM_PUBLIC_CHANNEL_ID</code> is set. Below
        is a live Postgres sample of the close summary copy.
        {configured ? " Channel id is configured in this environment." : " Channel id not set (preview only)."}
      </p>
      {error ? (
        <p className="mt-3 text-sm text-muted-foreground">{error}</p>
      ) : preview ? (
        <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-xs leading-relaxed text-foreground">
          {preview}
        </pre>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Loading preview…</p>
      )}
    </section>
  );
}
