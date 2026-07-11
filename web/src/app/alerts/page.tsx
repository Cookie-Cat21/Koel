import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { NfaFooter } from "@/components/nfa-footer";
import { serverApiGet } from "@/lib/api/server-fetch";
import { requirePageSession } from "@/lib/auth/page-session";
import { alertTypeLabel, formatNumber, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Alerts · Chime",
  description: "Active alert rules for your Chime watchlist.",
};

type AlertsPayload = {
  rules: {
    id: number;
    symbol: string;
    type: string;
    threshold: number | null;
    active: boolean;
    armed: boolean;
    created_at: string | null;
  }[];
};

export default async function AlertsPage() {
  await requirePageSession();

  const res = await serverApiGet("/api/v1/alerts");
  const payload: AlertsPayload | null = res.ok
    ? ((await res.json()) as AlertsPayload)
    : null;

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/alerts" />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          Alerts
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Active rules. Create and cancel from Telegram for now (
          <code className="font-mono text-xs">/alert</code>,{" "}
          <code className="font-mono text-xs">/cancel</code>).
        </p>

        {!payload ? (
          <p className="mt-8 text-sm text-muted-foreground">
            Could not load alerts right now.
          </p>
        ) : payload.rules.length === 0 ? (
          <p className="mt-8 text-sm text-muted-foreground">
            No active alerts. Set one with{" "}
            <code className="font-mono text-xs">/alert SYMBOL above PRICE</code>{" "}
            in Telegram.
          </p>
        ) : (
          <ul className="mt-8 divide-y divide-border/60">
            {payload.rules.map((rule) => (
              <li
                key={rule.id}
                className="flex flex-col gap-1 py-4 first:pt-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4"
              >
                <div className="min-w-0">
                  <Link
                    href={`/symbols/${encodeURIComponent(rule.symbol)}`}
                    className="font-mono text-sm font-medium underline-offset-4 hover:underline"
                  >
                    {rule.symbol}
                  </Link>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    #{rule.id} · {alertTypeLabel(rule.type)}
                    {rule.threshold != null
                      ? ` · ${formatNumber(rule.threshold)}`
                      : ""}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>{rule.armed ? "Armed" : "Disarmed"}</span>
                  <span>·</span>
                  <span>{formatTs(rule.created_at)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-8 text-xs text-muted-foreground">
          Information only — not financial advice.
        </p>
      </main>
      <NfaFooter />
    </div>
  );
}
