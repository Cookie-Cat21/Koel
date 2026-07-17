import {
  Activity,
  Crosshair,
  Database,
  LineChart,
  Radio,
  Sparkles,
  Timer,
  Trophy,
} from "lucide-react";
import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { AlertBanner } from "@/components/kit/alert-banner";
import { StatCard } from "@/components/kit/stat-card";
import { LiveIndicator } from "@/components/live-indicator";
import { NfaFooter } from "@/components/nfa-footer";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { sanitizeDisclosureText } from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { toNonNegativeSafeInt } from "@/lib/api/safe-int";
import { serverApiGet } from "@/lib/api/server-fetch";
import { normalizeSymbol } from "@/lib/api/symbol";
import { MAX_DATE_MS, toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Health · Chime",
  description: "Ops liveness for Chime poller and Postgres.",
};

/** Health timestamps older than this need explicit ops attention. */
const STALE_HEALTH_AGE_MS = 24 * 60 * 60 * 1000;
/** Cap age label digits — extreme past timestamps used to balloon ``Nd``. */
const MAX_HEALTH_AGE_DAYS = 9_999;
const HEALTH_UI_STRING_MAX = 512;
const HEALTH_UI_WATCHED_MAX = 64;
const HEALTH_UI_CIRCUITS_MAX = 32;
const CIRCUIT_STATES = new Set(["closed", "open", "half_open"]);

type BriefQueueHint = {
  pending_briefs?: number;
  pdf_enrich?: {
    in_flight_tasks?: number;
    last_batch_size?: number;
    batches_started?: number;
  };
};

type MlHealthBlock = {
  champion: {
    model_id: string;
    oos_hit: number | null;
    oos_gated_hit: number | null;
    oos_coverage: number | null;
    status: string;
  } | null;
  scoreboard: {
    hit_20d: number | null;
    hit_60d: number | null;
    gated_hit_20d: number | null;
    n_scored_60d: number;
  };
  accrual: {
    market_summary_days: number;
    order_book_snapshots: number;
    latest_order_book_at: string | null;
    forecast_points_latest_as_of: string | null;
    spoke_symbols_latest: number;
  };
  disclaimer: string;
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
  delivery?: {
    delivered_24h: number;
    retrying: number;
    dead_lettered: number;
  };
  retention?: {
    snapshot_retention_days: number;
  };
  ml?: MlHealthBlock | null;
};

function healthUiString(raw: unknown): string | null {
  return sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    HEALTH_UI_STRING_MAX,
  );
}

/** Fail-closed timestamp — sanitize then require parseable ISO (no raw echo). */
function healthTs(raw: unknown): string | null {
  if (raw === null) return null;
  if (typeof raw !== "string") return null;
  const cleaned = healthUiString(raw);
  return cleaned ? toIso(cleaned) : null;
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
        // Fail closed — only CSE SYMBOL_RE (no sanitize length-cap fallback).
        const sym = normalizeSymbol(item);
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
        // Allowlist only — sanitize-alone used to echo hostile circuit states.
        const stateRaw =
          typeof snap.state === "string" ? healthUiString(snap.state) : null;
        const state =
          stateRaw && CIRCUIT_STATES.has(stateRaw) ? stateRaw : null;
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
        p.last_tick_at === null ? null : healthTs(p.last_tick_at) ?? undefined,
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
    started_at: healthTs(r.started_at),
    last_snapshot_at: healthTs(r.last_snapshot_at),
    poller,
    delivery: parseDelivery(r.delivery),
    retention: parseRetention(r.retention),
    ml: parseMl(r.ml),
  };
}

function pctLabel(raw: number | null | undefined): string {
  if (raw == null || !Number.isFinite(raw)) return "—";
  return `${(raw * 100).toFixed(1)}%`;
}

/** Short label for long registry ids; full id stays in title / subtitle. */
function championShortId(modelId: string | null | undefined): string {
  if (!modelId) return "—";
  const trimmed = modelId.trim();
  // challenger_gated_c55_20260717 → gated_c55
  const m = trimmed.match(
    /(?:challenger_|champion_)?(gated_p90|gated_ltr|gated_c55|gated|hpe_p90|fin_sector|ltr)(?:_|$)/i,
  );
  if (m?.[1]) return m[1];
  if (trimmed.length <= 28) return trimmed;
  return `${trimmed.slice(0, 22)}…`;
}

function toneForHit(rate: number | null | undefined): "ok" | "warn" | "muted" {
  if (rate == null || !Number.isFinite(rate)) return "muted";
  if (rate >= 0.7) return "ok";
  if (rate >= 0.55) return "warn";
  return "muted";
}

function hitToneClass(tone: "ok" | "warn" | "muted"): string {
  if (tone === "ok") {
    return "border-emerald-500/35 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200";
  }
  if (tone === "warn") {
    return "border-amber-500/35 bg-amber-500/10 text-amber-900 dark:text-amber-100";
  }
  return "border-border/70 bg-muted/40 text-muted-foreground";
}

function parseMl(raw: unknown): MlHealthBlock | null {
  if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const m = raw as Record<string, unknown>;
  let champion: MlHealthBlock["champion"] = null;
  if (m.champion != null && typeof m.champion === "object" && !Array.isArray(m.champion)) {
    const c = m.champion as Record<string, unknown>;
    const modelId =
      typeof c.model_id === "string" ? c.model_id.trim().slice(0, 128) : "";
    if (modelId) {
      champion = {
        model_id: modelId,
        oos_hit: toFiniteNumber(c.oos_hit),
        oos_gated_hit: toFiniteNumber(c.oos_gated_hit),
        oos_coverage: toFiniteNumber(c.oos_coverage),
        status:
          typeof c.status === "string" ? c.status.trim().slice(0, 32) : "champion",
      };
    }
  }
  const sb =
    m.scoreboard != null &&
    typeof m.scoreboard === "object" &&
    !Array.isArray(m.scoreboard)
      ? (m.scoreboard as Record<string, unknown>)
      : {};
  const ac =
    m.accrual != null &&
    typeof m.accrual === "object" &&
    !Array.isArray(m.accrual)
      ? (m.accrual as Record<string, unknown>)
      : {};
  return {
    champion,
    scoreboard: {
      hit_20d: toFiniteNumber(sb.hit_20d),
      hit_60d: toFiniteNumber(sb.hit_60d),
      gated_hit_20d: toFiniteNumber(sb.gated_hit_20d),
      n_scored_60d: Math.max(0, toNonNegativeSafeInt(sb.n_scored_60d, 0)),
    },
    accrual: {
      market_summary_days: Math.max(
        0,
        toNonNegativeSafeInt(ac.market_summary_days, 0),
      ),
      order_book_snapshots: Math.max(
        0,
        toNonNegativeSafeInt(ac.order_book_snapshots, 0),
      ),
      latest_order_book_at: healthTs(ac.latest_order_book_at),
      forecast_points_latest_as_of:
        typeof ac.forecast_points_latest_as_of === "string"
          ? ac.forecast_points_latest_as_of.slice(0, 10)
          : null,
      spoke_symbols_latest: Math.max(
        0,
        toNonNegativeSafeInt(ac.spoke_symbols_latest, 0),
      ),
    },
    disclaimer:
      typeof m.disclaimer === "string" && m.disclaimer.trim()
        ? sanitizeDisclosureText(m.disclaimer, HEALTH_UI_STRING_MAX) ||
          "Research metrics only — not financial advice."
        : "Research metrics only — not financial advice.",
  };
}

function parseDelivery(raw: unknown): HealthPayload["delivery"] {
  if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
    return undefined;
  }
  const d = raw as Record<string, unknown>;
  const delivered = toNonNegativeSafeInt(d.delivered_24h, -1);
  const retrying = toNonNegativeSafeInt(d.retrying, -1);
  const dead = toNonNegativeSafeInt(d.dead_lettered, -1);
  if (delivered < 0 || retrying < 0 || dead < 0) return undefined;
  return {
    delivered_24h: delivered,
    retrying,
    dead_lettered: dead,
  };
}

function parseRetention(raw: unknown): HealthPayload["retention"] {
  if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
    return undefined;
  }
  const days = toNonNegativeSafeInt(
    (raw as Record<string, unknown>).snapshot_retention_days,
    -1,
  );
  if (days < 0) return undefined;
  return { snapshot_retention_days: days };
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
  const delivery = payload?.delivery ?? null;
  const retention = payload?.retention ?? null;
  const ml = payload?.ml ?? null;
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
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <PageHeader
          eyebrow="Ops"
          title="Health"
          description="Read-only ops view — database ping and optional poller status. No deploy controls here."
          action={
            payload ? (
              <LiveIndicator
                tone={pollerUnreachable || !ok ? (pollerUnreachable ? "down" : "stale") : "ok"}
                label={
                  pollerUnreachable
                    ? "Unreachable"
                    : ok
                      ? "Live"
                      : "Degraded"
                }
              />
            ) : (
              <LiveIndicator tone="down" label="Unreachable" />
            )
          }
        />

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
              <div className="mt-6">
                <AlertBanner
                  tone="danger"
                  icon={Radio}
                  title="Poller health unreachable"
                  description="HEALTH_URL is configured, but the dashboard could not reach the poller health endpoint. DB liveness is separate; check HEALTH_URL, routing, and the poller process before trusting alert freshness."
                />
              </div>
            ) : pollerDegraded ? (
              <div className="mt-6">
                <AlertBanner
                  tone="warning"
                  icon={Activity}
                  title="Poller reachable but degraded"
                  description="The poller health endpoint responded, but one or more poller checks reported unhealthy. Review tick flags, price/disclosure poll flags, watched-missing symbols, circuits, and recent poller logs."
                />
              </div>
            ) : null}

            <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <StatCard
                label="Database"
                value={payload.db_ok ? "ok" : "down"}
                icon={Database}
              />
              <StatCard
                label="Status"
                value={statusLabel}
                icon={Activity}
              />
              <StatCard
                label="Snapshot age"
                value={formatAge(snapshotAge)}
                icon={Timer}
              />
              <StatCard
                label="Tick age"
                value={formatAge(tickAge)}
                icon={Radio}
              />
            </div>

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

            {ml != null ? (
              <section
                className="mt-10 border-t border-border/60 pt-6"
                aria-labelledby="ml-heading"
              >
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div className="min-w-0">
                    <h2
                      id="ml-heading"
                      className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                    >
                      Model / forecast
                    </h2>
                    <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                      {ml.disclaimer}
                    </p>
                  </div>
                  <Link
                    href="/signals"
                    className="shrink-0 text-sm font-medium text-foreground underline-offset-4 hover:underline"
                  >
                    Open Signal Board →
                  </Link>
                </div>

                {/* Champion banner — full id, no truncation in a 1/4 card */}
                <article className="mt-5 rounded-xl border border-border bg-card p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-muted text-foreground">
                        <Trophy className="size-5" aria-hidden />
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                          Serving champion
                        </p>
                        {ml.champion ? (
                          <>
                            <p
                              className="mt-1 text-xl font-semibold tracking-tight text-foreground"
                              title={ml.champion.model_id}
                            >
                              {championShortId(ml.champion.model_id)}
                            </p>
                            <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                              {ml.champion.model_id}
                            </p>
                          </>
                        ) : (
                          <p className="mt-1 text-xl font-semibold text-muted-foreground">
                            None registered
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span
                        className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${hitToneClass(
                          toneForHit(ml.champion?.oos_gated_hit),
                        )}`}
                      >
                        Gated OOS {pctLabel(ml.champion?.oos_gated_hit)}
                      </span>
                      <span className="inline-flex items-center rounded-full border border-border/70 bg-muted/40 px-2.5 py-1 text-xs font-medium text-muted-foreground">
                        Always-on {pctLabel(ml.champion?.oos_hit)}
                      </span>
                      <span className="inline-flex items-center rounded-full border border-border/70 bg-muted/40 px-2.5 py-1 text-xs font-medium text-muted-foreground">
                        Coverage {pctLabel(ml.champion?.oos_coverage)}
                      </span>
                    </div>
                  </div>
                </article>

                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <StatCard
                    label="Gated hit (20d)"
                    value={pctLabel(ml.scoreboard.gated_hit_20d)}
                    hint={`${ml.scoreboard.n_scored_60d.toLocaleString()} scored rows (60d)`}
                    icon={Crosshair}
                    className={
                      toneForHit(ml.scoreboard.gated_hit_20d) === "ok"
                        ? "border-emerald-500/25"
                        : undefined
                    }
                  />
                  <StatCard
                    label="Board hit 20d / 60d"
                    value={`${pctLabel(ml.scoreboard.hit_20d)} / ${pctLabel(ml.scoreboard.hit_60d)}`}
                    hint="All scored outcomes (not selective-only)"
                    icon={LineChart}
                  />
                  <StatCard
                    label="Spoke symbols"
                    value={String(ml.accrual.spoke_symbols_latest)}
                    hint={
                      ml.accrual.forecast_points_latest_as_of
                        ? `Selective emits · as of ${ml.accrual.forecast_points_latest_as_of}`
                        : "No forecast_points yet"
                    }
                    icon={Sparkles}
                  />
                </div>

                {/* Accrual status — visual cues for unlock progress */}
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <article className="rounded-xl border border-border bg-card p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                          Market summary history
                        </p>
                        <p className="mt-1 font-mono text-2xl font-semibold tabular-nums">
                          {ml.accrual.market_summary_days}
                          <span className="text-base font-normal text-muted-foreground">
                            {" "}
                            / 60 days
                          </span>
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {ml.accrual.market_summary_days >= 60
                            ? "Ready to retest foreign-flow features (B-002)."
                            : "Accruing nightly from CSE (~2 sessions/call)."}
                        </p>
                      </div>
                      <span
                        className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-xs font-medium ${
                          ml.accrual.market_summary_days >= 60
                            ? hitToneClass("ok")
                            : ml.accrual.market_summary_days > 0
                              ? hitToneClass("warn")
                              : hitToneClass("muted")
                        }`}
                      >
                        {ml.accrual.market_summary_days >= 60
                          ? "Ready"
                          : "Accruing"}
                      </span>
                    </div>
                    <div
                      className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={60}
                      aria-valuenow={Math.min(60, ml.accrual.market_summary_days)}
                      aria-label="Market summary days toward 60"
                    >
                      <div
                        className="h-full rounded-full bg-foreground/70"
                        style={{
                          width: `${Math.min(100, (ml.accrual.market_summary_days / 60) * 100)}%`,
                        }}
                      />
                    </div>
                  </article>

                  <article className="rounded-xl border border-border bg-card p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                          Order-book snapshots
                        </p>
                        <p className="mt-1 font-mono text-2xl font-semibold tabular-nums">
                          {ml.accrual.order_book_snapshots}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {ml.accrual.latest_order_book_at
                            ? `Latest ${formatTs(ml.accrual.latest_order_book_at)}`
                            : "Empty outside market hours — nightly top-25 poll."}
                        </p>
                      </div>
                      <span
                        className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-xs font-medium ${
                          ml.accrual.order_book_snapshots > 0
                            ? hitToneClass("ok")
                            : hitToneClass("muted")
                        }`}
                      >
                        {ml.accrual.order_book_snapshots > 0 ? "Live" : "Idle"}
                      </span>
                    </div>
                  </article>
                </div>
              </section>
            ) : null}

            {delivery != null ? (
              <section
                className="mt-10 border-t border-border/60 pt-6"
                aria-labelledby="delivery-heading"
              >
                <h2
                  id="delivery-heading"
                  className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                >
                  Telegram delivery
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Cherry reliability slice — fire attempts from alert_log (not
                  a send console).
                </p>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <StatCard
                    label="Delivered (24h)"
                    value={String(delivery.delivered_24h)}
                    hint="message_sent or attempted_ok"
                  />
                  <StatCard
                    label="Retrying"
                    value={String(delivery.retrying)}
                    hint="Pending retries"
                  />
                  <StatCard
                    label="Dead-lettered"
                    value={String(delivery.dead_lettered)}
                    hint="Stopped after max attempts"
                  />
                </div>
              </section>
            ) : null}

            {retention != null ? (
              <section
                className="mt-10 border-t border-border/60 pt-6"
                aria-labelledby="retention-heading"
              >
                <h2
                  id="retention-heading"
                  className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                >
                  Snapshot retention
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Poller setting{" "}
                  <code className="font-mono text-xs">SNAPSHOT_RETENTION_DAYS</code>
                  {retention.snapshot_retention_days === 0
                    ? " — 0 means keep all price snapshots (no prune)."
                    : ` — prune snapshots older than ${retention.snapshot_retention_days} day(s).`}
                </p>
              </section>
            ) : null}

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
  // Fail closed — non-strings / out-of-range must not skew stale ops banners
  // (parity formatTs / isStaleTs; formatAge day-cap alone still computed huge ageMs).
  if (typeof iso !== "string" || !iso) return null;
  const ts = Date.parse(iso);
  if (Number.isNaN(ts) || Math.abs(ts) > MAX_DATE_MS) return null;
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

  // Fail closed — extreme past ISO used to render multi-million-day labels.
  if (days > MAX_HEALTH_AGE_DAYS) return `>${MAX_HEALTH_AGE_DAYS}d`;
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

/** Cap ops-notice copy — misbuilt callers used to balloon the health panel. */
const MAX_OPS_NOTICE_TITLE = 120;
const MAX_OPS_NOTICE_COPY = 600;

function sanitizeOpsNoticeText(
  raw: unknown,
  maxLen: number,
  fallback: string,
): string {
  // Fail closed — non-strings / controls / overlong must not balloon UI.
  const cleaned = sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    maxLen,
  );
  return cleaned ?? fallback;
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
  const safeTitle = sanitizeOpsNoticeText(
    title,
    MAX_OPS_NOTICE_TITLE,
    "Stale",
  );
  const safeCopy = sanitizeOpsNoticeText(copy, MAX_OPS_NOTICE_COPY, "");
  return (
    <Alert className="mt-5" variant="default">
      <AlertTitle>{safeTitle}</AlertTitle>
      {safeCopy ? <AlertDescription>{safeCopy}</AlertDescription> : null}
    </Alert>
  );
}
