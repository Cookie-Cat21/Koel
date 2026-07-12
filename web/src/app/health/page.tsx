import { AppNav } from "@/components/app-nav";
import { NfaFooter } from "@/components/nfa-footer";
import {
  MAX_HISTORY_SYMBOL_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toNonNegativeSafeInt } from "@/lib/api/safe-int";
import { serverApiGet } from "@/lib/api/server-fetch";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Health · Chime",
  description: "Ops liveness for Chime poller and Postgres.",
};

/** Health timestamps older than this need explicit ops attention. */
const STALE_HEALTH_AGE_MS = 24 * 60 * 60 * 1000;
const HEALTH_UI_STRING_MAX = 512;
const HEALTH_UI_WATCHED_MAX = 64;
const HEALTH_UI_CIRCUITS_MAX = 32;

type BriefQueueHint = {
  pending_briefs?: number;
  pdf_enrich?: {
    in_flight_tasks?: number;
    last_batch_size?: number;
    batches_started?: number;
  };
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
    watched_missing?: string[];
    circuits?: Record<string, { state?: string; failures?: number }>;
    /** Ops hint only — omit section when absent. */
    brief_queue?: BriefQueueHint;
  } | null;
};

function healthUiString(raw: unknown): string | null {
  return sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    HEALTH_UI_STRING_MAX,
  );
}

/**
 * Fail-closed health UI parse — hostile / wrong-shape JSON must not 500 the
 * ops page or render unbounded strings / unsafe React keys.
 */
function parseHealthPayload(body: unknown): HealthPayload | null {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const r = body as Record<string, unknown>;
  const status = r.status === "ok" || r.status === "degraded" ? r.status : null;
  if (!status) return null;
  if (typeof r.db_ok !== "boolean") return null;

  let poller: HealthPayload["poller"] = null;
  if (r.poller != null && typeof r.poller === "object" && !Array.isArray(r.poller)) {
    const p = r.poller as Record<string, unknown>;
    const watched: string[] = [];
    if (Array.isArray(p.watched_missing)) {
      for (const item of p.watched_missing) {
        const sym =
          sanitizeDisclosureText(
            typeof item === "string" ? item : null,
            MAX_HISTORY_SYMBOL_LENGTH,
          ) ?? "";
        if (!sym) continue;
        watched.push(sym);
        if (watched.length >= HEALTH_UI_WATCHED_MAX) break;
      }
    }

    let circuits: NonNullable<
      NonNullable<HealthPayload["poller"]>["circuits"]
    > | undefined;
    if (p.circuits != null && typeof p.circuits === "object" && !Array.isArray(p.circuits)) {
      circuits = {};
      for (const [key, value] of Object.entries(
        p.circuits as Record<string, unknown>,
      )) {
        if (Object.keys(circuits).length >= HEALTH_UI_CIRCUITS_MAX) break;
        const name = healthUiString(key);
        if (!name || name.length > 64) continue;
        if (value == null || typeof value !== "object" || Array.isArray(value)) {
          continue;
        }
        const snap = value as Record<string, unknown>;
        const state =
          typeof snap.state === "string" ? healthUiString(snap.state) : null;
        const failuresRaw = toNonNegativeSafeInt(snap.failures, -1);
        const failures = failuresRaw >= 0 ? failuresRaw : undefined;
        circuits[name] = {
          ...(state ? { state } : {}),
          ...(failures !== undefined ? { failures } : {}),
        };
      }
      if (Object.keys(circuits).length === 0) circuits = undefined;
    }

    let brief_queue: BriefQueueHint | undefined;
    if (
      p.brief_queue != null &&
      typeof p.brief_queue === "object" &&
      !Array.isArray(p.brief_queue)
    ) {
      const bq = p.brief_queue as Record<string, unknown>;
      const hint: BriefQueueHint = {};
      const pending = toNonNegativeSafeInt(bq.pending_briefs, -1);
      if (pending >= 0) hint.pending_briefs = pending;
      if (
        bq.pdf_enrich != null &&
        typeof bq.pdf_enrich === "object" &&
        !Array.isArray(bq.pdf_enrich)
      ) {
        const pe = bq.pdf_enrich as Record<string, unknown>;
        const pdf: NonNullable<BriefQueueHint["pdf_enrich"]> = {};
        for (const key of [
          "in_flight_tasks",
          "last_batch_size",
          "batches_started",
        ] as const) {
          const n = toNonNegativeSafeInt(pe[key], -1);
          if (n >= 0) pdf[key] = n;
        }
        if (Object.keys(pdf).length > 0) hint.pdf_enrich = pdf;
      }
      if (Object.keys(hint).length > 0) brief_queue = hint;
    }

    poller = {
      last_tick_at:
        p.last_tick_at === null
          ? null
          : typeof p.last_tick_at === "string"
            ? healthUiString(p.last_tick_at)
            : undefined,
      last_tick_ok:
        typeof p.last_tick_ok === "boolean" ? p.last_tick_ok : undefined,
      price_poll_ok:
        typeof p.price_poll_ok === "boolean" ? p.price_poll_ok : undefined,
      disclosure_poll_ok:
        typeof p.disclosure_poll_ok === "boolean"
          ? p.disclosure_poll_ok
          : undefined,
      lock_held_skip:
        typeof p.lock_held_skip === "boolean" ? p.lock_held_skip : undefined,
      last_error:
        p.last_error === null
          ? null
          : typeof p.last_error === "string"
            ? healthUiString(p.last_error)
            : undefined,
      watched_missing: watched,
      circuits,
      brief_queue,
    };
  } else if (r.poller === null) {
    poller = null;
  }

  return {
    status,
    db_ok: r.db_ok,
    started_at:
      typeof r.started_at === "string" ? healthUiString(r.started_at) : null,
    last_snapshot_at:
      typeof r.last_snapshot_at === "string"
        ? healthUiString(r.last_snapshot_at)
        : null,
    poller,
  };
}

export default async function HealthPage() {
  await requirePageSession();

  const res = await serverApiGet("/api/v1/health");
  let payload: HealthPayload | null = null;
  try {
    payload = parseHealthPayload(await res.json());
  } catch {
    payload = null;
  }

  const status = payload?.status ?? "degraded";
  const ok = status === "ok";
  const missing = payload?.poller?.watched_missing ?? [];
  const circuits = payload?.poller?.circuits ?? null;
  const briefQueue = payload?.poller?.brief_queue ?? null;
  const snapshotAge = timestampAge(payload?.last_snapshot_at);
  const tickAge = timestampAge(payload?.poller?.last_tick_at);
  const pollerUnreachable =
    payload?.poller?.last_error === "health_url_unreachable";
  const pollerDegraded =
    payload?.poller != null &&
    !pollerUnreachable &&
    (payload.poller.last_tick_ok === false ||
      payload.poller.price_poll_ok === false ||
      payload.poller.disclosure_poll_ok === false ||
      missing.length > 0);
  const statusLabel = pollerUnreachable ? "poller unreachable" : status;

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/health" />
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
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
                className={`inline-flex items-center rounded-md px-3 py-1 text-sm font-medium ${statusToneClass(
                  ok,
                  pollerUnreachable,
                )}`}
              >
                {statusLabel}
              </span>
              <span className="text-sm text-muted-foreground">
                HTTP {res.status}
              </span>
            </div>

            {pollerUnreachable ? (
              <OpsNotice
                tone="danger"
                title="Poller health unreachable"
                copy="HEALTH_URL is configured, but the dashboard could not reach the poller health endpoint. DB liveness is separate; check HEALTH_URL, routing, and the poller process before trusting alert freshness."
              />
            ) : pollerDegraded ? (
              <OpsNotice
                tone="warning"
                title="Poller reachable but degraded"
                copy="The poller health endpoint responded, but one or more poller checks reported unhealthy. Review tick flags, price/disclosure poll flags, watched-missing symbols, circuits, and recent poller logs."
              />
            ) : null}

            <dl className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2">
              <Row label="Database" value={payload.db_ok ? "ok" : "down"} />
              <Row label="Started" value={formatTs(payload.started_at)} />
              <Row
                label="Last snapshot"
                value={formatTs(payload.last_snapshot_at)}
              />
              <Row
                label="Last snapshot age"
                value={formatAge(snapshotAge)}
              />
            </dl>

            {snapshotAge?.stale ? (
              <StaleOpsNotice
                title="Snapshot age is stale"
                copy={`Last stored price snapshot is ${formatAge(snapshotAge)} old. Ops: confirm the poller is running during market hours and writing price_snapshots to Postgres.`}
              />
            ) : null}

            <section className="mt-10 border-t border-border/60 pt-6">
              <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                Poller
              </h2>
              {payload.poller == null ? (
                <p className="mt-3 text-sm text-muted-foreground">
                  No poller detail (HEALTH_URL unset). DB liveness only.
                </p>
              ) : (
                <>
                  {pollerUnreachable ? (
                    <p className="mt-3 text-sm text-muted-foreground">
                      The rows below are synthesized by the web proxy because
                      the configured poller health URL did not respond.
                    </p>
                  ) : pollerDegraded ? (
                    <p className="mt-3 text-sm text-muted-foreground">
                      HEALTH_URL responded; degradation is coming from the
                      poller fields below.
                    </p>
                  ) : null}
                  <dl className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">
                    <Row
                      label="Last tick"
                      value={formatTs(payload.poller.last_tick_at ?? null)}
                    />
                    <Row label="Last tick age" value={formatAge(tickAge)} />
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
                </>
              )}
              {tickAge?.stale ? (
                <StaleOpsNotice
                  title="Poller tick age is stale"
                  copy={`Last poller tick is ${formatAge(tickAge)} old. Ops: check HEALTH_URL, the poller process, and recent poller logs before trusting green DB liveness.`}
                />
              ) : null}
            </section>

            {payload.poller != null && (
              <section className="mt-10 border-t border-border/60 pt-6">
                <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                  Watched missing
                </h2>
                {missing.length === 0 ? (
                  <p className="mt-3 text-sm text-muted-foreground">
                    None — all watched symbols appeared in the latest trade
                    summary.
                  </p>
                ) : (
                  <ul className="mt-3 list-inside list-disc font-mono text-sm text-foreground">
                    {missing.map((sym) => (
                      <li key={sym}>{sym}</li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {circuits != null && Object.keys(circuits).length > 0 && (
              <section className="mt-10 border-t border-border/60 pt-6">
                <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                  Circuits
                </h2>
                <dl className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">
                  {Object.entries(circuits).map(([name, snap]) => (
                    <Row
                      key={name}
                      label={name}
                      value={`${snap?.state ?? "—"} (failures ${String(snap?.failures ?? "—")})`}
                    />
                  ))}
                </dl>
              </section>
            )}

            {briefQueue != null && (
              <section className="mt-10 border-t border-border/60 pt-6">
                <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                  Brief queue
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Ops hint only — does not change health status.
                </p>
                <dl className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <Row
                    label="Pending briefs"
                    value={
                      typeof briefQueue.pending_briefs === "number"
                        ? String(briefQueue.pending_briefs)
                        : "—"
                    }
                  />
                  <Row
                    label="PDF enrich in-flight"
                    value={
                      typeof briefQueue.pdf_enrich?.in_flight_tasks === "number"
                        ? String(briefQueue.pdf_enrich.in_flight_tasks)
                        : "—"
                    }
                  />
                  <Row
                    label="PDF enrich last batch"
                    value={
                      typeof briefQueue.pdf_enrich?.last_batch_size === "number"
                        ? String(briefQueue.pdf_enrich.last_batch_size)
                        : "—"
                    }
                  />
                  <Row
                    label="PDF enrich batches started"
                    value={
                      typeof briefQueue.pdf_enrich?.batches_started === "number"
                        ? String(briefQueue.pdf_enrich.batches_started)
                        : "—"
                    }
                  />
                </dl>
              </section>
            )}
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

type TimestampAge = {
  ageMs: number;
  stale: boolean;
};

function timestampAge(iso: string | null | undefined): TimestampAge | null {
  if (!iso) return null;
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return null;
  const ageMs = Math.max(0, Date.now() - ts);
  return {
    ageMs,
    stale: ageMs > STALE_HEALTH_AGE_MS,
  };
}

function formatAge(age: TimestampAge | null): string {
  if (!age) return "—";
  const totalMinutes = Math.max(0, Math.floor(age.ageMs / 60000));
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function statusToneClass(ok: boolean, pollerUnreachable: boolean): string {
  if (ok) {
    return "bg-[oklch(0.92_0.04_165)] text-[oklch(0.35_0.08_165)]";
  }
  if (pollerUnreachable) {
    return "bg-[oklch(0.94_0.04_25)] text-[oklch(0.38_0.12_25)]";
  }
  return "bg-[oklch(0.93_0.04_40)] text-[oklch(0.4_0.1_40)]";
}

function OpsNotice({
  tone,
  title,
  copy,
}: {
  tone: "danger" | "warning";
  title: string;
  copy: string;
}) {
  const className =
    tone === "danger"
      ? "border-[oklch(0.72_0.12_25)] bg-[oklch(0.97_0.03_25)]"
      : "border-[oklch(0.78_0.08_65)] bg-[oklch(0.97_0.03_80)]";
  const titleClassName =
    tone === "danger"
      ? "text-[oklch(0.36_0.13_25)]"
      : "text-[oklch(0.36_0.1_55)]";
  const copyClassName =
    tone === "danger"
      ? "text-[oklch(0.32_0.09_25)]"
      : "text-[oklch(0.32_0.07_55)]";

  return (
    <div className={`mt-5 rounded-lg border p-4 ${className}`}>
      <p className={`text-sm font-medium ${titleClassName}`}>{title}</p>
      <p className={`mt-1 text-sm ${copyClassName}`}>{copy}</p>
    </div>
  );
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

function StaleOpsNotice({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="mt-5 rounded-lg border border-[oklch(0.78_0.08_65)] bg-[oklch(0.97_0.03_80)] p-4">
      <p className="text-sm font-medium text-[oklch(0.36_0.1_55)]">
        {title}
      </p>
      <p className="mt-1 text-sm text-[oklch(0.32_0.07_55)]">{copy}</p>
    </div>
  );
}
