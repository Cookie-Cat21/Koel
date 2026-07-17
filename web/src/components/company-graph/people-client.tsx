"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import {
  Background,
  Controls,
  type Edge,
  Handle,
  MarkerType,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { PersonNode } from "@/lib/api/people-graph";
import { formatCompactNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<string, string> = {
  chairman: "Chairman",
  deputy_chairman: "Co/Deputy chair",
  ceo: "CEO",
  managing_director: "MD",
  executive_director: "Exec director",
  non_executive_director: "Non-exec",
  independent_director: "Independent",
  senior_independent_director: "Senior indep.",
  cfo: "CFO",
  company_secretary: "Secretary",
  director: "Director",
  key_management: "Key mgmt",
};

type PData = { label: string; sub: string; size: number; selected: boolean };
type CData = { label: string; sub: string; size: number; selected: boolean };

function PersonBubble({ data }: NodeProps<Node<PData>>) {
  return (
    <div
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-full border border-border bg-card px-2 text-center shadow-sm transition-transform hover:scale-105",
        data.selected && "ring-2 ring-ring",
      )}
      style={{ width: data.size, height: data.size }}
    >
      <Handle type="source" position={Position.Right} className="!size-1.5 !bg-border" />
      <span className="max-w-[5rem] truncate text-[10px] font-semibold leading-tight">
        {data.label}
      </span>
      <span className="max-w-[5rem] truncate text-[9px] text-muted-foreground">
        {data.sub}
      </span>
    </div>
  );
}

function CompanyBubble({ data }: NodeProps<Node<CData>>) {
  return (
    <div
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-lg border border-border bg-muted/40 px-2 text-center transition-transform hover:scale-105",
        data.selected && "ring-2 ring-ring",
      )}
      style={{ width: data.size, height: data.size * 0.72 }}
    >
      <Handle type="target" position={Position.Left} className="!size-1.5 !bg-border" />
      <span className="font-mono text-[10px] font-semibold">{data.label}</span>
      <span className="text-[9px] text-muted-foreground">{data.sub}</span>
    </div>
  );
}

const nodeTypes = { person: PersonBubble, company: CompanyBubble };

function shortName(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length <= 2) return name;
  return `${parts[0]} ${parts[parts.length - 1]}`;
}

function PeopleFlow({
  people,
  selectedId,
  onSelect,
}: {
  people: PersonNode[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const top = people.slice(0, 36);
  const companies = new Map<string, { mcap: number | null; name: string | null }>();
  for (const p of top) {
    for (const r of p.roles) {
      const prev = companies.get(r.symbol);
      if (!prev || (r.market_cap ?? 0) > (prev.mcap ?? 0)) {
        companies.set(r.symbol, {
          mcap: r.market_cap,
          name: r.company_name,
        });
      }
    }
  }

  const maxInf = Math.max(...top.map((p) => p.influence_score), 1);
  const companyList = Array.from(companies.entries()).slice(0, 40);

  const nodes: Node[] = [];
  const personCols = 3;
  top.forEach((p, i) => {
    const size = 36 + (p.influence_score / maxInf) * 32;
    const col = i % personCols;
    const row = Math.floor(i / personCols);
    nodes.push({
      id: `p-${p.id}`,
      type: "person",
      position: { x: 24 + col * 120, y: 20 + row * 62 },
      data: {
        label: shortName(p.name),
        sub: formatCompactNumber(p.influence_score, 1),
        size,
        selected: selectedId === p.id,
      },
    });
  });
  const companyX = 24 + personCols * 120 + 48;
  companyList.forEach(([sym, meta], i) => {
    const size = 48 + Math.min(24, Math.log10(Math.max(meta.mcap ?? 1e9, 1e9)) * 3);
    nodes.push({
      id: `c-${sym}`,
      type: "company",
      position: {
        x: companyX,
        y: 16 + i * Math.max(40, Math.min(52, 520 / Math.max(companyList.length, 1))),
      },
      data: {
        label: sym.replace(/\.(N|X)0000$/i, ""),
        sub: formatCompactNumber(meta.mcap, 1),
        size,
        selected: false,
      },
    });
  });

  const edges: Edge[] = [];
  for (const p of top) {
    const seen = new Set<string>();
    for (const r of p.roles) {
      if (seen.has(r.symbol) || !companies.has(r.symbol)) continue;
      seen.add(r.symbol);
      edges.push({
        id: `e-${p.id}-${r.symbol}-${r.role}`,
        source: `p-${p.id}`,
        target: `c-${r.symbol}`,
        label: ROLE_LABEL[r.role] ?? r.role,
        style: { stroke: "var(--chart-1)", strokeWidth: 1.2, opacity: 0.7 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 12,
          height: 12,
          color: "var(--chart-1)",
        },
        labelStyle: { fontSize: 8, fill: "var(--muted-foreground)" },
        labelBgStyle: { fill: "var(--background)", fillOpacity: 0.8 },
      });
    }
  }

  return (
    <div className="h-[min(70vh,560px)] w-full overflow-hidden rounded-xl border border-border bg-background/60">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => {
          if (node.id.startsWith("p-")) {
            const id = Number(node.id.slice(2));
            onSelect(Number.isFinite(id) ? id : null);
          }
        }}
        onPaneClick={() => onSelect(null)}
        nodesDraggable
      >
        <Background gap={22} size={1} color="var(--border)" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export function PeopleGraphClient({ people }: { people: PersonNode[] }) {
  const [selectedId, setSelectedId] = useState<number | null>(
    people[0]?.id ?? null,
  );
  const [leadershipOnly, setLeadershipOnly] = useState(false);

  const filtered = useMemo(() => {
    if (!leadershipOnly) return people;
    const lead = new Set([
      "chairman",
      "ceo",
      "managing_director",
      "deputy_chairman",
      "executive_director",
      "cfo",
    ]);
    return people.filter((p) => p.roles.some((r) => lead.has(r.role)));
  }, [people, leadershipOnly]);

  const selected = filtered.find((p) => p.id === selectedId) ?? filtered[0] ?? null;

  if (people.length === 0) {
    return (
      <EmptyState
        title="No people extracted yet"
        description="Run directors-backfill to pull official CSE companyProfile boards into the map."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={leadershipOnly}
            onChange={(e) => setLeadershipOnly(e.target.checked)}
            className="size-4 rounded border-border"
          />
          Leadership seats only
        </label>
        <Badge variant="outline" className="tabular-nums">
          {filtered.length} people
        </Badge>
        <p className="text-xs text-muted-foreground">
          Bubble size = linked company market value × role weight — not personal
          net worth.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <ReactFlowProvider>
          <PeopleFlow
            people={filtered}
            selectedId={selected?.id ?? null}
            onSelect={setSelectedId}
          />
        </ReactFlowProvider>

        <aside className="space-y-3 rounded-xl border border-border bg-card/40 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Influence ranking
            </p>
            <p className="text-[11px] text-muted-foreground">
              Research proxy from board seats × company market cap (LKR).
            </p>
          </div>
          <ol className="max-h-56 space-y-1 overflow-y-auto text-sm">
            {filtered.slice(0, 30).map((p, i) => (
              <li key={p.id}>
                <button
                  type="button"
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1 text-left hover:bg-muted",
                    selected?.id === p.id && "bg-muted",
                  )}
                  onClick={() => setSelectedId(p.id)}
                >
                  <span className="truncate">
                    <span className="mr-1.5 text-muted-foreground">{i + 1}.</span>
                    {p.name}
                  </span>
                  <span className="shrink-0 font-mono text-xs tabular-nums">
                    {formatCompactNumber(p.influence_score, 1)}
                  </span>
                </button>
              </li>
            ))}
          </ol>

          {selected ? (
            <div className="space-y-2 border-t border-border pt-3">
              <h2 className="font-display text-base font-semibold">
                {selected.name}
              </h2>
              <p className="text-xs text-muted-foreground">
                Top role:{" "}
                {selected.top_role
                  ? ROLE_LABEL[selected.top_role]
                  : "—"}{" "}
                · {selected.company_count} compan
                {selected.company_count === 1 ? "y" : "ies"}
              </p>
              <dl className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                <dt className="text-xs text-muted-foreground">
                  Linked market influence (LKR)
                </dt>
                <dd className="font-mono text-lg tabular-nums">
                  {formatCompactNumber(selected.influence_score, 1)}
                </dd>
              </dl>
              <ul className="max-h-44 space-y-1.5 overflow-y-auto text-sm">
                {selected.roles.map((r) => (
                  <li
                    key={`${r.symbol}-${r.role}`}
                    className="flex flex-wrap items-center gap-1.5"
                  >
                    <Badge variant="outline" className="text-[10px]">
                      {ROLE_LABEL[r.role] ?? r.role}
                    </Badge>
                    <Link
                      href={`/symbols/${encodeURIComponent(r.symbol)}`}
                      className="font-mono text-foreground underline-offset-2 hover:underline"
                    >
                      {r.symbol.replace(/\.(N|X)0000$/i, "")}
                    </Link>
                    <span className="text-xs text-muted-foreground">
                      mcap {formatCompactNumber(r.market_cap, 1)}
                    </span>
                  </li>
                ))}
              </ul>
              <Button asChild variant="secondary" size="sm" className="w-full">
                <Link href="/graph">Company ownership map</Link>
              </Button>
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
