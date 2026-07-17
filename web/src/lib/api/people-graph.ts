import type { Pool } from "pg";

import { toFiniteNumber } from "@/lib/api/finite-number";
import {
  MAX_STOCK_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import {
  pickInitialsDisplay,
  preferredDisplayName,
  softPersonKey,
} from "@/lib/api/person-aliases";
import { normalizeSymbol } from "@/lib/api/symbol";

export const PERSON_ROLES = [
  "chairman",
  "deputy_chairman",
  "ceo",
  "managing_director",
  "executive_director",
  "non_executive_director",
  "independent_director",
  "senior_independent_director",
  "cfo",
  "company_secretary",
  "director",
  "key_management",
] as const;

export type PersonRole = (typeof PERSON_ROLES)[number];

/** Role weight for linked-company market-value influence (not personal net worth). */
export const ROLE_WEIGHT: Record<PersonRole, number> = {
  chairman: 1,
  ceo: 1,
  managing_director: 1,
  deputy_chairman: 0.7,
  executive_director: 0.45,
  cfo: 0.4,
  senior_independent_director: 0.3,
  independent_director: 0.25,
  non_executive_director: 0.25,
  company_secretary: 0.15,
  director: 0.2,
  key_management: 0.2,
};

export type PersonNode = {
  id: number;
  name: string;
  roles: Array<{
    symbol: string;
    company_name: string | null;
    role: PersonRole;
    confidence: string;
    market_cap: number | null;
    equity: number | null;
    price: number | null;
    change_pct: number | null;
    volume: number | null;
    turnover: number | null;
  }>;
  /** Sum of market_cap × role_weight across seats — research proxy, not net worth. */
  influence_score: number;
  /** Sum of latest share volume across unique seated issuers. */
  linked_volume: number;
  /** Sum of latest turnover (LKR) across unique seated issuers. */
  linked_turnover: number;
  company_count: number;
  top_role: PersonRole | null;
};

export type PersonCompanyEdge = {
  person_id: number;
  symbol: string;
  role: PersonRole;
  confidence: string;
};

function asRole(raw: unknown): PersonRole | null {
  if (typeof raw !== "string") return null;
  const v = raw.trim().toLowerCase();
  return (PERSON_ROLES as readonly string[]).includes(v)
    ? (v as PersonRole)
    : null;
}

function scaleEquity(
  equity: number | null,
  scale: string | null,
): number | null {
  if (equity == null) return null;
  const mult =
    scale === "millions" ? 1e6 : scale === "thousands" ? 1e3 : 1;
  const v = equity * mult;
  return v >= 10_000 ? v : null;
}

export async function queryPeopleGraph(
  pool: Pool,
  opts: {
    limit?: number;
    minConfidence?: "low" | "medium" | "high";
    leadershipOnly?: boolean;
  } = {},
): Promise<{ people: PersonNode[]; edges: PersonCompanyEdge[] }> {
  const limit = Math.min(Math.max(opts.limit ?? 200, 1), 500);
  const minRank =
    opts.minConfidence === "high" ? 3 : opts.minConfidence === "low" ? 1 : 2;
  // Default false = include full boards (independent / NED / etc.)
  const leadershipOnly = opts.leadershipOnly === true;

  const roleFilter = leadershipOnly
    ? `AND r.role IN (
         'chairman','ceo','managing_director','deputy_chairman',
         'executive_director','cfo','senior_independent_director'
       )`
    : "";

  const rows = await pool.query(
    `
    SELECT
      p.id AS person_id,
      p.display_name,
      r.symbol,
      r.role,
      r.confidence,
      s.name AS company_name,
      ps.market_cap,
      ps.price,
      ps.change_pct,
      ps.volume,
      ps.turnover,
      n.equity,
      n.equity_scale
    FROM person_company_roles r
    JOIN people p ON p.id = r.person_id
    LEFT JOIN stocks s ON s.symbol = r.symbol
    LEFT JOIN company_graph_nodes n ON n.symbol = r.symbol
    LEFT JOIN LATERAL (
      SELECT market_cap, price, change_pct, volume, turnover
      FROM price_snapshots x
      WHERE x.symbol = r.symbol
      ORDER BY x.ts DESC
      LIMIT 1
    ) ps ON TRUE
    WHERE r.active
      -- Prefer official CSE companyProfile seats when present for that issuer
      AND (
        r.extract_notes->>'source' = 'cse_company_profile'
        OR NOT EXISTS (
          SELECT 1
          FROM person_company_roles x
          WHERE x.symbol = r.symbol
            AND x.active
            AND x.extract_notes->>'source' = 'cse_company_profile'
        )
      )
      AND CASE r.confidence
            WHEN 'high' THEN 3
            WHEN 'medium' THEN 2
            ELSE 1
          END >= $1
      ${roleFilter}
    ORDER BY p.id ASC, r.symbol ASC
    `,
    [minRank],
  );

  type Acc = {
    id: number;
    name: string;
    roles: PersonNode["roles"];
    influence: number;
    symbols: Set<string>;
    bestWeight: number;
    topRole: PersonRole | null;
  };
  const byPerson = new Map<number, Acc>();
  const edges: PersonCompanyEdge[] = [];

  for (const row of rows.rows) {
    const role = asRole(row.role);
    if (!role) continue;
    const personId = Number(row.person_id);
    if (!Number.isFinite(personId)) continue;
    const symbol = normalizeSymbol(row.symbol);
    if (!symbol) continue;
    const mcap = toFiniteNumber(row.market_cap);
    const equity = scaleEquity(
      toFiniteNumber(row.equity),
      typeof row.equity_scale === "string" ? row.equity_scale : null,
    );
    const price = toFiniteNumber(row.price);
    const changePct = toFiniteNumber(row.change_pct);
    const volume = toFiniteNumber(row.volume);
    const turnover = toFiniteNumber(row.turnover);
    const weight = ROLE_WEIGHT[role] ?? 0.2;

    let acc = byPerson.get(personId);
    if (!acc) {
      acc = {
        id: personId,
        name: preferredDisplayName(
          sanitizeDisclosureText(
            String(row.display_name ?? ""),
            MAX_STOCK_NAME_LENGTH,
          ) || "—",
        ),
        roles: [],
        influence: 0,
        symbols: new Set(),
        bestWeight: 0,
        topRole: null,
      };
      byPerson.set(personId, acc);
    }
    acc.roles.push({
      symbol,
      company_name:
        typeof row.company_name === "string"
          ? sanitizeDisclosureText(row.company_name, MAX_STOCK_NAME_LENGTH)
          : null,
      role,
      confidence:
        typeof row.confidence === "string" ? row.confidence : "medium",
      market_cap: mcap,
      equity,
      price,
      change_pct: changePct,
      volume,
      turnover,
    });
    acc.symbols.add(symbol);
    // One contribution per symbol: keep max weight seat for influence
    if (weight >= acc.bestWeight) {
      acc.bestWeight = weight;
      acc.topRole = role;
    }
    edges.push({
      person_id: personId,
      symbol,
      role,
      confidence:
        typeof row.confidence === "string" ? row.confidence : "medium",
    });
  }

  function linkedFlow(roles: PersonNode["roles"]): {
    volume: number;
    turnover: number;
  } {
    const seen = new Set<string>();
    let volume = 0;
    let turnover = 0;
    for (const r of roles) {
      if (seen.has(r.symbol)) continue;
      seen.add(r.symbol);
      volume += r.volume ?? 0;
      turnover += r.turnover ?? 0;
    }
    return { volume, turnover };
  }

  // Influence: per symbol take the highest role weight × company value
  const people: PersonNode[] = [];
  for (const acc of byPerson.values()) {
    const perSym = new Map<string, number>();
    for (const r of acc.roles) {
      const base = r.market_cap ?? r.equity ?? 0;
      const w = ROLE_WEIGHT[r.role] ?? 0.2;
      const score = base * w;
      const prev = perSym.get(r.symbol) ?? 0;
      if (score > prev) perSym.set(r.symbol, score);
    }
    let influence = 0;
    for (const v of perSym.values()) influence += v;
    const flow = linkedFlow(acc.roles);
    people.push({
      id: acc.id,
      name: acc.name,
      roles: acc.roles,
      influence_score: influence,
      linked_volume: flow.volume,
      linked_turnover: flow.turnover,
      company_count: acc.symbols.size,
      top_role: acc.topRole,
    });
  }

  // Soft-merge near-duplicate identities (D. H. S. Jayawardena ≈ D. Hasitha S. Jayawardena)
  const merged = new Map<string, PersonNode>();
  for (const p of people) {
    const key = softPersonKey(p.name);
    const prev = merged.get(key);
    if (!prev) {
      merged.set(key, p);
      continue;
    }
    // Prefer CSE initials-style labels when merging spelling variants
    const name = pickInitialsDisplay(p.name, prev.name);
    const roleMap = new Map<string, PersonNode["roles"][number]>();
    for (const r of [...prev.roles, ...p.roles]) {
      const rk = `${r.symbol}:${r.role}`;
      if (!roleMap.has(rk)) roleMap.set(rk, r);
    }
    const roles = Array.from(roleMap.values());
    const perSym = new Map<string, number>();
    for (const r of roles) {
      const base = r.market_cap ?? r.equity ?? 0;
      const w = ROLE_WEIGHT[r.role] ?? 0.2;
      const score = base * w;
      const prevScore = perSym.get(r.symbol) ?? 0;
      if (score > prevScore) perSym.set(r.symbol, score);
    }
    let influence = 0;
    for (const v of perSym.values()) influence += v;
    const symbols = new Set(roles.map((r) => r.symbol));
    const flow = linkedFlow(roles);
    merged.set(key, {
      id: prev.id,
      name,
      roles,
      influence_score: influence,
      linked_volume: flow.volume,
      linked_turnover: flow.turnover,
      company_count: symbols.size,
      top_role:
        (influence >= prev.influence_score ? p.top_role : prev.top_role) ??
        prev.top_role,
    });
  }

  const out = Array.from(merged.values());
  out.sort((a, b) => b.influence_score - a.influence_score);
  // Rebuild edges from merged people so soft-merged seats stay linked
  const mergedEdges: PersonCompanyEdge[] = [];
  for (const p of out.slice(0, limit)) {
    for (const r of p.roles) {
      mergedEdges.push({
        person_id: p.id,
        symbol: r.symbol,
        role: r.role,
        confidence: r.confidence,
      });
    }
  }
  return { people: out.slice(0, limit), edges: mergedEdges };
}
