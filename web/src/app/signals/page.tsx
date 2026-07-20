import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { serverApiGet } from "@/lib/api/server-fetch";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toFiniteNumber } from "@/lib/api/finite-number";
import {
  MAX_SIGNAL_REASON_LENGTH,
  MAX_SIGNAL_REASONS,
} from "@/lib/api/signals";
import {
  MAX_STOCK_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatNumber } from "@/lib/format";
import {
  gateShortLabel,
  isSelectiveGate,
  normalizeForecastGate,
} from "@/lib/forecast-gate";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Signal Board · koel",
  description:
    "Research scores from CSE path data — ranked factors with reasons. Not advice.",
};

const MAX_PAGE_ITEMS = 100;

type SignalItem = {
  symbol: string;
  name: string | null;
  score: number | null;
  as_of: string | null;
  model_version: string;
  reasons: string[];
  bar_count: number | null;
  spoke: boolean;
  forecast_gate: string | null;
  forecast_gate_label: string | null;
  forecast_confidence: number | null;
  forecast_confidence_band: string | null;
  rank: number;
  prior_rank: number | null;
  rank_delta: number | null;
};

type SignalBoardBody = {
  items: SignalItem[];
  as_of: string | null;
  prior_as_of: string | null;
};

function asDateIso(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const m = raw.match(/^(\d{4}-\d{2}-\d{2})/);
  return m ? m[1]! : null;
}

function asSignalBoard(body: unknown): SignalBoardBody | null {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const root = body as Record<string, unknown>;
  const itemsRaw = root.items;
  if (!Array.isArray(itemsRaw)) return null;
  const out: SignalItem[] = [];
  for (const row of itemsRaw) {
    if (out.length >= MAX_PAGE_ITEMS) break;
    if (row == null || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const symbol = normalizeSymbol(r.symbol);
    if (!symbol) continue;
    const reasonsRaw = Array.isArray(r.reasons) ? r.reasons : [];
    const reasons: string[] = [];
    for (const reason of reasonsRaw) {
      if (reasons.length >= MAX_SIGNAL_REASONS) break;
      if (typeof reason !== "string") continue;
      const cleaned = sanitizeDisclosureText(reason, MAX_SIGNAL_REASON_LENGTH);
      if (cleaned) reasons.push(cleaned);
    }
    const name =
      typeof r.name === "string"
        ? sanitizeDisclosureText(r.name, MAX_STOCK_NAME_LENGTH) || null
        : null;
    const forecastGate = normalizeForecastGate(r.forecast_gate);
    const forecastConfidence = toFiniteNumber(r.forecast_confidence);
    const forecastBand =
      typeof r.forecast_confidence_band === "string"
        ? r.forecast_confidence_band.trim().slice(0, 16) || null
        : null;
    const spoke =
      typeof r.spoke === "boolean" ? r.spoke : isSelectiveGate(forecastGate);
    const rankRaw = toFiniteNumber(r.rank);
    const priorRankRaw = toFiniteNumber(r.prior_rank);
    const rankDeltaRaw = toFiniteNumber(r.rank_delta);
    out.push({
      symbol,
      name,
      score: toFiniteNumber(r.score),
      as_of: asDateIso(r.as_of),
      model_version:
        typeof r.model_version === "string" && r.model_version.trim()
          ? r.model_version.trim().slice(0, 64)
          : "unknown",
      reasons,
      bar_count: (() => {
        const n = toFiniteNumber(r.bar_count);
        return n == null ? null : Math.trunc(n);
      })(),
      spoke,
      forecast_gate: forecastGate,
      forecast_gate_label:
        typeof r.forecast_gate_label === "string" && r.forecast_gate_label.trim()
          ? r.forecast_gate_label.trim().slice(0, 32)
          : gateShortLabel(forecastGate),
      forecast_confidence: forecastConfidence,
      forecast_confidence_band: forecastBand,
      rank: rankRaw == null || rankRaw < 1 ? out.length + 1 : Math.trunc(rankRaw),
      prior_rank:
        priorRankRaw == null || priorRankRaw < 1
          ? null
          : Math.trunc(priorRankRaw),
      rank_delta: rankDeltaRaw == null ? null : Math.trunc(rankDeltaRaw),
    });
  }
  return {
    items: out,
    as_of: asDateIso(root.as_of),
    prior_as_of: asDateIso(root.prior_as_of),
  };
}

function RankDeltaBadge({
  priorRank,
  rankDelta,
  hasPriorBoard,
}: {
  priorRank: number | null;
  rankDelta: number | null;
  hasPriorBoard: boolean;
}) {
  if (!hasPriorBoard) return null;
  if (priorRank == null || rankDelta == null) {
    return (
      <span className="text-xs tabular-nums text-muted-foreground">new</span>
    );
  }
  if (rankDelta === 0) {
    return (
      <span className="text-xs tabular-nums text-muted-foreground">—</span>
    );
  }
  if (rankDelta > 0) {
    return (
      <span className="text-xs font-medium tabular-nums text-emerald-700 dark:text-emerald-300">
        ↑{rankDelta}
      </span>
    );
  }
  return (
    <span className="text-xs font-medium tabular-nums text-rose-700 dark:text-rose-300">
      ↓{Math.abs(rankDelta)}
    </span>
  );
}

export default async function SignalsPage() {
  await requirePageSession();
  const res = await serverApiGet("/api/v1/signals?limit=50");
  let board: SignalBoardBody | null = null;
  if (res?.ok) {
    try {
      board = asSignalBoard(await res.json());
    } catch {
      board = null;
    }
  }

  const items = board?.items ?? null;
  const spokeCount = items?.filter((i) => i.spoke).length ?? 0;
  const hasDelta = board?.prior_as_of != null;

  return (
    <div className="min-h-screen bg-background">
      <AppNav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <PageHeader
          title="Signal Board"
          description="Research scores from CSE daily path factors (momentum, volatility, liquidity). Higher score is not a buy — informational only. Spoke means a selective forecast exists; Silent means the model stayed quiet."
        />
        <NfaInline className="mt-3" />
        {board != null && board.as_of ? (
          <p className="mt-3 text-sm text-muted-foreground">
            Board as of{" "}
            <span className="font-medium text-foreground">{board.as_of}</span>
            {hasDelta ? (
              <>
                {" · "}
                rank Δ vs{" "}
                <span className="font-medium text-foreground">
                  {board.prior_as_of}
                </span>
              </>
            ) : (
              <> · rank Δ needs a prior daily score run</>
            )}
          </p>
        ) : null}
        {items != null && items.length > 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Forecast coverage on this page:{" "}
            <span className="font-medium text-foreground">
              {spokeCount} Spoke
            </span>
            {" · "}
            <span className="font-medium text-foreground">
              {items.length - spokeCount} Silent
            </span>
            . Selective emits are historical OOS-calibrated — not guarantees.
          </p>
        ) : null}

        {items == null ? (
          <EmptyState
            title="Signal Board unavailable"
            description="Could not load research scores. Check session and database."
          />
        ) : items.length === 0 ? (
          <EmptyState
            title="No scores yet"
            description="Run path backfill then: python3 -m koel score-signals --limit 0"
          />
        ) : (
          <ol className="mt-8 divide-y divide-border rounded-lg border border-border">
            {items.map((row) => (
              <li
                key={row.symbol}
                className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="inline-flex items-baseline gap-1.5 text-xs text-muted-foreground tabular-nums">
                      <span>#{row.rank}</span>
                      <RankDeltaBadge
                        priorRank={row.prior_rank}
                        rankDelta={row.rank_delta}
                        hasPriorBoard={hasDelta}
                      />
                    </span>
                    <Link
                      href={`/symbols/${encodeURIComponent(row.symbol)}`}
                      className="font-medium text-foreground underline-offset-4 hover:underline"
                    >
                      {row.symbol}
                    </Link>
                    {row.name ? (
                      <span className="truncate text-sm text-muted-foreground">
                        {row.name}
                      </span>
                    ) : null}
                    <span
                      className={
                        row.spoke
                          ? "rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium tracking-wide text-emerald-800 uppercase dark:text-emerald-200"
                          : "rounded-full border border-border/70 px-2 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase"
                      }
                    >
                      {row.spoke ? "Spoke" : "Silent"}
                    </span>
                    {row.forecast_gate_label ? (
                      <span className="rounded-full border border-border/70 px-2 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
                        {row.forecast_gate_label}
                        {row.forecast_confidence != null
                          ? ` · ${Math.round(row.forecast_confidence * 100)}%`
                          : ""}
                      </span>
                    ) : null}
                  </div>
                  {row.reasons.length > 0 ? (
                    <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
                      {row.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  ) : null}
                  <p className="mt-1 text-xs text-muted-foreground">
                    {row.model_version}
                    {row.as_of ? ` · as of ${row.as_of}` : ""}
                    {row.bar_count != null ? ` · ${row.bar_count} bars` : ""}
                    {row.prior_rank != null
                      ? ` · was #${row.prior_rank}`
                      : hasDelta
                        ? " · new to board"
                        : ""}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Score
                  </p>
                  <p className="font-mono text-lg tabular-nums">
                    {row.score == null ? "—" : formatNumber(row.score)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}

        <NfaFooter />
      </main>
    </div>
  );
}
