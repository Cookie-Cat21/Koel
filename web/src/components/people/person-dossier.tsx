"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useState,
  useTransition,
  type KeyboardEvent,
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
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { ChangeBadge } from "@/components/kit/change-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { PersonDossier } from "@/lib/api/person-dossier";
import { ROLE_WEIGHT, type PersonRole } from "@/lib/api/people-graph";
import { formatCompactNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Person dossier UI — 10 agentic loops (Tremor KPI / HyperUI table+timeline /
 * bar-list ranking; Chime tokens; no purple/glow kits):
 *  1 Identity hero + monogram
 *  2 Tremor-style KPI strip
 *  3 Sticky underline tabs + keyboard
 *  4 HyperUI seats ledger
 *  5 Per-seat influence bar-list
 *  6 Ego network (person → issuers → peers)
 *  7 Co-director bar-list
 *  8 Across-years honest timeline
 *  9 Motion / tab transitions
 * 10 Empty states, soft-merge callout, mobile density
 */

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

type TabId = "seats" | "network" | "timeline";

function ticker(symbol: string): string {
  return symbol.replace(/\.(N|X)0000$/i, "");
}

function rolesSummary(roles: PersonRole[]): string {
  if (roles.length === 0) return "—";
  const sorted = [...roles].sort(
    (a, b) => (ROLE_WEIGHT[b] ?? 0) - (ROLE_WEIGHT[a] ?? 0),
  );
  if (sorted.length === 1) return ROLE_LABEL[sorted[0]] ?? sorted[0];
  if (sorted.length === 2) {
    return `${ROLE_LABEL[sorted[0]]}; ${ROLE_LABEL[sorted[1]]}`;
  }
  return `${ROLE_LABEL[sorted[0]]} +${sorted.length - 1}`;
}

function initials(name: string): string {
  const parts = name.replace(/\./g, " ").split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[parts.length - 1][0] ?? ""}`.toUpperCase();
}

function topSector(dossier: PersonDossier): string | null {
  const counts = new Map<string, number>();
  for (const s of dossier.seats) {
    if (!s.sector) continue;
    counts.set(s.sector, (counts.get(s.sector) ?? 0) + 1);
  }
  let best: string | null = null;
  let n = 0;
  for (const [sector, c] of counts) {
    if (c > n) {
      n = c;
      best = sector;
    }
  }
  return best;
}

type EgoData = {
  label: string;
  sub: string;
  kind: "self" | "company" | "peer";
};

function EgoNode({ data }: NodeProps<Node<EgoData>>) {
  return (
    <div
      className={cn(
        "flex min-h-10 min-w-[100px] max-w-[148px] flex-col justify-center rounded-md border px-2.5 py-1.5 text-center motion-safe:transition-transform motion-safe:duration-150 motion-safe:hover:scale-[1.03]",
        data.kind === "self" && "border-foreground/45 bg-background shadow-sm",
        data.kind === "company" && "border-border bg-muted/35",
        data.kind === "peer" && "border-border bg-background",
      )}
    >
      {data.kind !== "self" ? (
        <Handle
          type="target"
          position={Position.Left}
          className="!size-1.5 !bg-border"
        />
      ) : null}
      {data.kind !== "peer" ? (
        <Handle
          type="source"
          position={Position.Right}
          className="!size-1.5 !bg-border"
        />
      ) : null}
      <span className="truncate text-[11px] font-semibold leading-tight">
        {data.label}
      </span>
      {data.sub ? (
        <span className="truncate font-mono text-[10px] text-muted-foreground">
          {data.sub}
        </span>
      ) : null}
    </div>
  );
}

const egoTypes = { ego: EgoNode };

function EgoNetwork({ dossier }: { dossier: PersonDossier }) {
  const router = useRouter();
  const { nodes, edges } = useMemo(() => {
    const companies = dossier.seats.slice(0, 8);
    const peers = dossier.network.slice(0, 10);
    const midY = Math.max(40, (Math.max(companies.length, peers.length) - 1) * 23);
    const ns: Node[] = [
      {
        id: "self",
        type: "ego",
        position: { x: 12, y: midY },
        data: {
          label: dossier.name,
          sub: formatCompactNumber(dossier.influence_score, 1),
          kind: "self",
        },
      },
    ];
    companies.forEach((s, i) => {
      ns.push({
        id: `c-${s.symbol}`,
        type: "ego",
        position: { x: 210, y: 8 + i * 46 },
        data: {
          label: ticker(s.symbol),
          sub: formatCompactNumber(s.market_cap, 1),
          kind: "company",
        },
      });
    });
    peers.forEach((p, i) => {
      ns.push({
        id: `p-${p.id}`,
        type: "ego",
        position: { x: 400, y: 8 + i * 46 },
        data: {
          label: p.name,
          sub: `${p.shared_count} shared`,
          kind: "peer",
        },
      });
    });

    const es: Edge[] = [];
    for (const s of companies) {
      es.push({
        id: `e-self-${s.symbol}`,
        source: "self",
        target: `c-${s.symbol}`,
        type: "smoothstep",
        style: { stroke: "var(--chart-1)", strokeWidth: 1.5, opacity: 0.75 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 10,
          height: 10,
          color: "var(--chart-1)",
        },
      });
    }
    for (const p of peers) {
      const first = p.shared_symbols.find((sym) =>
        companies.some((c) => c.symbol === sym),
      );
      if (!first) continue;
      es.push({
        id: `e-${first}-${p.id}`,
        source: `c-${first}`,
        target: `p-${p.id}`,
        type: "smoothstep",
        style: { stroke: "var(--border)", strokeWidth: 1, opacity: 0.55 },
      });
    }
    return { nodes: ns, edges: es };
  }, [dossier]);

  if (dossier.seats.length === 0) {
    return (
      <div className="flex h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-border px-4 text-center">
        <p className="text-sm font-medium text-foreground">
          No board seats to map
        </p>
        <p className="mt-1 max-w-sm text-[12px] text-muted-foreground">
          Sync directors-backfill against CSE companyProfile to populate seats.
        </p>
      </div>
    );
  }

  return (
    <div className="h-[min(50vh,380px)] overflow-hidden rounded-xl border border-border bg-[radial-gradient(ellipse_at_20%_20%,color-mix(in_oklab,var(--muted)_55%,transparent),transparent_55%)]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={egoTypes}
        fitView
        fitViewOptions={{ padding: 0.22 }}
        minZoom={0.35}
        maxZoom={1.4}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
        panOnScroll
        onNodeClick={(_, node) => {
          if (node.id.startsWith("p-")) {
            router.push(`/people/${node.id.slice(2)}`);
          } else if (node.id.startsWith("c-")) {
            router.push(`/symbols/${encodeURIComponent(node.id.slice(2))}`);
          }
        }}
      >
        <Background gap={18} size={1} color="var(--border)" />
        <Controls
          showInteractive={false}
          position="bottom-left"
          className="!scale-110"
        />
      </ReactFlow>
    </div>
  );
}

function KpiCell({
  label,
  value,
  title,
}: {
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div className="rounded-md bg-muted/35 px-3 py-2">
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd
        className="truncate font-mono text-lg font-semibold tabular-nums"
        title={title}
      >
        {value}
      </dd>
    </div>
  );
}

export function PersonDossierView({ dossier }: { dossier: PersonDossier }) {
  const [tab, setTab] = useState<TabId>("seats");
  const [, startTransition] = useTransition();
  const baseId = useId();
  const sector = topSector(dossier);
  const topPeers = dossier.network.slice(0, 14);
  const seatSectors = useMemo(
    () =>
      Array.from(
        new Set(
          dossier.seats
            .map((s) => s.sector)
            .filter((s): s is string => Boolean(s)),
        ),
      ).slice(0, 6),
    [dossier.seats],
  );
  const tabs: Array<{ id: TabId; label: string; count?: number }> = [
    { id: "seats", label: "Seats", count: dossier.seats.length },
    { id: "network", label: "Network", count: dossier.network.length },
    {
      id: "timeline",
      label: "Across years",
      count: dossier.timeline.length || undefined,
    },
  ];

  const selectTab = useCallback(
    (id: TabId) => {
      startTransition(() => setTab(id));
    },
    [startTransition],
  );

  const onTabKeyDown = useCallback(
    (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft" && e.key !== "Home" && e.key !== "End") {
        return;
      }
      e.preventDefault();
      let next = index;
      if (e.key === "ArrowRight") next = (index + 1) % tabs.length;
      if (e.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      if (e.key === "Home") next = 0;
      if (e.key === "End") next = tabs.length - 1;
      selectTab(tabs[next].id);
      const el = document.getElementById(`${baseId}-tab-${tabs[next].id}`);
      el?.focus();
    },
    [baseId, selectTab, tabs],
  );

  // Loop 9: prefer deep-link tab from hash when present
  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (hash === "seats" || hash === "network" || hash === "timeline") {
      setTab(hash);
    }
  }, []);

  return (
    <div className="space-y-5">
      {/* Loop 1–2: identity hero + KPI strip */}
      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <div
          aria-hidden
          className="pointer-events-none h-16 border-b border-border/60 bg-[radial-gradient(420px_circle_at_10%_30%,color-mix(in_oklab,var(--muted)_90%,transparent),transparent_60%)]"
        />
        <div className="-mt-8 px-5 pb-6 sm:px-7 sm:pb-7">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex min-w-0 items-end gap-3.5">
              <div className="flex size-14 shrink-0 items-center justify-center rounded-xl border border-border bg-background font-mono text-sm font-semibold shadow-sm">
                {initials(dossier.name)}
              </div>
              <div className="min-w-0 space-y-1 pb-0.5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Chime · Director dossier
                </p>
                <h1 className="truncate font-display text-2xl font-semibold tracking-tight sm:text-3xl">
                  {dossier.name}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {dossier.top_role
                    ? ROLE_LABEL[dossier.top_role]
                    : "Director"}{" "}
                  · CSE initials as listed
                  {sector ? ` · ${sector}` : ""}
                </p>
              </div>
            </div>
            <div className="shrink-0 rounded-lg border border-border bg-background px-4 py-3.5 sm:min-w-[10.5rem] sm:text-right">
              <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                Linked influence
              </p>
              <p className="mt-1 font-mono text-2xl font-semibold tabular-nums leading-none">
                {formatCompactNumber(dossier.influence_score, 1)}
              </p>
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                LKR · not personal net worth
              </p>
            </div>
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-2.5 border-t border-border pt-5 sm:grid-cols-4">
            <KpiCell label="Companies" value={String(dossier.company_count)} />
            <KpiCell
              label="Linked volume"
              value={formatCompactNumber(dossier.linked_volume, 1)}
              title="Sum of latest share volume on seated issuers"
            />
            <KpiCell
              label="Linked turnover"
              value={formatCompactNumber(dossier.linked_turnover, 1)}
              title="Sum of latest turnover (LKR) on seated issuers"
            />
            <KpiCell
              label="Co-directors"
              value={String(dossier.network.length)}
            />
          </dl>

          {seatSectors.length > 0 ? (
            <ul className="mt-3 flex flex-wrap gap-1.5">
              {seatSectors.map((s) => (
                <li
                  key={s}
                  className="rounded border border-border/70 bg-muted/20 px-2 py-0.5 text-[11px] text-muted-foreground"
                >
                  {s}
                </li>
              ))}
            </ul>
          ) : null}

          {/* Loop 10: soft-merge callout */}
          {dossier.merged_ids.length > 1 ? (
            <p className="mt-3 rounded-md border border-border/70 bg-muted/25 px-3 py-2 text-[12px] text-muted-foreground">
              Soft-merged {dossier.merged_ids.length} CSE name variants (initial
              spelling). Display stays the primary CSE string.
            </p>
          ) : null}
        </div>
      </section>

      {/* Loop 3: sticky accessible tabs */}
      <div className="sticky top-[3.25rem] z-20 -mx-1 border-b border-border bg-background/95 px-1 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex flex-wrap items-center gap-1">
          <div
            role="tablist"
            aria-label="Dossier sections"
            className="flex flex-wrap gap-0.5"
          >
            {tabs.map((t, i) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                aria-controls={`${baseId}-panel-${t.id}`}
                id={`${baseId}-tab-${t.id}`}
                tabIndex={tab === t.id ? 0 : -1}
                onClick={() => {
                  selectTab(t.id);
                  window.history.replaceState(null, "", `#${t.id}`);
                }}
                onKeyDown={(e) => onTabKeyDown(e, i)}
                className={cn(
                  "relative rounded-t-md px-3.5 py-2.5 text-sm transition-colors",
                  tab === t.id
                    ? "bg-muted/45 font-semibold text-foreground"
                    : "text-muted-foreground hover:bg-muted/25 hover:text-foreground",
                )}
              >
                {t.label}
                {typeof t.count === "number" ? (
                  <span className="ml-1.5 font-mono text-[11px] tabular-nums text-muted-foreground">
                    {t.count}
                  </span>
                ) : null}
                {tab === t.id ? (
                  <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-foreground" />
                ) : null}
              </button>
            ))}
          </div>
          <div className="ml-auto flex gap-2 py-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/people">All people</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/graph">Ownership</Link>
            </Button>
          </div>
        </div>
      </div>

      {/* Loop 4–5: seats ledger + influence bars */}
      {tab === "seats" ? (
        <section
          role="tabpanel"
          id={`${baseId}-panel-seats`}
          aria-labelledby={`${baseId}-tab-seats`}
          className="space-y-3 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
        >
          <div>
            <h2 className="font-display text-lg font-semibold">Board seats</h2>
            <p className="text-[12px] text-muted-foreground">
              Official CSE companyProfile · latest quote volume on each seat
              (company figures, not personal)
            </p>
          </div>

          <div className="overflow-hidden rounded-xl border border-border">
            <div className="hidden grid-cols-[4.5rem_minmax(0,1.3fr)_4.5rem_4rem_4.5rem_4.5rem_4rem] gap-x-2 border-b border-border bg-muted/30 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground xl:grid">
              <span>Ticker</span>
              <span>Roles</span>
              <span className="text-right">Price</span>
              <span className="text-right">Chg</span>
              <span className="text-right">Vol</span>
              <span className="text-right">Mcap</span>
              <span className="text-right">Turn</span>
            </div>
            {dossier.seats.length === 0 ? (
              <div className="px-4 py-10 text-center">
                <p className="text-sm font-medium">No active seats</p>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  This person has no active CSE board roles in the current
                  snapshot.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-border/70">
                {dossier.seats.map((seat, i) => (
                  <li
                    key={seat.symbol}
                    className="grid grid-cols-1 gap-2 px-4 py-3 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:fill-mode-both motion-safe:duration-300 hover:bg-muted/35 sm:grid-cols-[4.5rem_minmax(0,1fr)_auto] sm:items-center sm:gap-x-3 sm:py-2.5 xl:grid-cols-[4.5rem_minmax(0,1.3fr)_4.5rem_5rem_4.5rem_4.5rem_4rem]"
                    style={{ animationDelay: `${Math.min(i, 10) * 35}ms` }}
                  >
                    <Link
                      href={`/symbols/${encodeURIComponent(seat.symbol)}`}
                      className="font-mono text-[13px] font-semibold underline-offset-2 hover:underline"
                    >
                      {ticker(seat.symbol)}
                    </Link>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-1">
                        {[...seat.roles]
                          .sort(
                            (a, b) =>
                              (ROLE_WEIGHT[b] ?? 0) - (ROLE_WEIGHT[a] ?? 0),
                          )
                          .slice(0, 3)
                          .map((r) => (
                            <Badge
                              key={r}
                              variant="outline"
                              className="px-1.5 py-0 text-[10px] font-normal"
                            >
                              {ROLE_LABEL[r] ?? r}
                            </Badge>
                          ))}
                        {seat.roles.length > 3 ? (
                          <span className="text-[10px] text-muted-foreground">
                            +{seat.roles.length - 3}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                        {seat.company_name ?? "—"}
                        {seat.sector ? ` · ${seat.sector}` : ""}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] xl:hidden">
                        <span className="font-mono tabular-nums text-muted-foreground">
                          {seat.price != null
                            ? formatCompactNumber(seat.price, 2)
                            : "—"}
                        </span>
                        <ChangeBadge
                          changePct={seat.change_pct}
                          className="h-5 px-1.5"
                        />
                        <span className="font-mono tabular-nums text-muted-foreground">
                          vol {formatCompactNumber(seat.volume, 1)}
                        </span>
                        <span className="font-mono tabular-nums text-muted-foreground">
                          to {formatCompactNumber(seat.turnover, 1)}
                        </span>
                      </div>
                      <div className="mt-1 h-1 max-w-[14rem] overflow-hidden rounded-sm bg-muted">
                        <div
                          className="h-full rounded-sm bg-foreground/65 transition-[width] duration-500"
                          style={{
                            width: `${Math.max(seat.influence_share * 100, 2)}%`,
                          }}
                        />
                      </div>
                    </div>
                    <span className="hidden font-mono text-[12px] tabular-nums text-muted-foreground xl:block xl:text-right">
                      {seat.price != null
                        ? formatCompactNumber(seat.price, 2)
                        : "—"}
                    </span>
                    <span className="hidden justify-end xl:flex">
                      <ChangeBadge
                        changePct={seat.change_pct}
                        className="h-5 px-1.5"
                      />
                    </span>
                    <span className="hidden font-mono text-[12px] tabular-nums text-foreground xl:block xl:text-right">
                      {formatCompactNumber(seat.volume, 1)}
                    </span>
                    <span className="hidden font-mono text-[12px] tabular-nums text-muted-foreground xl:block xl:text-right">
                      {formatCompactNumber(seat.market_cap, 1)}
                    </span>
                    <span className="hidden font-mono text-[12px] tabular-nums text-muted-foreground xl:block xl:text-right">
                      {formatCompactNumber(seat.turnover, 1)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      ) : null}

      {/* Loop 6–7: network graph + peer bar-list */}
      {tab === "network" ? (
        <section
          role="tabpanel"
          id={`${baseId}-panel-network`}
          aria-labelledby={`${baseId}-tab-network`}
          className="space-y-4 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
        >
          <div>
            <h2 className="font-display text-lg font-semibold">
              Board network
            </h2>
            <p className="text-[12px] text-muted-foreground">
              Person → companies → co-directors. Click a node to open it.
            </p>
          </div>

          <ReactFlowProvider>
            <EgoNetwork dossier={dossier} />
          </ReactFlowProvider>

          <div className="overflow-hidden rounded-xl border border-border">
            <div className="grid grid-cols-[minmax(0,1fr)_3.5rem_5rem] gap-x-3 border-b border-border bg-muted/30 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              <span>Co-director</span>
              <span className="text-right">Shared</span>
              <span className="text-right">Influence</span>
            </div>
            {topPeers.length === 0 ? (
              <div className="px-4 py-10 text-center">
                <p className="text-sm font-medium">No co-directors yet</p>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  Sync more issuers with directors-backfill to densify the
                  network.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-border/70">
                {topPeers.map((p, i) => {
                  const maxShared = topPeers[0]?.shared_count || 1;
                  const pct = (p.shared_count / maxShared) * 100;
                  return (
                    <li
                      key={p.id}
                      style={{ animationDelay: `${Math.min(i, 10) * 30}ms` }}
                      className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:fill-mode-both motion-safe:duration-300"
                    >
                      <Link
                        href={`/people/${p.id}`}
                        title={p.shared_symbols.map(ticker).join(", ")}
                        className="grid grid-cols-[minmax(0,1fr)_3.5rem_5rem] items-center gap-x-3 px-4 py-2.5 transition-colors hover:bg-muted/40"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-[13px] font-medium">
                            {p.name}
                          </span>
                          <span
                            className="mt-0.5 block truncate text-[11px] text-muted-foreground"
                            title={p.shared_symbols.map(ticker).join(", ")}
                          >
                            {p.top_role
                              ? ROLE_LABEL[p.top_role]
                              : "Director"}{" "}
                            ·{" "}
                            {p.shared_symbols
                              .slice(0, 5)
                              .map(ticker)
                              .join(", ")}
                            {p.shared_symbols.length > 5 ? "…" : ""}
                          </span>
                          <span className="mt-1 block h-1 max-w-[12rem] overflow-hidden rounded-sm bg-muted">
                            <span
                              className="block h-full rounded-sm bg-foreground/60"
                              style={{ width: `${Math.max(pct, 8)}%` }}
                            />
                          </span>
                        </span>
                        <span className="text-right font-mono text-[12px] tabular-nums">
                          {p.shared_count}
                        </span>
                        <span className="text-right font-mono text-[12px] tabular-nums text-muted-foreground">
                          {formatCompactNumber(p.influence_score, 1)}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>
      ) : null}

      {/* Across years: live seats + issuer filings / board events from DB */}
      {tab === "timeline" ? (
        <section
          role="tabpanel"
          id={`${baseId}-panel-timeline`}
          aria-labelledby={`${baseId}-tab-timeline`}
          className="space-y-3 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
        >
          <div>
            <h2 className="font-display text-lg font-semibold">Across years</h2>
            <p className="text-[12px] text-muted-foreground">
              CSE boards are live-only. Below: today&apos;s seats, then filings
              on those issuers (appointments when polled; annuals already in DB).
            </p>
          </div>

          <ol className="relative space-y-3 border-l border-border pl-4">
            <li className="relative">
              <span
                aria-hidden
                className="absolute -left-[1.3rem] top-1.5 size-2.5 rounded-full border-2 border-foreground bg-background"
              />
              <div className="rounded-lg border border-border bg-background px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    Current observation
                  </p>
                  <Badge variant="outline">Live CSE</Badge>
                </div>
                <p className="mt-1 text-sm">
                  {dossier.company_count} active seat
                  {dossier.company_count === 1 ? "" : "s"}
                  {sector ? ` · densest in ${sector}` : ""}
                </p>
                <ul className="mt-3 divide-y divide-border/60 rounded-md border border-border/70">
                  {dossier.seats.map((s) => (
                    <li
                      key={`${s.symbol}-${s.roles.join("-")}`}
                      className="flex items-center justify-between gap-3 px-3 py-2 text-[12px]"
                    >
                      <Link
                        href={`/symbols/${encodeURIComponent(s.symbol)}`}
                        className="font-mono font-semibold underline-offset-2 hover:underline"
                      >
                        {ticker(s.symbol)}
                      </Link>
                      <span className="min-w-0 truncate text-muted-foreground">
                        {rolesSummary(s.roles)}
                      </span>
                      <span className="shrink-0 font-mono tabular-nums text-muted-foreground">
                        {(s.influence_share * 100).toFixed(0)}%
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </li>

            {dossier.timeline.length === 0 ? (
              <li className="relative">
                <span
                  aria-hidden
                  className="absolute -left-[1.3rem] top-1.5 size-2.5 rounded-full border border-dashed border-muted-foreground/40 bg-background"
                />
                <div className="rounded-lg border border-dashed border-border/80 px-4 py-3">
                  <p className="text-[12px] text-muted-foreground">
                    No issuer filings on file for these seats yet. Poller stores
                    annuals/appointment categories as they arrive.
                  </p>
                </div>
              </li>
            ) : (
              dossier.timeline.map((ev) => {
                const day = ev.at.slice(0, 10);
                const href = ev.url
                  ? ev.url
                  : `/symbols/${encodeURIComponent(ev.symbol)}`;
                const external = Boolean(ev.url);
                return (
                  <li key={`${ev.disclosure_id}-${ev.symbol}`} className="relative">
                    <span
                      aria-hidden
                      className={cn(
                        "absolute -left-[1.3rem] top-1.5 size-2.5 rounded-full border bg-background",
                        ev.kind === "board_event"
                          ? "border-foreground"
                          : "border-border",
                      )}
                    />
                    <div className="rounded-lg border border-border/80 bg-card/40 px-4 py-2.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                          {day}
                        </span>
                        <Badge variant="outline" className="text-[10px]">
                          {ev.kind === "board_event" ? "Board event" : "Filing"}
                        </Badge>
                        <Link
                          href={`/symbols/${encodeURIComponent(ev.symbol)}`}
                          className="font-mono text-[11px] font-semibold underline-offset-2 hover:underline"
                        >
                          {ticker(ev.symbol)}
                        </Link>
                      </div>
                      {external ? (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 block text-[13px] text-foreground underline-offset-2 hover:underline"
                        >
                          {ev.title}
                        </a>
                      ) : (
                        <Link
                          href={href}
                          className="mt-1 block text-[13px] text-foreground underline-offset-2 hover:underline"
                        >
                          {ev.title}
                        </Link>
                      )}
                      {ev.category ? (
                        <p className="mt-0.5 text-[11px] text-muted-foreground">
                          {ev.category}
                        </p>
                      ) : null}
                    </div>
                  </li>
                );
              })
            )}
          </ol>
        </section>
      ) : null}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {dossier.disclaimer}
      </p>
    </div>
  );
}
