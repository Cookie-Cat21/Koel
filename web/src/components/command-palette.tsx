"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  MAX_STOCK_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { normalizeSymbol } from "@/lib/api/symbol";
import { formatNumber } from "@/lib/format";

type CommandSymbol = {
  symbol: string;
  name: string | null;
  price: number | null;
};

const MAX_RESULTS = 8;
const DEBOUNCE_MS = 180;

function parseSymbols(body: unknown): CommandSymbol[] {
  if (!body || typeof body !== "object" || Array.isArray(body)) return [];
  const raw = (body as { items?: unknown }).items;
  if (!Array.isArray(raw)) return [];
  const out: CommandSymbol[] = [];
  for (const row of raw) {
    if (out.length >= MAX_RESULTS) break;
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const symbol = normalizeSymbol(r.symbol);
    if (!symbol) continue;
    out.push({
      symbol,
      name: sanitizeDisclosureText(
        typeof r.name === "string" ? r.name : null,
        MAX_STOCK_NAME_LENGTH,
      ),
      price: toFiniteNumber(r.price),
    });
  }
  return out;
}

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CommandSymbol[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpenChange(true);
      } else if (event.key === "Escape" && open) {
        event.preventDefault();
        onOpenChange(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onOpenChange, open]);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const qs = new URLSearchParams({
          q: query.trim(),
          limit: String(MAX_RESULTS),
        });
        const res = await fetch(`/api/v1/symbols?${qs.toString()}`, {
          credentials: "same-origin",
          signal: ctrl.signal,
        });
        if (!res.ok) {
          setResults([]);
          setError(`Search unavailable (${res.status}).`);
          return;
        }
        setResults(parseSymbols(await res.json()));
        setActiveIndex(0);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setResults([]);
        setError("Search unavailable.");
      } finally {
        if (!ctrl.signal.aborted) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
  }, [open, query]);

  const active = useMemo(
    () => results[Math.min(activeIndex, Math.max(0, results.length - 1))],
    [activeIndex, results],
  );

  function openSymbol(symbol: string) {
    const normalized = normalizeSymbol(symbol);
    if (!normalized) return;
    onOpenChange(false);
    setQuery("");
    router.push(`/symbols/${encodeURIComponent(normalized)}`);
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-background/80 px-4 py-16 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onOpenChange(false);
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="command-palette-title"
        className="mx-auto w-full max-w-lg rounded-xl border border-border bg-background p-3 shadow-xl"
      >
        <div className="flex items-center justify-between gap-3 px-1 pb-3">
          <h2 id="command-palette-title" className="text-sm font-medium">
            Search symbols
          </h2>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            Esc
          </Button>
        </div>
        <Input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActiveIndex((idx) =>
                results.length === 0 ? 0 : (idx + 1) % results.length,
              );
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActiveIndex((idx) =>
                results.length === 0
                  ? 0
                  : (idx - 1 + results.length) % results.length,
              );
            } else if (event.key === "Enter" && active) {
              event.preventDefault();
              openSymbol(active.symbol);
            } else if (event.key === "Escape") {
              event.preventDefault();
              onOpenChange(false);
            }
          }}
          placeholder="Search symbol or company"
          autoComplete="off"
          spellCheck={false}
          aria-controls="command-palette-results"
          aria-activedescendant={
            active ? `command-palette-result-${active.symbol}` : undefined
          }
        />
        <div className="mt-3" aria-live="polite">
          {error ? (
            <p className="px-2 py-3 text-sm text-muted-foreground">{error}</p>
          ) : loading && results.length === 0 ? (
            <p className="px-2 py-3 text-sm text-muted-foreground">Searching...</p>
          ) : results.length === 0 ? (
            <p className="px-2 py-3 text-sm text-muted-foreground">
              No symbols found.
            </p>
          ) : (
            <ul id="command-palette-results" role="listbox" className="flex flex-col gap-1">
              {results.map((item, idx) => {
                const selected = idx === activeIndex;
                return (
                  <li key={item.symbol} role="option" aria-selected={selected}>
                    <button
                      id={`command-palette-result-${item.symbol}`}
                      type="button"
                      className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none ${
                        selected ? "bg-muted" : "hover:bg-muted/70"
                      }`}
                      onMouseEnter={() => setActiveIndex(idx)}
                      onClick={() => openSymbol(item.symbol)}
                    >
                      <span className="min-w-0">
                        <span className="block font-mono font-medium">
                          {item.symbol}
                        </span>
                        {item.name ? (
                          <span className="block truncate text-xs text-muted-foreground">
                            {item.name}
                          </span>
                        ) : null}
                      </span>
                      <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                        {formatNumber(item.price)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
