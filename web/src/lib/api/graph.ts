import type { Pool } from "pg";

import { toFiniteNumber } from "@/lib/api/finite-number";
import {
  MAX_STOCK_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { normalizeSymbol } from "@/lib/api/symbol";

export const GRAPH_RELATIONS = [
  "subsidiary",
  "associate",
  "joint_venture",
  "related_party",
  "group_mention",
] as const;

export type GraphRelation = (typeof GRAPH_RELATIONS)[number];

export const GRAPH_CONFIDENCE = ["low", "medium", "high"] as const;
export type GraphConfidence = (typeof GRAPH_CONFIDENCE)[number];

export type GraphNode = {
  id: number;
  symbol: string | null;
  name: string;
  node_kind: "listed" | "unlisted";
  sector: string | null;
  equity: number | null;
  equity_as_of: string | null;
  equity_scale: string;
  equity_currency: string;
  equity_confidence: string;
  market_cap: number | null;
};

export type GraphEdge = {
  id: number;
  src_node_id: number;
  dst_node_id: number;
  src_symbol: string | null;
  dst_symbol: string | null;
  src_name: string;
  dst_name: string;
  relation: GraphRelation;
  ownership_pct: number | null;
  ownership_pct_confidence: string;
  confidence: GraphConfidence;
  evidence_snippet: string | null;
};

const CONF_RANK: Record<string, number> = { low: 1, medium: 2, high: 3 };

export function normalizeConfidence(raw: unknown): GraphConfidence | null {
  if (typeof raw !== "string") return null;
  const v = raw.trim().toLowerCase();
  return (GRAPH_CONFIDENCE as readonly string[]).includes(v)
    ? (v as GraphConfidence)
    : null;
}

export function normalizeRelation(raw: unknown): GraphRelation | null {
  if (typeof raw !== "string") return null;
  const v = raw.trim().toLowerCase();
  return (GRAPH_RELATIONS as readonly string[]).includes(v)
    ? (v as GraphRelation)
    : null;
}

function asIsoDate(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === "string" && value.length >= 10) {
    return value.slice(0, 10);
  }
  return null;
}

export async function queryCompanyGraph(
  pool: Pool,
  opts: {
    minConfidence?: GraphConfidence;
    limit?: number;
    focusSymbol?: string | null;
    includeIsolates?: boolean;
  } = {},
): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  const minConf = opts.minConfidence ?? "medium";
  const minRank = CONF_RANK[minConf] ?? 2;
  // Cap high enough for a full listed↔listed ownership map after densify.
  const limit = Math.min(Math.max(opts.limit ?? 80, 1), 400);
  const focus = opts.focusSymbol ? normalizeSymbol(opts.focusSymbol) : null;

  const edgeRows = await pool.query(
    `
    SELECT
      e.id,
      e.src_node_id,
      e.dst_node_id,
      e.relation,
      e.ownership_pct,
      e.ownership_pct_confidence,
      e.confidence,
      e.evidence_snippet,
      ns.symbol AS src_symbol,
      nd.symbol AS dst_symbol,
      ns.display_name AS src_name,
      nd.display_name AS dst_name
    FROM company_graph_edges e
    JOIN company_graph_nodes ns ON ns.id = e.src_node_id
    JOIN company_graph_nodes nd ON nd.id = e.dst_node_id
    WHERE e.active
      AND CASE e.confidence
            WHEN 'high' THEN 3
            WHEN 'medium' THEN 2
            ELSE 1
          END >= $1
      AND (
        $2::text IS NULL
        OR ns.symbol = $2
        OR nd.symbol = $2
      )
      AND ns.symbol IS NOT NULL
      AND nd.symbol IS NOT NULL
    ORDER BY
      CASE e.confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
      e.id DESC
    LIMIT $3
    `,
    [minRank, focus, limit * 3],
  );

  const relationRank: Record<string, number> = {
    subsidiary: 4,
    associate: 3,
    joint_venture: 3,
    related_party: 2,
    group_mention: 1,
  };
  const bestByPair = new Map<string, GraphEdge>();
  const nodeIds = new Set<number>();
  for (const row of edgeRows.rows) {
    const relation = normalizeRelation(row.relation);
    const confidence = normalizeConfidence(row.confidence);
    if (!relation || !confidence) continue;
    const srcId = Number(row.src_node_id);
    const dstId = Number(row.dst_node_id);
    if (!Number.isFinite(srcId) || !Number.isFinite(dstId)) continue;
    const edge: GraphEdge = {
      id: Number(row.id),
      src_node_id: srcId,
      dst_node_id: dstId,
      src_symbol: normalizeSymbol(row.src_symbol),
      dst_symbol: normalizeSymbol(row.dst_symbol),
      src_name:
        sanitizeDisclosureText(String(row.src_name ?? ""), MAX_STOCK_NAME_LENGTH) ||
        "—",
      dst_name:
        sanitizeDisclosureText(String(row.dst_name ?? ""), MAX_STOCK_NAME_LENGTH) ||
        "—",
      relation,
      ownership_pct: toFiniteNumber(row.ownership_pct),
      ownership_pct_confidence:
        typeof row.ownership_pct_confidence === "string"
          ? row.ownership_pct_confidence
          : "none",
      confidence,
      evidence_snippet:
        typeof row.evidence_snippet === "string"
          ? sanitizeDisclosureText(row.evidence_snippet, 280)
          : null,
    };
    // One undirected pair → keep strongest relation (subsidiary > associate > …)
    const a = Math.min(srcId, dstId);
    const b = Math.max(srcId, dstId);
    const key = `${a}:${b}`;
    const prev = bestByPair.get(key);
    if (!prev || (relationRank[relation] ?? 0) > (relationRank[prev.relation] ?? 0)) {
      bestByPair.set(key, edge);
    }
    if (bestByPair.size >= limit * 2) break;
  }
  const edges = Array.from(bestByPair.values());
  const edgeNodeIds = new Set<number>();
  for (const e of edges) {
    edgeNodeIds.add(e.src_node_id);
    edgeNodeIds.add(e.dst_node_id);
    nodeIds.add(e.src_node_id);
    nodeIds.add(e.dst_node_id);
  }

  // When isolates are requested, load the full listed universe (up to
  // ``limit``) — do not drop unlinked issuers once a few PDF edges exist.
  const wantIsolates = opts.includeIsolates || edgeNodeIds.size === 0;
  if (wantIsolates) {
    const iso = await pool.query(
      `
      SELECT n.id
      FROM company_graph_nodes n
      LEFT JOIN LATERAL (
        SELECT market_cap
        FROM price_snapshots p
        WHERE n.symbol IS NOT NULL AND p.symbol = n.symbol
          AND p.market_cap IS NOT NULL
        ORDER BY p.ts DESC
        LIMIT 1
      ) ps ON TRUE
      WHERE n.node_kind = 'listed'
        AND n.symbol IS NOT NULL
      ORDER BY
        CASE
          WHEN n.equity IS NOT NULL
           AND n.equity_confidence IN ('medium', 'high') THEN 0
          ELSE 1
        END,
        n.equity DESC NULLS LAST,
        ps.market_cap DESC NULLS LAST,
        n.symbol
      LIMIT $1
      `,
      [limit],
    );
    for (const row of iso.rows) {
      const id = Number(row.id);
      if (Number.isFinite(id)) nodeIds.add(id);
    }
  }

  if (nodeIds.size === 0) {
    return { nodes: [], edges: [] };
  }

  const isolateIds = Array.from(nodeIds).filter((id) => !edgeNodeIds.has(id));
  const isolateBudget = wantIsolates
    ? Math.max(0, limit - edgeNodeIds.size)
    : Math.max(0, Math.min(limit, limit - edgeNodeIds.size));
  const ids = [
    ...Array.from(edgeNodeIds),
    ...isolateIds.slice(0, isolateBudget),
  ];
  const nodeRows = await pool.query(
    `
    SELECT
      n.id,
      n.symbol,
      n.display_name,
      n.node_kind,
      n.equity,
      n.equity_as_of,
      n.equity_scale,
      n.equity_currency,
      n.equity_confidence,
      s.sector,
      ps.market_cap
    FROM company_graph_nodes n
    LEFT JOIN stocks s ON s.symbol = n.symbol
    LEFT JOIN LATERAL (
      SELECT market_cap
      FROM price_snapshots p
      WHERE n.symbol IS NOT NULL AND p.symbol = n.symbol
        AND p.market_cap IS NOT NULL
      ORDER BY p.ts DESC
      LIMIT 1
    ) ps ON TRUE
    WHERE n.id = ANY($1::bigint[])
    `,
    [ids],
  );

  const nodes: GraphNode[] = [];
  for (const row of nodeRows.rows) {
    const id = Number(row.id);
    if (!Number.isFinite(id)) continue;
    const kind = row.node_kind === "unlisted" ? "unlisted" : "listed";
    nodes.push({
      id,
      symbol: normalizeSymbol(row.symbol),
      name:
        sanitizeDisclosureText(String(row.display_name ?? ""), MAX_STOCK_NAME_LENGTH) ||
        "—",
      node_kind: kind,
      sector:
        typeof row.sector === "string"
          ? sanitizeDisclosureText(row.sector, 80)
          : null,
      equity: toFiniteNumber(row.equity),
      equity_as_of: asIsoDate(row.equity_as_of),
      equity_scale:
        typeof row.equity_scale === "string" ? row.equity_scale : "unknown",
      equity_currency:
        typeof row.equity_currency === "string" ? row.equity_currency : "LKR",
      equity_confidence:
        typeof row.equity_confidence === "string"
          ? row.equity_confidence
          : "none",
      market_cap: toFiniteNumber(row.market_cap),
    });
  }

  const kept = new Set(nodes.map((n) => n.id));
  const keptEdges = edges.filter(
    (e) => kept.has(e.src_node_id) && kept.has(e.dst_node_id),
  );
  return { nodes, edges: keptEdges };
}

export async function queryGraphNodeDetail(
  pool: Pool,
  symbol: string,
): Promise<{
  node: GraphNode;
  edges_out: GraphEdge[];
  edges_in: GraphEdge[];
  evidence: Array<{
    disclosure_id: number;
    title: string | null;
    published_at: string | null;
    pdf_url: string | null;
    equity_ok: boolean;
    relations_ok: boolean;
  }>;
} | null> {
  const sym = normalizeSymbol(symbol);
  if (!sym) return null;

  const { nodes, edges } = await queryCompanyGraph(pool, {
    minConfidence: "low",
    limit: 100,
    focusSymbol: sym,
    includeIsolates: true,
  });
  const node = nodes.find((n) => n.symbol === sym);
  if (!node) return null;

  const edges_out = edges.filter((e) => e.src_node_id === node.id);
  const edges_in = edges.filter((e) => e.dst_node_id === node.id);

  const ev = await pool.query(
    `
    SELECT
      g.disclosure_id,
      d.title,
      d.published_at,
      d.pdf_url,
      g.equity_ok,
      g.relations_ok
    FROM filing_graph_extracts g
    JOIN disclosures d ON d.id = g.disclosure_id
    WHERE g.symbol = $1
    ORDER BY g.fiscal_period_end DESC NULLS LAST, g.id DESC
    LIMIT 8
    `,
    [sym],
  );

  const evidence = ev.rows.map((row) => ({
    disclosure_id: Number(row.disclosure_id),
    title:
      typeof row.title === "string"
        ? sanitizeDisclosureText(row.title, 160)
        : null,
    published_at:
      row.published_at instanceof Date
        ? row.published_at.toISOString()
        : typeof row.published_at === "string"
          ? row.published_at
          : null,
    pdf_url: typeof row.pdf_url === "string" ? row.pdf_url : null,
    equity_ok: Boolean(row.equity_ok),
    relations_ok: Boolean(row.relations_ok),
  }));

  return { node, edges_out, edges_in, evidence };
}
