"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";

import { CompanyGraphCanvas } from "@/components/company-graph/graph-canvas";
import { EmptyState } from "@/components/empty-state";
import { KpiStrip } from "@/components/kit/kpi-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { GraphEdge, GraphNode } from "@/lib/api/graph";
import { formatCompactNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

function scaleEquity(node: GraphNode): number | null {
  if (node.equity == null) return null;
  const mult =
    node.equity_scale === "millions"
      ? 1e6
      : node.equity_scale === "thousands"
        ? 1e3
        : 1;
  const scaled = node.equity * mult;
  // Guard %-like / stub extracts that slipped through
  if (scaled < 10_000) return null;
  return scaled;
}

const RELATION_LABEL: Record<string, string> = {
  subsidiary: "Subsidiary",
  associate: "Associate",
  joint_venture: "Joint venture",
  related_party: "Related party",
};

function shortSymbol(symbol: string | null): string {
  if (!symbol) return "";
  return symbol.replace(/\.(N|X)0000$/i, "");
}

export function CompanyGraphClient({
  nodes,
  edges,
  initialFocus,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  initialFocus?: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  // Only pre-select when URL has ?symbol= — otherwise show full map, nothing focused.
  const initialSelected =
    nodes.find((n) => n.symbol === initialFocus)?.id ?? null;

  const [selectedId, setSelectedId] = useState<number | null>(initialSelected);
  const [query, setQuery] = useState(
    initialFocus ? shortSymbol(initialFocus) : "",
  );
  // Suggestions stay open while typing; close after pick / Escape / blur.
  const [suggestOpen, setSuggestOpen] = useState(false);
  // CSE has no ownership JSON API — edges are PDF-extracted. Low/group_mention
  // noise is dropped; we always show medium+ (no user confidence picker).
  const [holdingsOnly, setHoldingsOnly] = useState(
    searchParams.get("hubs") === "1",
  );
  const [showHints, setShowHints] = useState(true);

  // "/" focuses the symbol search (power-user shortcut)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) {
        return;
      }
      e.preventDefault();
      document.getElementById("graph-symbol-search")?.focus();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Persist filters in URL (strip legacy ?confidence=)
  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("confidence");
    if (holdingsOnly) params.set("hubs", "1");
    else params.delete("hubs");
    const sel = nodes.find((n) => n.id === selectedId);
    if (sel?.symbol) params.set("symbol", sel.symbol);
    else params.delete("symbol");
    const next = params.toString();
    const cur = searchParams.toString();
    if (next !== cur) {
      startTransition(() => {
        router.replace(next ? `${pathname}?${next}` : pathname, {
          scroll: false,
        });
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync filters only
  }, [holdingsOnly, selectedId]);

  const filteredEdges = useMemo(() => {
    const rank = { low: 1, medium: 2, high: 3 } as const;
    return edges.filter((e) => rank[e.confidence] >= rank.medium);
  }, [edges]);

  // Show every loaded listed issuer (incl. isolates with no PDF links yet).
  // Edge-only filtering hid ~170 CSE names even though nodes already exist.
  const visibleNodes = useMemo(() => {
    let list = nodes.slice();
    if (holdingsOnly) {
      const hubIds = new Set(
        filteredEdges
          .filter(
            (e) => e.relation === "subsidiary" || e.relation === "associate",
          )
          .map((e) => e.src_node_id),
      );
      const keep = new Set(
        list
          .filter(
            (n) =>
              hubIds.has(n.id) ||
              (n.name.toLowerCase().includes("holdings") &&
                n.node_kind === "listed"),
          )
          .map((n) => n.id),
      );
      for (const e of filteredEdges) {
        if (keep.has(e.src_node_id)) keep.add(e.dst_node_id);
      }
      list = nodes.filter((n) => keep.has(n.id));
    }
    return list;
  }, [nodes, holdingsOnly, filteredEdges]);

  const linkedListedCount = useMemo(() => {
    const ids = new Set<number>();
    for (const e of filteredEdges) {
      ids.add(e.src_node_id);
      ids.add(e.dst_node_id);
    }
    return nodes.filter(
      (n) => n.node_kind === "listed" && ids.has(n.id),
    ).length;
  }, [filteredEdges, nodes]);

  const visibleEdges = useMemo(() => {
    const ids = new Set(visibleNodes.map((n) => n.id));
    return filteredEdges.filter(
      (e) => ids.has(e.src_node_id) && ids.has(e.dst_node_id),
    );
  }, [filteredEdges, visibleNodes]);

  const selected =
    selectedId != null
      ? (visibleNodes.find((n) => n.id === selectedId) ?? null)
      : null;

  const selectedEdges = useMemo(() => {
    if (selectedId == null) return [];
    const raw = visibleEdges.filter(
      (e) =>
        e.src_node_id === selectedId || e.dst_node_id === selectedId,
    );
    const rank: Record<string, number> = {
      subsidiary: 4,
      associate: 3,
      joint_venture: 3,
      related_party: 2,
      group_mention: 1,
    };
    const best = new Map<string, GraphEdge>();
    for (const e of raw) {
      const a = Math.min(e.src_node_id, e.dst_node_id);
      const b = Math.max(e.src_node_id, e.dst_node_id);
      const key = `${a}:${b}:${e.src_node_id === selectedId ? "out" : "in"}`;
      const prev = best.get(key);
      if (!prev || (rank[e.relation] ?? 0) > (rank[prev.relation] ?? 0)) {
        best.set(key, e);
      }
    }
    return Array.from(best.values());
  }, [visibleEdges, selectedId]);

  const suggestions = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (q.length < 1) return [];
    return visibleNodes
      .filter(
        (n) =>
          (n.symbol && n.symbol.toUpperCase().includes(q)) ||
          n.name.toUpperCase().includes(q) ||
          shortSymbol(n.symbol).includes(q),
      )
      .slice(0, 6);
  }, [query, visibleNodes]);

  function focusNode(node: GraphNode) {
    setSelectedId(node.id);
    setQuery(shortSymbol(node.symbol) || node.name.slice(0, 12));
    setSuggestOpen(false);
    setShowHints(false);
  }

  function focusSearch() {
    const q = query.trim().toUpperCase();
    if (!q) return;
    const hit =
      suggestions[0] ||
      visibleNodes.find(
        (n) =>
          (n.symbol && n.symbol.includes(q)) ||
          n.name.toUpperCase().includes(q) ||
          shortSymbol(n.symbol) === q,
      );
    if (hit) focusNode(hit);
  }

  const listedCount = useMemo(
    () => visibleNodes.filter((n) => n.node_kind === "listed").length,
    [visibleNodes],
  );
  const highConfLinks = useMemo(
    () => visibleEdges.filter((e) => e.confidence === "high").length,
    [visibleEdges],
  );

  if (nodes.length === 0) {
    return (
      <EmptyState
        title="No graph data yet"
        description="Run financials backfill + drain-graph on annual PDFs to populate ownership links and equity."
      />
    );
  }

  return (
    <div className="space-y-4">
      <KpiStrip
        ariaLabel="Ownership map summary"
        items={[
          {
            id: "companies",
            label: "Companies",
            value: String(visibleNodes.length),
            hint: `${listedCount} listed · ${linkedListedCount} with links`,
          },
          {
            id: "links",
            label: "Links",
            value: String(visibleEdges.length),
            hint: `${highConfLinks} high confidence`,
          },
          {
            id: "source",
            label: "Source",
            value: "PDF",
            hint: "Not a CSE ownership API",
          },
        ]}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative flex min-w-0 flex-1 gap-2">
          <div className="relative min-w-0 flex-1 max-w-xs">
            <Input
              id="graph-symbol-search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSuggestOpen(true);
              }}
              onFocus={() => {
                if (query.trim().length > 0) setSuggestOpen(true);
              }}
              onBlur={() => {
                // Defer so suggestion mousedown/click still fires.
                window.setTimeout(() => setSuggestOpen(false), 120);
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  e.preventDefault();
                  setSuggestOpen(false);
                  return;
                }
                if (e.key === "Enter") focusSearch();
              }}
              placeholder="Focus symbol (e.g. JKH)"
              className="w-full"
              aria-label="Focus symbol"
              aria-autocomplete="list"
              aria-expanded={suggestOpen && suggestions.length > 0}
            />
            {suggestOpen && suggestions.length > 0 ? (
              <ul
                className="absolute z-20 mt-1 max-h-48 w-full overflow-auto rounded-md border border-border bg-background py-1 text-sm shadow-sm"
                role="listbox"
              >
                {suggestions.map((n) => (
                  <li
                    key={n.id}
                    role="option"
                    aria-selected={
                      selectedId != null && n.id === selectedId
                    }
                  >
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left hover:bg-muted"
                      onMouseDown={(e) => {
                        // Prevent input blur-before-click from eating the pick.
                        e.preventDefault();
                      }}
                      onClick={() => focusNode(n)}
                    >
                      <span className="font-mono text-foreground">
                        {shortSymbol(n.symbol) || "—"}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {n.name}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <Button type="button" variant="secondary" onClick={focusSearch}>
            Focus
          </Button>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={holdingsOnly}
            onChange={(e) => setHoldingsOnly(e.target.checked)}
            className="size-4 rounded border-border"
          />
          Holdings hubs
        </label>
        <span className="hidden text-[11px] text-muted-foreground sm:inline">
          Annual-report PDFs · research map only
        </span>
      </div>

      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        {Object.entries(RELATION_LABEL).map(([key, label]) => (
          <span key={key} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block size-2 rounded-full"
              style={{
                background:
                  key === "subsidiary"
                    ? "var(--chart-1)"
                    : key === "associate"
                      ? "var(--chart-2)"
                      : key === "joint_venture"
                        ? "var(--chart-3)"
                        : key === "related_party"
                          ? "var(--chart-4)"
                          : "var(--chart-5)",
              }}
            />
            {label}
          </span>
        ))}
        {showHints ? (
          <span className="ml-auto text-[11px] text-muted-foreground/80">
            Full map · click a company to focus · click blank space to clear
          </span>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <CompanyGraphCanvas
          nodes={visibleNodes}
          edges={visibleEdges}
          selectedId={selectedId}
          onSelect={(id) => {
            setSelectedId(id);
            if (id == null) setQuery("");
            setShowHints(id == null);
          }}
        />

        <aside className="rounded-xl border border-border bg-card/40 p-4">
          {selected ? (
            <div className="space-y-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {selected.node_kind === "listed" ? "Listed" : "Unlisted"}
                </p>
                <h2 className="font-display text-lg font-semibold text-foreground">
                  {selected.symbol ?? selected.name}
                </h2>
                <p className="text-sm text-muted-foreground">{selected.name}</p>
                {selected.sector ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {selected.sector}
                  </p>
                ) : null}
              </div>

              <dl className="grid grid-cols-1 gap-2 text-sm">
                <div className="rounded-lg border border-border/70 px-3 py-2">
                  <dt className="text-xs text-muted-foreground">
                    Market cap (LKR)
                  </dt>
                  <dd className="font-mono tabular-nums">
                    {formatCompactNumber(selected.market_cap, 1)}
                  </dd>
                </div>
                <div className="rounded-lg border border-border/70 px-3 py-2">
                  <dt className="text-xs text-muted-foreground">
                    Equity / net assets (LKR)
                  </dt>
                  <dd className="font-mono tabular-nums">
                    {formatCompactNumber(scaleEquity(selected), 1)}
                    {selected.equity_as_of ? (
                      <span className="ml-1 text-xs text-muted-foreground">
                        as of {selected.equity_as_of}
                      </span>
                    ) : null}
                  </dd>
                  <dd className="text-[11px] text-muted-foreground">
                    conf {selected.equity_confidence} · scale{" "}
                    {selected.equity_scale}
                  </dd>
                </div>
              </dl>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  Links ({selectedEdges.length})
                </p>
                {/* No bottom gradient fade — it sat on the last visible row and
                    double-composited badge/ticker text (looked “sliced”). */}
                <ul className="max-h-48 space-y-1 overflow-y-auto overscroll-contain pr-0.5 text-sm">
                  {selectedEdges.slice(0, 24).map((e) => {
                    const outbound = e.src_node_id === selected.id;
                    const other = outbound ? e.dst_name : e.src_name;
                    const otherSym = outbound ? e.dst_symbol : e.src_symbol;
                    return (
                      <li
                        key={`${e.id}-${outbound ? "out" : "in"}`}
                        className="flex min-h-8 flex-nowrap items-center gap-1.5"
                      >
                        <Badge
                          variant="outline"
                          className="shrink-0 px-1.5 py-0 text-[10px]"
                        >
                          {outbound ? "→" : "←"} {RELATION_LABEL[e.relation]}
                        </Badge>
                        <button
                          type="button"
                          className="min-w-0 truncate text-left text-foreground underline-offset-2 hover:underline"
                          onClick={() => {
                            const id = outbound
                              ? e.dst_node_id
                              : e.src_node_id;
                            const n = visibleNodes.find((x) => x.id === id);
                            if (n) focusNode(n);
                          }}
                        >
                          {otherSym ?? other}
                        </button>
                        {e.ownership_pct != null ? (
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {e.ownership_pct}%
                          </span>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </div>

              {selected.symbol ? (
                <Button asChild variant="secondary" size="sm" className="w-full">
                  <Link
                    href={`/symbols/${encodeURIComponent(selected.symbol)}`}
                  >
                    Open symbol
                  </Link>
                </Button>
              ) : null}
            </div>
          ) : (
            <div className={cn("space-y-2 text-sm text-muted-foreground")}>
              <p className="font-medium text-foreground">Nothing selected</p>
              <p>
                Showing the full ownership map. Click a company for equity,
                market cap, and links — or click the blank canvas to clear a
                focus.
              </p>
              <p className="text-[11px]">
                {visibleNodes.length} companies ({linkedListedCount} linked) ·{" "}
                {visibleEdges.length} links · isolates have no PDF ties yet
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
