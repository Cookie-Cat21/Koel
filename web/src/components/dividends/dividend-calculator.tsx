"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useId, useState, useTransition } from "react";
import { Banknote, CalendarDays, Percent, Plus, Search, Trash2 } from "lucide-react";

import { InlineError } from "@/components/inline-error";
import {
  EventTimeline,
  type EventTimelineItem,
} from "@/components/kit/event-timeline";
import { StatCard } from "@/components/kit/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  fetchDividendSymbol,
  type DividendSymbolPayload,
} from "@/lib/api/dividends";
import { normalizeSymbol } from "@/lib/api/symbol";
import {
  estimateDividend,
  formatDividendDate,
  MAX_DIVIDEND_DPS,
  MAX_DIVIDEND_SHARES,
  shortDividendTitle,
} from "@/lib/dividends";
import { formatNumber, formatPct, formatTs } from "@/lib/format";
import { cn } from "@/lib/utils";

const DEFAULT_SHARES = "1000";
const WHT_RATE = 0.14;

function parsePositiveInput(
  raw: string,
  max: number,
): number | null {
  const t = raw.trim().replace(/,/g, "");
  if (!t) return null;
  if (!/^\d+(\.\d+)?$/.test(t)) return null;
  const n = Number(t);
  if (!Number.isFinite(n) || n <= 0 || n > max) return null;
  return n;
}

type CalculatorRow = {
  id: string;
  payload: DividendSymbolPayload;
  shares: string;
  dps: string;
};

function rowDps(payload: DividendSymbolPayload, override: string): string {
  const manual = override.trim();
  if (manual) return manual;
  return payload.suggested_dps != null ? String(payload.suggested_dps) : "";
}

function upsertRow(rows: CalculatorRow[], row: CalculatorRow): CalculatorRow[] {
  const existing = rows.findIndex((item) => item.payload.symbol === row.payload.symbol);
  if (existing === -1) return [row, ...rows];
  const next = [...rows];
  next[existing] = row;
  return next;
}

/**
 * HyperUI-style KPI strip + Watermelon FAQ sibling page inputs.
 * Session-only shares — never persisted as portfolio holdings.
 */
export function DividendCalculator({
  initialSymbol = "",
  className,
}: {
  initialSymbol?: string;
  className?: string;
}) {
  const reduceMotion = useReducedMotion();
  const formId = useId();
  const [symbol, setSymbol] = useState(initialSymbol);
  const [shares, setShares] = useState(DEFAULT_SHARES);
  const [dps, setDps] = useState("");
  const [rows, setRows] = useState<CalculatorRow[]>([]);
  const [applyWht, setApplyWht] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    const seed = normalizeSymbol(initialSymbol);
    if (!seed) return;
    let cancelled = false;
    startTransition(async () => {
      setError(null);
      const res = await fetchDividendSymbol(seed);
      if (cancelled) return;
      if (!res.ok) {
        setError(res.message);
        return;
      }
      setRows((prev) =>
        upsertRow(prev, {
          id: res.data.symbol,
          payload: res.data,
          shares: DEFAULT_SHARES,
          dps: rowDps(res.data, ""),
        }),
      );
    });
    return () => {
      cancelled = true;
    };
  }, [initialSymbol]);

  function onLookup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const normalized = normalizeSymbol(symbol);
    if (!normalized) {
      setError("Enter a CSE symbol (e.g. JKH.N0000).");
      return;
    }
    startTransition(async () => {
      const res = await fetchDividendSymbol(normalized);
      if (!res.ok) {
        setError(res.message);
        return;
      }
      setSymbol(res.data.symbol);
      setRows((prev) =>
        upsertRow(prev, {
          id: res.data.symbol,
          payload: res.data,
          shares,
          dps: rowDps(res.data, dps),
        }),
      );
      setSymbol("");
      setDps("");
    });
  }

  const rowEstimates = rows.map((row) => {
    const sharesN = parsePositiveInput(row.shares, MAX_DIVIDEND_SHARES);
    const dpsN = parsePositiveInput(row.dps, MAX_DIVIDEND_DPS);
    return {
      row,
      sharesN,
      dpsN,
      estimate: estimateDividend(sharesN, dpsN, row.payload.last_price ?? null),
    };
  });
  const grossCash = rowEstimates.reduce(
    (sum, item) => sum + (item.estimate.cash ?? 0),
    0,
  );
  const hasCash = rowEstimates.some((item) => item.estimate.cash != null);
  const whtAmount = hasCash && applyWht ? grossCash * WHT_RATE : null;
  const netCash = hasCash ? grossCash - (whtAmount ?? 0) : null;
  const totalEvents = rows.reduce(
    (sum, row) => sum + row.payload.events.length,
    0,
  );

  const timeline: EventTimelineItem[] = rows.flatMap((row) => {
    if (row.payload.events.length > 0) {
      return row.payload.events.slice(0, 8).map((event) => {
        const linkedDisclosure = row.payload.items.find(
          (item) => item.id === event.disclosure_id,
        );
        const bits: string[] = [];
        if (event.dps != null) bits.push(`DPS ${formatNumber(event.dps)} LKR`);
        if (event.d_pay) bits.push(`Pay ${formatDividendDate(event.d_pay)}`);
        if (event.dates_tbd) bits.push("Dates TBD");
        return {
          id: `${row.payload.symbol}-event-${event.id}`,
          at: event.d_xd
            ? `XD ${formatDividendDate(event.d_xd)}`
            : event.d_ann
              ? formatDividendDate(event.d_ann)
              : null,
          title: `${row.payload.symbol} · ${shortDividendTitle(event.title)}`,
          href: linkedDisclosure?.pdf_url || linkedDisclosure?.url || null,
          external: Boolean(linkedDisclosure?.pdf_url || linkedDisclosure?.url),
          badge: event.kind,
          meta: bits.length > 0 ? bits.join(" · ") : null,
          emphasis: event.dates_tbd ? "empty" : "default",
        };
      });
    }
    return row.payload.items.slice(0, 8).map((item) => {
      const bits: string[] = [];
      if (item.parsed.dps != null) {
        bits.push(`DPS ${formatNumber(item.parsed.dps)} LKR`);
      }
      if (item.parsed.xd) bits.push(`XD ${item.parsed.xd}`);
      if (item.parsed.payment) bits.push(`Pay ${item.parsed.payment}`);
      if (item.parsed.dates_tbd) bits.push("Dates TBD");
      return {
        id: `${row.payload.symbol}-disclosure-${item.id}`,
        at: item.published_at ? formatTs(item.published_at) : null,
        title: `${row.payload.symbol} · ${shortDividendTitle(item.title)}`,
        href: item.pdf_url || item.url,
        external: true,
        badge: item.category,
        meta: bits.length > 0 ? bits.join(" · ") : null,
        emphasis: item.parsed.dates_tbd ? "empty" : "default",
      };
    });
  });

  function updateRow(symbolKey: string, patch: Partial<Pick<CalculatorRow, "shares" | "dps">>) {
    setRows((prev) =>
      prev.map((row) =>
        row.payload.symbol === symbolKey ? { ...row, ...patch } : row,
      ),
    );
  }

  function removeRow(symbolKey: string) {
    setRows((prev) => prev.filter((row) => row.payload.symbol !== symbolKey));
  }

  return (
    <div className={cn("flex flex-col gap-8", className)}>
      <form
        onSubmit={onLookup}
        className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(8rem,0.6fr)_minmax(8rem,0.6fr)_auto] lg:items-end"
        noValidate
        aria-labelledby={`${formId}-lookup`}
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <Label htmlFor={`${formId}-symbol`} id={`${formId}-lookup`}>
            Symbol
          </Label>
          <Input
            id={`${formId}-symbol`}
            name="symbol"
            className="h-10 font-mono"
            placeholder="e.g. JKH.N0000"
            value={symbol}
            onChange={(e) => {
              setSymbol(e.target.value);
              if (error) setError(null);
            }}
            autoComplete="off"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${formId}-error` : undefined}
            required
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor={`${formId}-shares`}>Shares</Label>
          <Input
            id={`${formId}-shares`}
            inputMode="decimal"
            className="h-10 font-mono tabular-nums"
            placeholder={DEFAULT_SHARES}
            value={shares}
            onChange={(e) => setShares(e.target.value)}
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor={`${formId}-dps`}>DPS (optional)</Label>
          <Input
            id={`${formId}-dps`}
            inputMode="decimal"
            className="h-10 font-mono tabular-nums"
            placeholder="Use latest event"
            value={dps}
            onChange={(e) => setDps(e.target.value)}
          />
        </div>
        <Button
          type="submit"
          className="h-10 shrink-0"
          disabled={pending}
          aria-busy={pending}
        >
          {rows.length > 0 ? (
            <Plus className="size-4" aria-hidden />
          ) : (
            <Search className="size-4" aria-hidden />
          )}
          {pending ? "Loading…" : rows.length > 0 ? "Add row" : "Add symbol"}
        </Button>
      </form>

      {error ? (
        <InlineError id={`${formId}-error`} message={error} />
      ) : null}

      {rows.length > 0 ? (
        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: "easeOut" }}
          className="flex flex-col gap-6"
        >
          <div className="rounded-xl border border-border/70">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 px-4 py-3">
              <div>
                <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                  Session rows
                </h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Shares stay in this browser session; this is not a portfolio.
                </p>
              </div>
              <label className="flex max-w-sm items-start gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 rounded border-border"
                  checked={applyWht}
                  onChange={(e) => setApplyWht(e.target.checked)}
                />
                <span>
                  Estimate 14% WHT{" "}
                  <span className="block">estimate only — not a tax report</span>
                </span>
              </label>
            </div>
            <ul className="divide-y divide-border/60">
              {rowEstimates.map(({ row, sharesN, dpsN, estimate }) => (
                <li
                  key={row.id}
                  className="grid gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(7rem,0.45fr)_minmax(7rem,0.45fr)_minmax(8rem,0.6fr)_auto] lg:items-center"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/symbols/${encodeURIComponent(row.payload.symbol)}`}
                        className="font-mono text-sm font-semibold tracking-tight text-foreground underline-offset-2 hover:underline"
                      >
                        {row.payload.symbol}
                      </Link>
                      {row.payload.last_price != null ? (
                        <Badge variant="outline" className="font-mono tabular-nums">
                          Last {formatNumber(row.payload.last_price)} LKR
                        </Badge>
                      ) : (
                        <Badge variant="outline">No snapshot yet</Badge>
                      )}
                    </div>
                    {row.payload.name ? (
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {row.payload.name}
                      </p>
                    ) : null}
                    {row.payload.last_ts ? (
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        Last tick {formatTs(row.payload.last_ts)}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor={`${formId}-${row.id}-shares`}>Shares</Label>
                    <Input
                      id={`${formId}-${row.id}-shares`}
                      inputMode="decimal"
                      className="h-9 font-mono tabular-nums"
                      value={row.shares}
                      onChange={(e) =>
                        updateRow(row.payload.symbol, { shares: e.target.value })
                      }
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor={`${formId}-${row.id}-dps`}>DPS</Label>
                    <Input
                      id={`${formId}-${row.id}-dps`}
                      inputMode="decimal"
                      className="h-9 font-mono tabular-nums"
                      value={row.dps}
                      placeholder={
                        row.payload.suggested_dps != null
                          ? String(row.payload.suggested_dps)
                          : "1.50"
                      }
                      onChange={(e) =>
                        updateRow(row.payload.symbol, { dps: e.target.value })
                      }
                    />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">Cash / yield</p>
                    <p className="font-mono text-sm font-semibold tabular-nums">
                      {estimate.cash != null
                        ? `${formatNumber(estimate.cash)} LKR`
                        : "—"}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {sharesN != null && dpsN != null
                        ? `${formatNumber(sharesN, 0)} × ${formatNumber(dpsN)}`
                        : "Enter shares and DPS"}
                      {" · "}
                      yield{" "}
                      {estimate.yield_pct != null
                        ? formatPct(estimate.yield_pct)
                        : "—"}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="justify-self-start lg:justify-self-end"
                    onClick={() => removeRow(row.payload.symbol)}
                  >
                    <Trash2 className="size-4" aria-hidden />
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          </div>

          <motion.div
            key={`${grossCash}-${applyWht ? "wht" : "gross"}`}
            initial={reduceMotion ? false : { opacity: 0.55 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="grid grid-cols-1 gap-3 sm:grid-cols-3"
          >
            <StatCard
              label="Combined cash"
              value={
                netCash != null
                  ? `${formatNumber(netCash)} LKR`
                  : "—"
              }
              hint={
                applyWht && whtAmount != null
                  ? `After estimated WHT of ${formatNumber(whtAmount)} LKR`
                  : hasCash
                    ? "WHT estimate is off"
                    : "Enter shares and DPS"
              }
              icon={Banknote}
            />
            <StatCard
              label="Gross cash"
              value={
                hasCash
                  ? `${formatNumber(grossCash)} LKR`
                  : "—"
              }
              hint={
                applyWht
                  ? "Before the optional WHT estimate"
                  : "No tax estimate applied"
              }
              icon={Percent}
            />
            <StatCard
              label="Event rows"
              value={String(totalEvents)}
              hint={`${rows.length} symbol${rows.length === 1 ? "" : "s"} in session`}
              icon={CalendarDays}
            />
          </motion.div>

          <section aria-labelledby={`${formId}-timeline`}>
            <h2
              id={`${formId}-timeline`}
              className="font-display text-lg font-semibold tracking-tight"
            >
              Dividend timeline
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              From dividend_events first, then stored CSE disclosures when an
              event row is not available — the market stays open on XD day.
            </p>
            <div className="mt-4">
              <EventTimeline
                items={timeline}
                empty={
                  <p className="text-sm text-muted-foreground">
                    No dividend events stored for these symbols yet. Run the
                    poller, or set a disclosure alert for category Dividend on{" "}
                    <Link
                      href="/alerts"
                      className="underline-offset-2 hover:underline"
                    >
                      Alerts
                    </Link>
                    .
                  </p>
                }
              />
            </div>
          </section>
        </motion.div>
      ) : null}
    </div>
  );
}
