"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError } from "@/components/inline-error";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { apiErrorMessage, apiMutate } from "@/lib/api/client-fetch";
import {
  FILING_CATEGORY_LABELS,
  FILING_CATEGORY_TAGS,
  normalizeFilingTags,
  type FilingCategoryTag,
} from "@/lib/api/filing-categories";

export type SettingsPreferences = {
  digest_enabled: boolean;
  quiet_hours_start: number | null;
  quiet_hours_end: number | null;
  alert_quota_max: number;
  watchlist_auto_move_pct: number | null;
  disclosure_category_prefs: FilingCategoryTag[];
  tv_webhook_token: string | null;
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
    start === null ||
    (typeof start === "number" &&
      Number.isSafeInteger(start) &&
      start >= 0 &&
      start <= 23)
      ? start
      : undefined;
  const normalizedEnd =
    end === null ||
    (typeof end === "number" &&
      Number.isSafeInteger(end) &&
      end >= 0 &&
      end <= 23)
      ? end
      : undefined;
  if (normalizedStart === undefined || normalizedEnd === undefined) return null;
  if (typeof quota !== "number" || !Number.isSafeInteger(quota) || quota < 0) {
    return null;
  }
  const auto =
    r.watchlist_auto_move_pct === null
      ? null
      : typeof r.watchlist_auto_move_pct === "number" &&
          Number.isFinite(r.watchlist_auto_move_pct)
        ? r.watchlist_auto_move_pct
        : null;
  const token =
    typeof r.tv_webhook_token === "string" && r.tv_webhook_token.trim()
      ? r.tv_webhook_token.trim()
      : null;
  return {
    digest_enabled: digest,
    quiet_hours_start: normalizedStart,
    quiet_hours_end: normalizedEnd,
    alert_quota_max: quota,
    watchlist_auto_move_pct: auto,
    disclosure_category_prefs: normalizeFilingTags(r.disclosure_category_prefs),
    tv_webhook_token: token,
  };
}

export function SettingsForm({ initial }: { initial: SettingsPreferences }) {
  const router = useRouter();
  const toast = useToast();
  const [digestEnabled, setDigestEnabled] = useState(initial.digest_enabled);
  const [quietStart, setQuietStart] = useState(hourValue(initial.quiet_hours_start));
  const [quietEnd, setQuietEnd] = useState(hourValue(initial.quiet_hours_end));
  const [autoMove, setAutoMove] = useState(initial.watchlist_auto_move_pct != null);
  const [categories, setCategories] = useState<FilingCategoryTag[]>(
    initial.disclosure_category_prefs.length > 0
      ? initial.disclosure_category_prefs
      : [...FILING_CATEGORY_TAGS],
  );
  const [webhookToken, setWebhookToken] = useState(initial.tv_webhook_token);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function toggleCategory(tag: FilingCategoryTag) {
    setCategories((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    );
  }

  async function save(extra: Record<string, unknown> = {}) {
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
    if (categories.length === 0) {
      setError("Keep at least one filing category, or check all for unrestricted.");
      return;
    }
    // All checked → unrestricted (store []).
    const prefsOut =
      categories.length === FILING_CATEGORY_TAGS.length ? [] : categories;

    setPending(true);
    try {
      const { ok, status, data } = await apiMutate("/api/v1/me/preferences", {
        method: "PATCH",
        body: {
          digest_enabled: digestEnabled,
          quiet_hours_start: start,
          quiet_hours_end: end,
          watchlist_auto_move_pct: autoMove ? 5 : null,
          disclosure_category_prefs: prefsOut,
          ...extra,
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
        setAutoMove(prefs.watchlist_auto_move_pct != null);
        setCategories(
          prefs.disclosure_category_prefs.length > 0
            ? prefs.disclosure_category_prefs
            : [...FILING_CATEGORY_TAGS],
        );
        setWebhookToken(prefs.tv_webhook_token);
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

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    await save();
  }

  const webhookUrl =
    typeof window !== "undefined" && webhookToken
      ? `${window.location.origin}/api/v1/hooks/tradingview?token=${encodeURIComponent(webhookToken)}`
      : webhookToken
        ? `/api/v1/hooks/tradingview?token=${encodeURIComponent(webhookToken)}`
        : null;

  return (
    <form
      onSubmit={onSubmit}
      className="mt-8 space-y-6"
      noValidate
    >
      <section className="rounded-lg border border-border/70 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Label htmlFor="digest_enabled">Close digest</Label>
            <p className="mt-1 text-sm text-muted-foreground">
              After the cash session, batch watchlist movers and fires into one
              Telegram summary (≈14:30–16:00 SLT).
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

      <section className="rounded-lg border border-border/70 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Label htmlFor="auto_move">Watchlist auto 5% move</Label>
            <p className="mt-1 text-sm text-muted-foreground">
              Arm a daily ±5% move alert for every symbol on your watchlist
              (Robinhood / Groww style). New watches pick it up automatically.
            </p>
          </div>
          <input
            id="auto_move"
            name="auto_move"
            type="checkbox"
            checked={autoMove}
            onChange={(e) => setAutoMove(e.target.checked)}
            className="mt-1 h-5 w-5 rounded border-border text-foreground accent-foreground"
          />
        </div>
      </section>

      <section className="rounded-lg border border-border/70 p-4 sm:p-5">
        <Label>Filing categories (disclosure alerts)</Label>
        <p className="mt-1 text-sm text-muted-foreground">
          When a disclosure rule has no category filter, only these tags can
          fire. Leave all checked for unrestricted (Tijori-style chips).
        </p>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {FILING_CATEGORY_TAGS.map((tag) => (
            <label
              key={tag}
              className="flex items-center gap-2 text-sm text-foreground"
            >
              <input
                type="checkbox"
                checked={categories.includes(tag)}
                onChange={() => toggleCategory(tag)}
                className="h-4 w-4 rounded border-border accent-foreground"
              />
              {FILING_CATEGORY_LABELS[tag]}
            </label>
          ))}
        </div>
      </section>

      <section className="grid gap-4 rounded-lg border border-border/70 p-4 sm:grid-cols-2 sm:p-5">
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
          Hours are Asia/Colombo (SLT). During quiet hours Telegram pushes are
          held and delivered after the window ends.
        </p>
      </section>

      <section className="rounded-lg border border-border/70 p-4 sm:p-5">
        <Label>TradingView → Telegram webhook</Label>
        <p className="mt-1 text-sm text-muted-foreground">
          Optional power-user path: paste this URL into a TradingView alert
          webhook. koel still uses its own poller for CSE truth.
        </p>
        {webhookUrl ? (
          <code className="mt-3 block break-all rounded-md bg-muted/50 p-3 text-xs">
            {webhookUrl}
          </code>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            No token yet — generate one to enable inbound alerts.
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={pending}
            onClick={() => void save({ rotate_tv_webhook_token: true })}
          >
            {webhookToken ? "Rotate token" : "Generate token"}
          </Button>
          {webhookToken ? (
            <Button
              type="button"
              variant="ghost"
              disabled={pending}
              onClick={() => void save({ clear_tv_webhook_token: true })}
            >
              Clear token
            </Button>
          ) : null}
        </div>
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
    </form>
  );
}
