"use client";

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

type CompanyNodeData = {
  label: string;
  subtitle: string;
  size: number;
  selected: boolean;
  listed: boolean;
};

function companySize(node: GraphNode): number {
  const raw = node.market_cap ?? scaleEquity(node) ?? 1e9;
  const log = Math.log10(Math.max(raw, 1e6));
  // ~1e9 → ~36px, ~1e12 → ~64px
  return Math.max(36, Math.min(72, 20 + (log - 6) * 8));
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

function CompanyNode({ data }: NodeProps<Node<CompanyNodeData>>) {
  const size = data.size;
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-full border bg-card px-2 text-center shadow-sm",
        data.listed ? "border-border" : "border-dashed border-muted-foreground/40",
        data.selected && "ring-2 ring-ring",
      )}
      style={{ width: size, height: size, minWidth: size }}
    >
      <Handle type="target" position={Position.Left} className="!bg-border !size-1.5" />
      <span className="max-w-[4.5rem] truncate text-[10px] font-semibold leading-tight text-foreground">
        {data.label}
      </span>
      {data.subtitle ? (
        <span className="max-w-[4.5rem] truncate text-[9px] text-muted-foreground">
          {data.subtitle}
        </span>
      ) : null}
      <Handle type="source" position={Position.Right} className="!bg-border !size-1.5" />
    </div>
  );
}

const nodeTypes = { company: CompanyNode };

function layoutNodes(
  graphNodes: GraphNode[],
  focusId: number | null,
): Node<CompanyNodeData>[] {
  const n = graphNodes.length;
  if (n === 0) return [];
  const cx = 420;
  const cy = 280;
  const radius = Math.min(240, 80 + n * 14);

  return graphNodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    const isFocus = focusId != null && node.id === focusId;
    const r = isFocus ? 0 : radius;
    const size = companySize(node);
    const label = node.symbol?.replace(/\.N0000$|\.X0000$/i, "") ?? node.name.slice(0, 10);
    const worth = node.market_cap ?? scaleEquity(node);
    return {
      id: String(node.id),
      type: "company",
      position: {
        x: cx + r * Math.cos(angle) - size / 2,
        y: cy + r * Math.sin(angle) - size / 2,
      },
      data: {
        label,
        subtitle: worth != null ? formatCompactNumber(worth, 1) : "",
        size,
        selected: isFocus,
        listed: node.node_kind === "listed",
      },
    };
  });
}

function toFlowEdges(edges: GraphEdge[]): Edge[] {
  return edges.map((e) => ({
    id: `e-${e.id}`,
    source: String(e.src_node_id),
    target: String(e.dst_node_id),
    label: e.relation.replace("_", " "),
    style: {
      stroke: RELATION_STROKE[e.relation] ?? "var(--border)",
      strokeWidth: e.confidence === "high" ? 2.2 : e.confidence === "medium" ? 1.6 : 1,
      opacity: e.confidence === "low" ? 0.45 : 0.85,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 14,
      height: 14,
      color: RELATION_STROKE[e.relation] ?? "var(--border)",
    },
    labelStyle: { fontSize: 9, fill: "var(--muted-foreground)" },
    labelBgStyle: { fill: "var(--background)", fillOpacity: 0.85 },
  }));
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
  const initialNodes = useMemo(
    () => layoutNodes(graphNodes, selectedId),
    [graphNodes, selectedId],
  );
  const initialEdges = useMemo(() => toFlowEdges(graphEdges), [graphEdges]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(layoutNodes(graphNodes, selectedId));
    setEdges(toFlowEdges(graphEdges));
  }, [graphNodes, graphEdges, selectedId, setNodes, setEdges]);

  return (
    <div className="h-[min(70vh,560px)] w-full overflow-hidden rounded-xl border border-border bg-background/60">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.35}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => {
          const id = Number(node.id);
          onSelect(Number.isFinite(id) ? id : null);
        }}
        onPaneClick={() => onSelect(null)}
      >
        <Background gap={22} size={1} color="var(--border)" />
        <Controls showInteractive={false} className="!shadow-none !border-border" />
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
