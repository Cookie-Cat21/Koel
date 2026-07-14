import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { PageHeader } from "@/components/page-header";
import { SettingsForm, type SettingsPreferences } from "@/components/settings-form";
import { Button } from "@/components/ui/button";
import { serverApiGet } from "@/lib/api/server-fetch";
import { toNonNegativeSafeInt } from "@/lib/api/safe-int";
import { requirePageSession } from "@/lib/auth/page-session";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Settings · Chime",
  description: "Telegram delivery preferences for Chime alerts.",
};

function quietHour(raw: unknown): number | null | undefined {
  if (raw === null) return null;
  const n = toNonNegativeSafeInt(raw, -1);
  return n >= 0 && n <= 23 ? n : undefined;
}

function parsePreferences(body: unknown): SettingsPreferences | null {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const r = body as Record<string, unknown>;
  if (typeof r.digest_enabled !== "boolean") return null;
  const start = quietHour(r.quiet_hours_start);
  const end = quietHour(r.quiet_hours_end);
  if (start === undefined || end === undefined) return null;
  const quota = toNonNegativeSafeInt(r.alert_quota_max, -1);
  if (quota < 0) return null;
  return {
    digest_enabled: r.digest_enabled,
    quiet_hours_start: start,
    quiet_hours_end: end,
    alert_quota_max: quota,
  };
}

export default async function SettingsPage() {
  await requirePageSession();

  const res = await serverApiGet("/api/v1/me/preferences");
  let prefs: SettingsPreferences | null = null;
  if (res.ok) {
    try {
      prefs = parsePreferences(await res.json());
    } catch {
      prefs = null;
    }
  }

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/settings" />
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <PageHeader
          eyebrow="Account"
          title="Settings"
          description="Manage digest and quiet-hour preferences. Chime still sends actionable alerts through Telegram."
        />

        {prefs ? (
          <SettingsForm initial={prefs} />
        ) : (
          <EmptyState
            title="Couldn’t load settings"
            description="Chime couldn’t fetch your delivery preferences right now. Refresh in a moment, or keep using Telegram commands while the dashboard recovers."
            action={
              <Button asChild variant="outline">
                <Link href="/settings">Try again</Link>
              </Button>
            }
          />
        )}
      </main>
      <NfaFooter />
    </div>
  );
}
