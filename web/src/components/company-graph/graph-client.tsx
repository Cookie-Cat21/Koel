"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { CompanyGraphCanvas } from "@/components/company-graph/graph-canvas";
import { EmptyState } from "@/components/empty-state";
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
  return node.equity * mult;
}

const RELATION_LABEL: Record<string, string> = {
  subsidiary: "Subsidiary",
  associate: "Associate",
  joint_venture: "Joint venture",
  related_party: "Related party",
  group_mention: "Group mention",
};

export function CompanyGraphClient({
  nodes,
  edges,
  initialFocus,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  initialFocus?: string | null;
}) {
  const initialSelected =
    nodes.find((n) => n.symbol === initialFocus)?.id ??
    nodes.find((n) => n.node_kind === "listed")?.id ??
    null;

  const [selectedId, setSelectedId] = useState<number | null>(initialSelected);
  const [query, setQuery] = useState(initialFocus ?? "");
  const [minConf, setMinConf] = useState<"medium" | "high" | "low">("medium");
  const [holdingsOnly, setHoldingsOnly] = useState(false);

  const filteredEdges = useMemo(() => {
    const rank = { low: 1, medium: 2, high: 3 } as const;
    return edges.filter((e) => rank[e.confidence] >= rank[minConf]);
  }, [edges, minConf]);

  const activeNodeIds = useMemo(() => {
    const ids = new Set<number>();
    for (const e of filteredEdges) {
      ids.add(e.src_node_id);
      ids.add(e.dst_node_id);
    }
    if (ids.size === 0) {
      for (const n of nodes) {
        if (n.equity != null) ids.add(n.id);
      }
    }
    return ids;
  }, [filteredEdges, nodes]);

  const visibleNodes = useMemo(() => {
    let list = nodes.filter((n) => activeNodeIds.has(n.id));
    if (holdingsOnly) {
      const hubIds = new Set(
        filteredEdges
          .filter((e) => e.relation === "subsidiary" || e.relation === "associate")
          .map((e) => e.src_node_id),
      );
      list = list.filter(
        (n) => hubIds.has(n.id) || (n.name.toLowerCase().includes("holdings") && n.node_kind === "listed"),
      );
      // Keep neighbors of hubs
      const keep = new Set(list.map((n) => n.id));
      for (const e of filteredEdges) {
        if (keep.has(e.src_node_id)) keep.add(e.dst_node_id);
      }
      list = nodes.filter((n) => keep.has(n.id) && activeNodeIds.has(n.id));
    }
    return list;
  }, [nodes, activeNodeIds, holdingsOnly, filteredEdges]);

  const visibleEdges = useMemo(() => {
    const ids = new Set(visibleNodes.map((n) => n.id));
    return filteredEdges.filter(
      (e) => ids.has(e.src_node_id) && ids.has(e.dst_node_id),
    );
  }, [filteredEdges, visibleNodes]);

  const selected = visibleNodes.find((n) => n.id === selectedId) ?? null;
  const selectedEdges = useMemo(() => {
    const raw = visibleEdges.filter(
      (e) => e.src_node_id === selectedId || e.dst_node_id === selectedId,
    );
    // Prefer stronger relation labels when the same pair appears twice
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

  function focusSearch() {
    const q = query.trim().toUpperCase();
    if (!q) return;
    const hit = visibleNodes.find(
      (n) =>
        (n.symbol && n.symbol.includes(q)) ||
        n.name.toUpperCase().includes(q),
    );
    if (hit) setSelectedId(hit.id);
  }

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
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="flex min-w-0 flex-1 gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") focusSearch();
            }}
            placeholder="Focus symbol (e.g. JKH)"
            className="max-w-xs"
            aria-label="Focus symbol"
          />
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
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Min confidence
          <select
            value={minConf}
            onChange={(e) =>
              setMinConf(e.target.value as "low" | "medium" | "high")
            }
            className="rounded-md border border-border bg-background px-2 py-1 text-foreground"
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
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
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <CompanyGraphCanvas
          nodes={visibleNodes}
          edges={visibleEdges}
          selectedId={selectedId}
          onSelect={setSelectedId}
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
                  <dt className="text-xs text-muted-foreground">Market cap</dt>
                  <dd className="font-mono tabular-nums">
                    {formatCompactNumber(selected.market_cap, 1)}
                  </dd>
                </div>
                <div className="rounded-lg border border-border/70 px-3 py-2">
                  <dt className="text-xs text-muted-foreground">
                    Equity / net assets
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
                <ul className="max-h-48 space-y-1.5 overflow-y-auto text-sm">
                  {selectedEdges.slice(0, 24).map((e) => {
                    const outbound = e.src_node_id === selected.id;
                    const other = outbound ? e.dst_name : e.src_name;
                    const otherSym = outbound ? e.dst_symbol : e.src_symbol;
                    return (
                      <li
                        key={e.id}
                        className="flex flex-wrap items-center gap-1.5"
                      >
                        <Badge variant="outline" className="text-[10px]">
                          {outbound ? "→" : "←"} {RELATION_LABEL[e.relation]}
                        </Badge>
                        <span className="truncate text-foreground">
                          {otherSym ?? other}
                        </span>
                        {e.ownership_pct != null ? (
                          <span className="text-xs text-muted-foreground">
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
                  <Link href={`/symbols/${encodeURIComponent(selected.symbol)}`}>
                    Open symbol
                  </Link>
                </Button>
              ) : null}
            </div>
          ) : (
            <p className={cn("text-sm text-muted-foreground")}>
              Select a company node to see equity, market cap, and linked
              entities.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}
