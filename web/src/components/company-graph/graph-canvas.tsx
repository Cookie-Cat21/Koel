"use client";

import {
  forceCollide,
  forceManyBody,
  forceSimulation,
  type SimulationNodeDatum,
} from "d3-force";
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
import { useEffect, useMemo } from "react";

import type { GraphEdge, GraphNode } from "@/lib/api/graph";
import { formatCompactNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const RELATION_STROKE: Record<string, string> = {
  subsidiary: "var(--chart-1)",
  associate: "var(--chart-2)",
  joint_venture: "var(--chart-3)",
  related_party: "var(--chart-4)",
  group_mention: "var(--chart-5)",
};

const RELATION_SHORT: Record<string, string> = {
  subsidiary: "sub",
  associate: "assoc",
  joint_venture: "JV",
  related_party: "RP",
  group_mention: "grp",
};

const CX = 480;
const CY = 320;

type CompanyNodeData = {
  label: string;
  subtitle: string;
  size: number;
  selected: boolean;
  dimmed: boolean;
  listed: boolean;
};

type SimNode = SimulationNodeDatum & {
  id: string;
  size: number;
};

function companySize(node: GraphNode): number {
  const raw = node.market_cap ?? scaleEquity(node) ?? 1e9;
  const log = Math.log10(Math.max(raw, 1e6));
  return Math.max(40, Math.min(78, 22 + (log - 6) * 9));
}

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

function shortLabel(node: GraphNode): string {
  return (
    node.symbol?.replace(/\.N0000$|\.X0000$/i, "") ?? node.name.slice(0, 10)
  );
}

function CompanyNode({ data }: NodeProps<Node<CompanyNodeData>>) {
  const size = data.selected ? data.size + 12 : data.size;
  return (
    <div
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-full border bg-card px-2 text-center shadow-sm transition-[transform,opacity,border-color,box-shadow] duration-150 motion-safe:hover:scale-[1.04]",
        data.listed
          ? "border-border"
          : "border-dashed border-muted-foreground/40",
        data.selected &&
          "z-10 border-foreground shadow-[0_0_0_2px_var(--background),0_0_0_3px_var(--ring)]",
        data.dimmed && "opacity-25",
      )}
      style={{ width: size, height: size, minWidth: size }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-1.5 !bg-border"
      />
      <span className="max-w-[5rem] truncate text-[11px] font-semibold leading-tight text-foreground">
        {data.label}
      </span>
      {data.subtitle ? (
        <span className="max-w-[5rem] truncate text-[9px] text-muted-foreground">
          {data.subtitle}
        </span>
      ) : null}
      <Handle
        type="source"
        position={Position.Right}
        className="!size-1.5 !bg-border"
      />
    </div>
  );
}

const nodeTypes = { company: CompanyNode };

function adjacency(edges: GraphEdge[]): Map<number, number[]> {
  const adj = new Map<number, number[]>();
  const add = (a: number, b: number) => {
    const list = adj.get(a);
    if (list) {
      if (!list.includes(b)) list.push(b);
    } else adj.set(a, [b]);
  };
  for (const e of edges) {
    add(e.src_node_id, e.dst_node_id);
    add(e.dst_node_id, e.src_node_id);
  }
  return adj;
}

/**
 * Focused view = hub + 1-hop (readable ownership star).
 * Overview (nothing selected) = full graph, no hub pinned.
 */
function selectDisplayGraph(
  graphNodes: GraphNode[],
  edges: GraphEdge[],
  selectedId: number | null,
): { nodes: GraphNode[]; edges: GraphEdge[]; hubId: number | null } {
  const byId = new Map(graphNodes.map((n) => [n.id, n]));

  if (selectedId != null && byId.has(selectedId)) {
    const ids = new Set<number>([selectedId]);
    for (const e of edges) {
      if (e.src_node_id === selectedId) ids.add(e.dst_node_id);
      if (e.dst_node_id === selectedId) ids.add(e.src_node_id);
    }
    const nodes = [...ids]
      .map((id) => byId.get(id))
      .filter((n): n is GraphNode => Boolean(n));
    const subEdges = edges.filter(
      (e) => ids.has(e.src_node_id) && ids.has(e.dst_node_id),
    );
    return { nodes, edges: subEdges, hubId: selectedId };
  }

  // Nothing selected — show every company/link passed in.
  return { nodes: graphNodes, edges, hubId: null };
}

/**
 * Hub at center, neighbors on a wide ring with d3-force collide/charge polish.
 * Obsidian-like repulsion without collapsing into a hairball.
 */
function layoutOwnership(
  graphNodes: GraphNode[],
  edges: GraphEdge[],
  hubId: number | null,
  selectedId: number | null,
): Node<CompanyNodeData>[] {
  const n = graphNodes.length;
  if (n === 0) return [];

  const adj = adjacency(edges);
  const neighbors =
    hubId != null ? new Set(adj.get(hubId) ?? []) : new Set<number>();

  const hubNode = hubId != null ? graphNodes.find((x) => x.id === hubId) : null;
  const ringNodes = graphNodes
    .filter((x) => x.id !== hubId)
    .sort((a, b) => shortLabel(a).localeCompare(shortLabel(b)));

  // Focused: wide ring around hub. Overview: larger cloud so all firms fit.
  const radius = Math.max(
    hubId != null ? 210 : 280,
    (ringNodes.length * (hubId != null ? 88 : 64)) / (2 * Math.PI),
  );

  const seeded: SimNode[] = [];
  if (hubNode) {
    seeded.push({
      id: String(hubNode.id),
      size: companySize(hubNode),
      x: CX,
      y: CY,
      fx: CX,
      fy: CY,
    });
  }

  ringNodes.forEach((node, i) => {
    const angle =
      (2 * Math.PI * i) / Math.max(ringNodes.length, 1) - Math.PI / 2;
    // Overview: spiral bands so a full map isn't one overcrowded ring.
    const band = hubId == null ? Math.floor(i / Math.max(12, Math.ceil(ringNodes.length / 4))) : i % 3;
    const r = radius + band * (hubId != null ? 12 : 70) + (i % 5) * 6;
    const size = companySize(node);
    seeded.push({
      id: String(node.id),
      size,
      x: CX + r * Math.cos(angle),
      y: CY + r * Math.sin(angle),
      fx: null,
      fy: null,
    });
  });

  const charge = -Math.min(
    hubId != null ? 700 : 1100,
    Math.max(280, 200 + n * (hubId != null ? 8 : 5)),
  );
  const sim = forceSimulation(seeded)
    .force(
      "charge",
      forceManyBody().strength(charge).distanceMin(40).distanceMax(900),
    )
    .force(
      "collide",
      forceCollide<SimNode>()
        .radius((d) => d.size / 2 + (hubId != null ? 18 : 14))
        .strength(1)
        .iterations(3),
    )
    .stop();

  for (let i = 0; i < (hubId != null ? 180 : 220); i++) sim.tick();

  const byId = new Map(seeded.map((s) => [s.id, s]));
  const focusNeighbors =
    selectedId != null
      ? new Set<number>([
          selectedId,
          ...(adj.get(selectedId) ?? []),
        ])
      : null;

  return graphNodes.map((node) => {
    const s = byId.get(String(node.id));
    const size = companySize(node);
    const worth = node.market_cap ?? scaleEquity(node);
    const isFocus = selectedId != null && node.id === selectedId;
    const x = s?.x ?? CX;
    const y = s?.y ?? CY;
    return {
      id: String(node.id),
      type: "company" as const,
      position: { x: x - size / 2, y: y - size / 2 },
      zIndex: isFocus ? 10 : neighbors.has(node.id) ? 2 : 1,
      data: {
        label: shortLabel(node),
        subtitle: worth != null ? formatCompactNumber(worth, 1) : "",
        size,
        selected: isFocus,
        dimmed: focusNeighbors != null && !focusNeighbors.has(node.id),
        listed: node.node_kind === "listed",
      },
    };
  });
}

function edgeLabel(e: GraphEdge): string {
  if (e.ownership_pct != null && Number.isFinite(e.ownership_pct)) {
    return `${Math.round(e.ownership_pct)}%`;
  }
  return RELATION_SHORT[e.relation] ?? e.relation.replace("_", " ");
}

function toFlowEdges(
  edges: GraphEdge[],
  selectedId: number | null,
): Edge[] {
  return edges.map((e) => {
    const incident =
      selectedId == null ||
      e.src_node_id === selectedId ||
      e.dst_node_id === selectedId;
    // In ego view every edge is incident; still keep labels short.
    const showLabel = selectedId != null && incident;
    const muted = selectedId != null && !incident;
    const stroke = muted
      ? "var(--border)"
      : (RELATION_STROKE[e.relation] ?? "var(--border)");
    const baseWidth =
      e.confidence === "high" ? 2.4 : e.confidence === "medium" ? 1.7 : 1.1;
    return {
      id: `e-${e.id}`,
      source: String(e.src_node_id),
      target: String(e.dst_node_id),
      label: showLabel ? edgeLabel(e) : undefined,
      style: {
        stroke,
        strokeWidth: muted ? 1 : baseWidth,
        opacity: muted ? 0.15 : 0.9,
      },
      markerEnd: muted
        ? undefined
        : {
            type: MarkerType.ArrowClosed,
            width: 12,
            height: 12,
            color: stroke,
          },
      labelStyle: { fontSize: 10, fill: "var(--foreground)" },
      labelBgStyle: { fill: "var(--background)", fillOpacity: 0.94 },
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 3,
    };
  });
}

function GraphInner({
  nodes: graphNodes,
  edges: graphEdges,
  selectedId,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const { fitView } = useReactFlow();

  const display = useMemo(
    () => selectDisplayGraph(graphNodes, graphEdges, selectedId),
    [graphNodes, graphEdges, selectedId],
  );

  const laidOut = useMemo(
    () =>
      layoutOwnership(
        display.nodes,
        display.edges,
        display.hubId,
        selectedId,
      ),
    [display, selectedId],
  );
  const flowEdges = useMemo(
    () => toFlowEdges(display.edges, selectedId),
    [display.edges, selectedId],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(laidOut);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setNodes(laidOut);
    setEdges(flowEdges);
    const id = requestAnimationFrame(() => {
      fitView({ padding: 0.28, duration: 220, maxZoom: 1.15 });
    });
    return () => cancelAnimationFrame(id);
  }, [laidOut, flowEdges, setNodes, setEdges, fitView]);

  return (
    <div className="h-[min(62vh,520px)] w-full overflow-hidden rounded-xl border border-border bg-[radial-gradient(ellipse_at_50%_40%,color-mix(in_oklab,var(--muted)_35%,transparent),transparent_65%)] sm:h-[min(70vh,560px)]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.28, maxZoom: 1.15 }}
        minZoom={0.15}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
        panOnScroll
        onNodeClick={(_, node) => {
          const id = Number(node.id);
          onSelect(Number.isFinite(id) ? id : null);
        }}
        onPaneClick={() => onSelect(null)}
      >
        <Background gap={22} size={1} color="var(--border)" />
        <Controls
          showInteractive={false}
          className="!border-border !shadow-none"
        />
      </ReactFlow>
    </div>
  );
}

export function CompanyGraphCanvas(props: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}) {
  return (
    <ReactFlowProvider>
      <GraphInner {...props} />
    </ReactFlowProvider>
  );
}
