"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError } from "@/components/inline-error";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { apiErrorMessage, apiMutate } from "@/lib/api/client-fetch";

export type SettingsPreferences = {
  digest_enabled: boolean;
  quiet_hours_start: number | null;
  quiet_hours_end: number | null;
  alert_quota_max: number;
};

const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}

function hourValue(hour: number | null): string {
  return hour == null ? "" : String(hour);
}

function parseHourValue(raw: string): number | null | undefined {
  if (raw === "") return null;
  if (!/^\d{1,2}$/.test(raw)) return undefined;
  const n = Number(raw);
  return Number.isSafeInteger(n) && n >= 0 && n <= 23 ? n : undefined;
}

function parsePrefs(data: unknown): SettingsPreferences | null {
  if (data == null || typeof data !== "object" || Array.isArray(data)) {
    return null;
  }
  const r = data as Record<string, unknown>;
  const digest = r.digest_enabled;
  const start = r.quiet_hours_start;
  const end = r.quiet_hours_end;
  const quota = r.alert_quota_max;
  if (typeof digest !== "boolean") return null;
  const normalizedStart =
    start === null || (typeof start === "number" && Number.isSafeInteger(start) && start >= 0 && start <= 23)
      ? start
      : undefined;
  const normalizedEnd =
    end === null || (typeof end === "number" && Number.isSafeInteger(end) && end >= 0 && end <= 23)
      ? end
      : undefined;
  if (normalizedStart === undefined || normalizedEnd === undefined) return null;
  if (typeof quota !== "number" || !Number.isSafeInteger(quota) || quota < 0) {
    return null;
  }
  return {
    digest_enabled: digest,
    quiet_hours_start: normalizedStart,
    quiet_hours_end: normalizedEnd,
    alert_quota_max: quota,
  };
}

export function SettingsForm({ initial }: { initial: SettingsPreferences }) {
  const router = useRouter();
  const toast = useToast();
  const [digestEnabled, setDigestEnabled] = useState(initial.digest_enabled);
  const [quietStart, setQuietStart] = useState(hourValue(initial.quiet_hours_start));
  const [quietEnd, setQuietEnd] = useState(hourValue(initial.quiet_hours_end));
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const start = parseHourValue(quietStart);
    const end = parseHourValue(quietEnd);
    if (start === undefined || end === undefined) {
      setError("Quiet hours must be off or between 00:00 and 23:00.");
      return;
    }
    if ((start == null) !== (end == null)) {
      setError("Set both quiet-hour ends, or leave both off.");
      return;
    }

    setPending(true);
    try {
      const { ok, status, data } = await apiMutate("/api/v1/me/preferences", {
        method: "PATCH",
        body: {
          digest_enabled: digestEnabled,
          quiet_hours_start: start,
          quiet_hours_end: end,
        },
      });
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not save (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      const prefs = parsePrefs(data);
      if (prefs) {
        setDigestEnabled(prefs.digest_enabled);
        setQuietStart(hourValue(prefs.quiet_hours_start));
        setQuietEnd(hourValue(prefs.quiet_hours_end));
      }
      toast.success("Settings saved.");
      router.refresh();
    } catch {
      const msg = "Network error. Try again.";
      setError(msg);
      toast.error(msg);
    } finally {
      setPending(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="mt-8 rounded-lg border border-border/70 p-4 sm:p-5"
      noValidate
    >
      <div className="flex flex-col gap-6">
        <section className="flex flex-col gap-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Label htmlFor="digest_enabled">Digest mode</Label>
              <p className="mt-1 text-sm text-muted-foreground">
                Batch eligible alerts into the digest path when supported.
                Immediate Telegram pushes remain the primary surface.
              </p>
            </div>
            <input
              id="digest_enabled"
              name="digest_enabled"
              type="checkbox"
              checked={digestEnabled}
              onChange={(e) => setDigestEnabled(e.target.checked)}
              className="mt-1 h-5 w-5 rounded border-border text-foreground accent-foreground"
            />
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="quiet_hours_start">Quiet hours start (SLT)</Label>
            <select
              id="quiet_hours_start"
              name="quiet_hours_start"
              value={quietStart}
              onChange={(e) => setQuietStart(e.target.value)}
              className="h-10 rounded-lg border border-input bg-transparent px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <option value="">Off</option>
              {HOURS.map((hour) => (
                <option key={hour} value={hour}>
                  {formatHour(hour)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="quiet_hours_end">Quiet hours end (SLT)</Label>
            <select
              id="quiet_hours_end"
              name="quiet_hours_end"
              value={quietEnd}
              onChange={(e) => setQuietEnd(e.target.value)}
              className="h-10 rounded-lg border border-input bg-transparent px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <option value="">Off</option>
              {HOURS.map((hour) => (
                <option key={hour} value={hour}>
                  {formatHour(hour)}
                </option>
              ))}
            </select>
          </div>
          <p className="text-xs text-muted-foreground sm:col-span-2">
            Hours are Asia/Colombo (SLT). Set both ends, or leave both Off.
            Overnight windows work (e.g. 22:00→06:00). During quiet hours
            Telegram pushes are held and delivered after the window ends — not
            dropped. Same start and end turns quiet hours off.
          </p>
        </section>

        <section className="rounded-md bg-muted/40 p-3 text-sm text-muted-foreground">
          Active alert quota:{" "}
          <span className="font-mono text-foreground tabular-nums">
            {initial.alert_quota_max}
          </span>
        </section>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={pending} aria-busy={pending || undefined}>
            {pending ? "Saving…" : "Save settings"}
          </Button>
          <InlineError id="settings_form_error" message={error} />
        </div>
      </div>
    </form>
  );
}
