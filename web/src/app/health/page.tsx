import { AppNav } from "@/components/app-nav";
import { NfaFooter } from "@/components/nfa-footer";
import { serverApiGet } from "@/lib/api/server-fetch";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Health · Chime",
  description: "Ops liveness for Chime poller and Postgres.",
};

type HealthPayload = {
  status: "ok" | "degraded";
  db_ok: boolean;
  started_at: string | null;
  last_snapshot_at: string | null;
  poller: {
    last_tick_at?: string | null;
    last_tick_ok?: boolean;
    price_poll_ok?: boolean;
    disclosure_poll_ok?: boolean;
    lock_held_skip?: boolean;
    last_error?: string | null;
  } | null;
};

export default async function HealthPage() {
  await requirePageSession();

  const res = await serverApiGet("/api/v1/health");
  let payload: HealthPayload | null = null;
  try {
    payload = (await res.json()) as HealthPayload;
  } catch {
    payload = null;
  }

  const status = payload?.status ?? "degraded";
  const ok = status === "ok";

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/health" />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          Health
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Read-only ops view — database ping and optional poller status. No
          deploy controls here.
        </p>

        {!payload ? (
          <p className="mt-8 text-sm text-muted-foreground">
            Health endpoint unreachable.
          </p>
        ) : (
          <>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center rounded-md px-3 py-1 text-sm font-medium ${
                  ok
                    ? "bg-[oklch(0.92_0.04_165)] text-[oklch(0.35_0.08_165)]"
                    : "bg-[oklch(0.93_0.04_40)] text-[oklch(0.4_0.1_40)]"
                }`}
              >
                {status}
              </span>
              <span className="text-sm text-muted-foreground">
                HTTP {res.status}
              </span>
            </div>

            <dl className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2">
              <Row label="Database" value={payload.db_ok ? "ok" : "down"} />
              <Row label="Started" value={formatTs(payload.started_at)} />
              <Row
                label="Last snapshot"
                value={formatTs(payload.last_snapshot_at)}
              />
            </dl>

            <section className="mt-10 border-t border-border/60 pt-6">
              <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                Poller
              </h2>
              {payload.poller == null ? (
                <p className="mt-3 text-sm text-muted-foreground">
                  No poller detail (HEALTH_URL unset). DB liveness only.
                </p>
              ) : (
                <dl className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <Row
                    label="Last tick"
                    value={formatTs(payload.poller.last_tick_at ?? null)}
                  />
                  <Row
                    label="Last tick ok"
                    value={boolLabel(payload.poller.last_tick_ok)}
                  />
                  <Row
                    label="Price poll"
                    value={boolLabel(payload.poller.price_poll_ok)}
                  />
                  <Row
                    label="Disclosure poll"
                    value={boolLabel(payload.poller.disclosure_poll_ok)}
                  />
                  <Row
                    label="Lock skip"
                    value={boolLabel(payload.poller.lock_held_skip)}
                  />
                  <Row
                    label="Last error"
                    value={payload.poller.last_error ?? "—"}
                  />
                </dl>
              )}
            </section>
          </>
        )}
      </main>
      <NfaFooter />
    </div>
  );
}

function boolLabel(v: boolean | undefined): string {
  if (v === true) return "yes";
  if (v === false) return "no";
  return "—";
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-b border-border/40 pb-3 sm:border-0 sm:pb-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words font-mono text-sm text-foreground">
        {value}
      </dd>
    </div>
  );
}
