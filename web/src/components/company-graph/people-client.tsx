"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

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
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { EmptyState } from "@/components/empty-state";
import { FilterChip } from "@/components/kit/rank-bar-list";
import { Button } from "@/components/ui/button";
import type { PersonNode, PersonRole } from "@/lib/api/people-graph";
import { ROLE_WEIGHT } from "@/lib/api/people-graph";
import { formatCompactNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<string, string> = {
  chairman: "Chair",
  deputy_chairman: "Deputy",
  ceo: "CEO",
  managing_director: "MD",
  executive_director: "Exec",
  non_executive_director: "NED",
  independent_director: "Indep",
  senior_independent_director: "Sr indep",
  cfo: "CFO",
  company_secretary: "Sec",
  director: "Dir",
  key_management: "Key",
};

const ROLE_SORT = (a: string, b: string) =>
  (ROLE_WEIGHT[b as PersonRole] ?? 0) - (ROLE_WEIGHT[a as PersonRole] ?? 0);

const CANVAS_PEOPLE = 18;
const CANVAS_COMPANIES = 22;

function ticker(symbol: string): string {
  return symbol.replace(/\.(N|X)0000$/i, "");
}

function shortName(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length <= 2) return name;
  const last = parts[parts.length - 1];
  const head = parts.slice(0, -1);
  if (head.every((p) => p.length <= 2)) {
    return `${head.slice(0, 3).join(" ")}${head.length > 3 ? "…" : ""} ${last}`;
  }
  return `${parts[0]} ${last}`;
}

function rolesSummary(roles: string[]): string {
  const sorted = [...roles].sort(ROLE_SORT);
  if (sorted.length === 0) return "—";
  if (sorted.length === 1) return ROLE_LABEL[sorted[0]] ?? sorted[0];
  if (sorted.length === 2) {
    return `${ROLE_LABEL[sorted[0]] ?? sorted[0]}; ${ROLE_LABEL[sorted[1]] ?? sorted[1]}`;
  }
  return `${ROLE_LABEL[sorted[0]] ?? sorted[0]} +${sorted.length - 1}`;
}

function groupRolesByCompany(person: PersonNode) {
  const bySym = new Map<
    string,
    {
      symbol: string;
      company_name: string | null;
      market_cap: number | null;
      volume: number | null;
      turnover: number | null;
      price: number | null;
      change_pct: number | null;
      roles: string[];
    }
  >();
  for (const r of person.roles) {
    const prev = bySym.get(r.symbol);
    if (!prev) {
      bySym.set(r.symbol, {
        symbol: r.symbol,
        company_name: r.company_name,
        market_cap: r.market_cap,
        volume: r.volume,
        turnover: r.turnover,
        price: r.price,
        change_pct: r.change_pct,
        roles: [r.role],
      });
      continue;
    }
    if (!prev.roles.includes(r.role)) prev.roles.push(r.role);
    if ((r.market_cap ?? 0) > (prev.market_cap ?? 0)) {
      prev.market_cap = r.market_cap;
    }
    if (prev.volume == null && r.volume != null) prev.volume = r.volume;
    if (prev.turnover == null && r.turnover != null) prev.turnover = r.turnover;
    if (prev.price == null && r.price != null) prev.price = r.price;
    if (prev.change_pct == null && r.change_pct != null) {
      prev.change_pct = r.change_pct;
    }
  }
  return Array.from(bySym.values())
    .map((row) => ({ ...row, roles: [...row.roles].sort(ROLE_SORT) }))
    .sort(
      (a, b) =>
        (b.volume ?? 0) - (a.volume ?? 0) ||
        (b.market_cap ?? 0) - (a.market_cap ?? 0),
    );
}

function initialsAvatar(name: string): string {
  const parts = name.replace(/\./g, " ").split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[parts.length - 1][0] ?? ""}`.toUpperCase();
}

type PData = {
  label: string;
  sub: string;
  selected: boolean;
  dimmed: boolean;
};
type CData = {
  label: string;
  sub: string;
  selected: boolean;
  dimmed: boolean;
};

function PersonPill({ data }: NodeProps<Node<PData>>) {
  return (
    <div
      className={cn(
        "flex h-10 w-[152px] cursor-pointer flex-col justify-center rounded-md border bg-background px-2.5 transition-[transform,opacity,border-color,box-shadow] duration-150 motion-safe:hover:scale-[1.03] hover:border-foreground/30",
        data.selected
          ? "border-foreground/40 shadow-sm"
          : "border-border",
        data.dimmed && "opacity-20",
      )}
    >
      <Handle
        type="source"
        position={Position.Right}
        className="!size-1.5 !bg-border"
      />
      <span className="truncate text-[11px] font-semibold leading-tight">
        {data.label}
      </span>
      <span className="truncate font-mono text-[10px] tabular-nums text-muted-foreground">
        {data.sub}
      </span>
    </div>
  );
}

function CompanyPill({ data }: NodeProps<Node<CData>>) {
  return (
    <div
      className={cn(
        "flex h-10 w-[100px] cursor-pointer flex-col justify-center rounded-md border bg-muted/30 px-2 transition-[transform,opacity,border-color] duration-150 motion-safe:hover:scale-[1.03]",
        data.selected ? "border-foreground/40 bg-background" : "border-border",
        data.dimmed && "opacity-20",
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-1.5 !bg-border"
      />
      <span className="font-mono text-[11px] font-semibold">{data.label}</span>
      <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
        {data.sub}
      </span>
    </div>
  );
}

const nodeTypes = { person: PersonPill, company: CompanyPill };

function orderBipartite(
  peopleIds: number[],
  companyIds: string[],
  links: Array<{ personId: number; symbol: string }>,
): { people: number[]; companies: string[] } {
  let people = [...peopleIds];
  let companies = [...companyIds];
  for (let iter = 0; iter < 4; iter++) {
    const pIndex = new Map(people.map((id, i) => [id, i]));
    companies = [...companies].sort((a, b) => {
      const aLinks = links.filter((l) => l.symbol === a);
      const bLinks = links.filter((l) => l.symbol === b);
      const aBar =
        aLinks.reduce((s, l) => s + (pIndex.get(l.personId) ?? 0), 0) /
        Math.max(aLinks.length, 1);
      const bBar =
        bLinks.reduce((s, l) => s + (pIndex.get(l.personId) ?? 0), 0) /
        Math.max(bLinks.length, 1);
      return aBar - bBar;
    });
    const cIndex = new Map(companies.map((id, i) => [id, i]));
    people = [...people].sort((a, b) => {
      const aLinks = links.filter((l) => l.personId === a);
      const bLinks = links.filter((l) => l.personId === b);
      const aBar =
        aLinks.reduce((s, l) => s + (cIndex.get(l.symbol) ?? 0), 0) /
        Math.max(aLinks.length, 1);
      const bBar =
        bLinks.reduce((s, l) => s + (cIndex.get(l.symbol) ?? 0), 0) /
        Math.max(bLinks.length, 1);
      return aBar - bBar;
    });
  }
  return { people, companies };
}

function FitViewOnChange({ nonce }: { nonce: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    // Wait a frame so the fixed-height container has measured before fitting.
    const t = window.setTimeout(() => {
      void fitView({ padding: 0.18, duration: 180, maxZoom: 1.35 });
    }, 60);
    return () => window.clearTimeout(t);
  }, [fitView, nonce]);
  return null;
}

function PeopleFlow({
  people,
  selectedId,
  onSelect,
  searching,
}: {
  people: PersonNode[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  searching: boolean;
}) {
  const router = useRouter();
  const layout = useMemo(() => {
    const ranked = [...people].sort(
      (a, b) => b.influence_score - a.influence_score,
    );
    const budget = searching
      ? Math.min(ranked.length, 24)
      : Math.min(ranked.length, CANVAS_PEOPLE);
    const visiblePeople = ranked.slice(0, budget);

    const companyMeta = new Map<
      string,
      { mcap: number | null; degree: number }
    >();
    const links: Array<{ personId: number; symbol: string; role: string }> =
      [];
    for (const p of visiblePeople) {
      const seen = new Set<string>();
      for (const r of p.roles) {
        if (seen.has(r.symbol)) continue;
        seen.add(r.symbol);
        links.push({ personId: p.id, symbol: r.symbol, role: r.role });
        const prev = companyMeta.get(r.symbol);
        companyMeta.set(r.symbol, {
          mcap: Math.max(prev?.mcap ?? 0, r.market_cap ?? 0) || r.market_cap,
          degree: (prev?.degree ?? 0) + 1,
        });
      }
    }

    const companyIds = Array.from(companyMeta.entries())
      .sort((a, b) => {
        if (b[1].degree !== a[1].degree) return b[1].degree - a[1].degree;
        return (b[1].mcap ?? 0) - (a[1].mcap ?? 0);
      })
      .slice(0, CANVAS_COMPANIES)
      .map(([sym]) => sym);
    const companySet = new Set(companyIds);
    const visibleLinks = links.filter((l) => companySet.has(l.symbol));
    const ordered = orderBipartite(
      visiblePeople.map((p) => p.id),
      companyIds,
      visibleLinks,
    );
    const byId = new Map(visiblePeople.map((p) => [p.id, p]));

    const selectedCompanies = new Set<string>();
    if (selectedId != null) {
      for (const l of visibleLinks) {
        if (l.personId === selectedId) selectedCompanies.add(l.symbol);
      }
    }
    const focusActive = selectedId != null;

    const flowNodes: Node[] = [];
    ordered.people.forEach((id, i) => {
      const p = byId.get(id);
      if (!p) return;
      flowNodes.push({
        id: `p-${id}`,
        type: "person",
        position: { x: 20, y: 12 + i * 52 },
        data: {
          label: shortName(p.name),
          sub: formatCompactNumber(p.influence_score, 1),
          selected: id === selectedId,
          dimmed: focusActive && id !== selectedId,
        },
        zIndex: id === selectedId ? 4 : 1,
      });
    });
    ordered.companies.forEach((sym, i) => {
      const meta = companyMeta.get(sym);
      flowNodes.push({
        id: `c-${sym}`,
        type: "company",
        position: { x: 340, y: 12 + i * 48 },
        data: {
          label: ticker(sym),
          sub: formatCompactNumber(meta?.mcap ?? null, 1),
          selected: selectedCompanies.has(sym),
          dimmed: focusActive && !selectedCompanies.has(sym),
        },
        zIndex: selectedCompanies.has(sym) ? 3 : 1,
      });
    });

    const flowEdges: Edge[] = [];
    const edgeSeen = new Set<string>();
    for (const l of visibleLinks) {
      const key = `${l.personId}:${l.symbol}`;
      if (edgeSeen.has(key)) continue;
      edgeSeen.add(key);
      const focused = selectedId != null && l.personId === selectedId;
      const faded = focusActive && !focused;
      const person = byId.get(l.personId);
      const role =
        person?.roles.find((r) => r.symbol === l.symbol)?.role ?? l.role;
      flowEdges.push({
        id: `e-${key}`,
        source: `p-${l.personId}`,
        target: `c-${l.symbol}`,
        type: "smoothstep",
        label: focused ? (ROLE_LABEL[role] ?? role) : undefined,
        animated: focused,
        style: {
          stroke: focused ? "var(--chart-1)" : "var(--border)",
          strokeWidth: focused ? 2 : 1,
          opacity: faded ? 0.06 : focused ? 0.95 : 0.28,
        },
        markerEnd: focused
          ? {
              type: MarkerType.ArrowClosed,
              width: 12,
              height: 12,
              color: "var(--chart-1)",
            }
          : undefined,
        labelStyle: { fontSize: 10, fill: "var(--foreground)", fontWeight: 600 },
        labelBgStyle: { fill: "var(--background)", fillOpacity: 0.95 },
        labelBgPadding: [3, 5] as [number, number],
        zIndex: focused ? 5 : 0,
      });
    }

    return {
      nodes: flowNodes,
      edges: flowEdges,
      layoutKey: `${ordered.people.join(",")}|${selectedId ?? "x"}|${searching}`,
    };
  }, [people, selectedId, searching]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layout.edges);

  useEffect(() => {
    setNodes(layout.nodes);
    setEdges(layout.edges);
  }, [layout.nodes, layout.edges, setNodes, setEdges]);

  if (people.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-border text-sm text-muted-foreground">
        No people match this filter.
      </div>
    );
  }

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-border bg-background">
      <p className="pointer-events-none absolute left-3 top-3 z-10 text-[10px] text-muted-foreground">
        Click a person to inspect seats
        {!searching
          ? ` · top ${Math.min(people.length, CANVAS_PEOPLE)} on canvas`
          : null}
      </p>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18, maxZoom: 1.35 }}
        minZoom={0.35}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
        onNodeClick={(_, node) => {
          if (node.id.startsWith("p-")) {
            const id = Number(node.id.slice(2));
            onSelect(Number.isFinite(id) ? id : null);
          } else if (node.id.startsWith("c-")) {
            const sym = node.id.slice(2);
            const linked = people
              .filter((p) => p.roles.some((r) => r.symbol === sym))
              .sort((a, b) => b.influence_score - a.influence_score);
            if (linked[0]) onSelect(linked[0].id);
          }
        }}
        onNodeDoubleClick={(_, node) => {
          if (!node.id.startsWith("p-")) return;
          const id = Number(node.id.slice(2));
          if (Number.isFinite(id)) router.push(`/people/${id}`);
        }}
        onPaneClick={() => onSelect(null)}
      >
        <Background gap={18} size={1} color="var(--border)" />
        <Controls
          showInteractive={false}
          position="bottom-left"
          className="!scale-110"
        />
        <FitViewOnChange nonce={layout.layoutKey} />
      </ReactFlow>
    </div>
  );
}

function RankRow({
  person,
  rank,
  maxScore,
  selected,
  onSelect,
}: {
  person: PersonNode;
  rank: number;
  maxScore: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const router = useRouter();
  const pct = maxScore > 0 ? (person.influence_score / maxScore) * 100 : 0;
  const topLabel = person.top_role
    ? ROLE_LABEL[person.top_role] ?? person.top_role
    : "—";
  return (
    <li>
      <div
        data-person-id={person.id}
        className={cn(
          "group relative rounded-md transition-colors duration-150",
          selected ? "bg-muted" : "hover:bg-muted/60",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-foreground transition-opacity",
            selected ? "opacity-100" : "opacity-0 group-hover:opacity-40",
          )}
        />
        <button
          type="button"
          title={`${person.name} — click to inspect, Enter for dossier`}
          onClick={onSelect}
          onDoubleClick={() => router.push(`/people/${person.id}`)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              router.push(`/people/${person.id}`);
            }
          }}
          className="grid w-full grid-cols-[1.5rem_minmax(0,1fr)_auto] items-baseline gap-x-2 px-2 py-2 pl-3 text-left"
        >
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {rank}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-medium leading-tight">
              {person.name}
            </span>
            <span className="mt-0.5 block truncate text-[10px] text-muted-foreground">
              {topLabel} · {person.company_count} co
              {person.company_count === 1 ? "" : "s"} · vol{" "}
              {formatCompactNumber(person.linked_volume, 1)}
            </span>
          </span>
          <span className="shrink-0 text-right">
            <span className="block font-mono text-xs tabular-nums">
              {formatCompactNumber(person.influence_score, 1)}
            </span>
            <span className="mt-0.5 block font-mono text-[10px] tabular-nums text-muted-foreground">
              to {formatCompactNumber(person.linked_turnover, 1)}
            </span>
          </span>
        </button>
        <div className="mx-2 mb-1.5 ml-9 h-1 overflow-hidden rounded-sm bg-muted">
          <div
            className="h-full rounded-sm bg-foreground/70 transition-[width] duration-300"
            style={{ width: `${Math.max(pct, 2)}%` }}
          />
        </div>
        <div className="flex justify-end px-2 pb-1.5">
          <Link
            href={`/people/${person.id}`}
            className="text-[10px] font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            Open dossier →
          </Link>
        </div>
      </div>
    </li>
  );
}

function PersonInspector({ person }: { person: PersonNode }) {
  const seats = groupRolesByCompany(person);
  const panelRef = useRef<HTMLDivElement>(null);
  const [spot, setSpot] = useState({ x: 40, y: 30 });

  function onMove(e: ReactMouseEvent<HTMLDivElement>) {
    const el = panelRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setSpot({
      x: ((e.clientX - rect.left) / Math.max(rect.width, 1)) * 100,
      y: ((e.clientY - rect.top) / Math.max(rect.height, 1)) * 100,
    });
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col border-t border-border bg-background animate-in fade-in-0 slide-in-from-bottom-1 duration-150">
      <div
        ref={panelRef}
        onMouseMove={onMove}
        className="relative overflow-hidden border-b border-border px-4 py-3"
        style={{
          backgroundImage: `radial-gradient(420px circle at ${spot.x}% ${spot.y}%, color-mix(in oklab, var(--muted) 80%, transparent), transparent 55%)`,
        }}
      >
        <div className="relative flex items-start gap-3">
          <div
            aria-hidden
            className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-background font-mono text-[11px] font-semibold"
          >
            {initialsAvatar(person.name)}
          </div>
          <div className="min-w-0 flex-1">
            <h2
              className="truncate font-display text-[15px] font-semibold leading-snug"
              title={person.name}
            >
              {person.name}
            </h2>
            <p className="text-[11px] text-muted-foreground">
              {person.top_role ? ROLE_LABEL[person.top_role] : "—"} ·{" "}
              {person.company_count} compan
              {person.company_count === 1 ? "y" : "ies"}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
              Influence
            </p>
            <p className="font-mono text-lg font-semibold tabular-nums leading-none">
              {formatCompactNumber(person.influence_score, 1)}
            </p>
          </div>
        </div>
        <dl className="relative mt-2 grid grid-cols-2 gap-2">
          <div className="rounded-md bg-background/70 px-2.5 py-1.5">
            <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Linked vol
            </dt>
            <dd className="font-mono text-sm font-semibold tabular-nums">
              {formatCompactNumber(person.linked_volume, 1)}
            </dd>
          </div>
          <div className="rounded-md bg-background/70 px-2.5 py-1.5">
            <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Turnover
            </dt>
            <dd className="font-mono text-sm font-semibold tabular-nums">
              {formatCompactNumber(person.linked_turnover, 1)}
            </dd>
          </div>
        </dl>
        <div className="relative mt-2">
          <Button asChild size="sm" className="w-full">
            <Link href={`/people/${person.id}`}>
              Open full dossier · network & years
            </Link>
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="sticky top-0 z-[1] grid grid-cols-[3.5rem_minmax(0,1fr)_3.2rem_3.2rem] gap-x-2 border-b border-border bg-background/95 px-4 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground backdrop-blur">
          <span>Ticker</span>
          <span>Roles</span>
          <span className="text-right">Vol</span>
          <span className="text-right">Mcap</span>
        </div>
        {seats.length === 0 ? (
          <p className="px-4 py-6 text-center text-[12px] text-muted-foreground">
            No linked companies in this filter.
          </p>
        ) : (
          <ul className="divide-y divide-border/70">
            {seats.map((row, i) => (
              <li
                key={row.symbol}
                className="grid grid-cols-[3.5rem_minmax(0,1fr)_3.2rem_3.2rem] items-center gap-x-2 px-4 py-2 transition-opacity duration-200"
                style={{
                  animationDelay: `${Math.min(i, 8) * 35}ms`,
                }}
              >
                <Link
                  href={`/symbols/${encodeURIComponent(row.symbol)}`}
                  className="font-mono text-[12px] font-semibold underline-offset-2 hover:underline"
                  title={row.company_name ?? row.symbol}
                >
                  {ticker(row.symbol)}
                </Link>
                <span
                  className="truncate text-[11px] text-muted-foreground"
                  title={row.roles
                    .map((r) => ROLE_LABEL[r] ?? r)
                    .join("; ")}
                >
                  {rolesSummary(row.roles)}
                  {row.price != null ? (
                    <span className="ml-1 font-mono tabular-nums">
                      · {formatCompactNumber(row.price, 2)}
                    </span>
                  ) : null}
                </span>
                <span className="text-right font-mono text-[11px] tabular-nums text-foreground">
                  {formatCompactNumber(row.volume, 1)}
                </span>
                <span className="text-right font-mono text-[11px] tabular-nums text-muted-foreground">
                  {formatCompactNumber(row.market_cap, 1)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-border p-3">
        <Button asChild variant="outline" size="sm" className="w-full">
          <Link href="/graph">Company ownership map</Link>
        </Button>
      </div>
    </div>
  );
}

export function PeopleGraphClient({ people }: { people: PersonNode[] }) {
  const [selectedId, setSelectedId] = useState<number | null>(
    people[0]?.id ?? null,
  );
  const [leadershipOnly, setLeadershipOnly] = useState(true);
  const [query, setQuery] = useState("");
  const listRef = useRef<HTMLOListElement>(null);

  const filtered = useMemo(() => {
    const lead = new Set([
      "chairman",
      "ceo",
      "managing_director",
      "deputy_chairman",
      "executive_director",
      "cfo",
    ]);
    const q = query.trim().toLowerCase();
    return people.filter((p) => {
      if (leadershipOnly && !p.roles.some((r) => lead.has(r.role))) return false;
      if (!q) return true;
      if (p.name.toLowerCase().includes(q)) return true;
      return p.roles.some(
        (r) =>
          r.symbol.toLowerCase().includes(q) ||
          (r.company_name?.toLowerCase().includes(q) ?? false),
      );
    });
  }, [people, leadershipOnly, query]);

  const ranked = useMemo(
    () =>
      [...filtered].sort((a, b) => b.influence_score - a.influence_score),
    [filtered],
  );
  const maxScore = ranked[0]?.influence_score ?? 1;

  const activeId =
    selectedId != null && filtered.some((p) => p.id === selectedId)
      ? selectedId
      : (filtered[0]?.id ?? null);

  useEffect(() => {
    if (activeId == null || !listRef.current) return;
    const el = listRef.current.querySelector(
      `[data-person-id="${activeId}"]`,
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [activeId]);

  const selected = ranked.find((p) => p.id === activeId) ?? null;
  const searching = query.trim().length > 0;

  if (people.length === 0) {
    return (
      <EmptyState
        title="No people extracted yet"
        description="Run directors-backfill to pull official CSE companyProfile boards into the map."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search people or symbols…"
          className="h-9 w-full max-w-[16rem] rounded-md border border-border bg-background px-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Search people or symbols"
        />
        <FilterChip
          active={!leadershipOnly}
          onClick={() => setLeadershipOnly(false)}
        >
          All roles
        </FilterChip>
        <FilterChip
          active={leadershipOnly}
          onClick={() => setLeadershipOnly(true)}
        >
          Leadership
        </FilterChip>
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {filtered.length} people
        </span>
        <span className="hidden text-[11px] text-muted-foreground sm:inline">
          Not personal net worth
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-stretch">
        {/* Fixed height (not min-height): React Flow + fitView mis-measure a
            min-height-only parent and translate the bipartite graph off-screen. */}
        <div className="h-[min(72vh,640px)] min-h-[420px]">
          <ReactFlowProvider>
            <PeopleFlow
              people={ranked}
              selectedId={selected?.id ?? null}
              onSelect={setSelectedId}
              searching={searching}
            />
          </ReactFlowProvider>
        </div>

        <aside className="flex h-[min(72vh,640px)] min-h-[420px] flex-col overflow-hidden rounded-xl border border-border bg-background">
          <div className="border-b border-border px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Influence ranking
            </p>
            <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
              Σ (market cap × role weight). Enter / double-click opens dossier.
              Boards from CSE companyProfile — refresh via directors-backfill.
            </p>
          </div>

          {ranked.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center">
              <p className="text-sm text-muted-foreground">No matches</p>
              {query ? (
                <button
                  type="button"
                  className="text-[12px] text-foreground underline-offset-2 hover:underline"
                  onClick={() => setQuery("")}
                >
                  Clear search
                </button>
              ) : null}
            </div>
          ) : (
            <ol
              ref={listRef}
              className="max-h-[46%] min-h-0 space-y-0.5 overflow-y-auto px-1.5 py-1.5"
            >
              {ranked.slice(0, 80).map((p, i) => (
                <RankRow
                  key={p.id}
                  person={p}
                  rank={i + 1}
                  maxScore={maxScore}
                  selected={selected?.id === p.id}
                  onSelect={() => setSelectedId(p.id)}
                />
              ))}
            </ol>
          )}

          {selected ? (
            <PersonInspector person={selected} />
          ) : (
            <div className="flex flex-1 items-center justify-center border-t border-dashed border-border px-4 py-8 text-center text-[12px] text-muted-foreground">
              Select a person to inspect seats
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
