import type { Pool } from "pg";

import { toFiniteNumber } from "@/lib/api/finite-number";
import {
  MAX_STOCK_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import {
  pickInitialsDisplay,
  softPersonKey,
} from "@/lib/api/person-aliases";
import {
  PERSON_ROLES,
  ROLE_WEIGHT,
  type PersonRole,
} from "@/lib/api/people-graph";
import { normalizeSymbol } from "@/lib/api/symbol";

export type DossierSeat = {
  symbol: string;
  company_name: string | null;
  sector: string | null;
  roles: PersonRole[];
  market_cap: number | null;
  price: number | null;
  change_pct: number | null;
  volume: number | null;
  turnover: number | null;
  influence_share: number;
};

export type DossierCoDirector = {
  id: number;
  name: string;
  shared_symbols: string[];
  shared_count: number;
  top_role: PersonRole | null;
  influence_score: number;
};

/** Issuer filings / board events on seated companies (DB-only; no CSE call). */
export type DossierTimelineEvent = {
  at: string;
  kind: "board_event" | "issuer_filing";
  symbol: string;
  title: string;
  category: string | null;
  url: string | null;
  disclosure_id: number;
};

export type PersonDossier = {
  id: number;
  name: string;
  merged_ids: number[];
  top_role: PersonRole | null;
  influence_score: number;
  company_count: number;
  /** Sum of latest share volume across seated issuers (not personal volume). */
  linked_volume: number;
  /** Sum of latest turnover (LKR) across seated issuers. */
  linked_turnover: number;
  seats: DossierSeat[];
  network: DossierCoDirector[];
  timeline: DossierTimelineEvent[];
  disclaimer: string;
};

const BOARD_EVENT_CAT =
  /(APPOINTMENT|RESIGNATION|RETIREMENT|DEMISE).*(DIRECTOR|CHAIR)|DEALINGS BY DIRECTORS|RELATED PARTY TRANSACTION/i;

function asRole(raw: unknown): PersonRole | null {
  if (typeof raw !== "string") return null;
  const v = raw.trim().toLowerCase();
  return (PERSON_ROLES as readonly string[]).includes(v)
    ? (v as PersonRole)
    : null;
}

function roleRank(role: PersonRole): number {
  return ROLE_WEIGHT[role] ?? 0;
}

/**
 * Load a person dossier. Soft-merges CSE initials variants that share the
 * same softPersonKey so K. Balendra / K. N. J. Balendra land on one page.
 */
export async function queryPersonDossier(
  pool: Pool,
  personId: number,
): Promise<PersonDossier | null> {
  if (!Number.isFinite(personId) || personId <= 0) return null;

  const seed = await pool.query(
    `SELECT id, display_name, name_norm FROM people WHERE id = $1`,
    [personId],
  );
  if (seed.rows.length === 0) return null;

  const seedName = String(seed.rows[0].display_name ?? "");
  const mergeKey = softPersonKey(seedName);

  // Pull a bounded candidate set that might soft-merge with this person
  const candidates = await pool.query(
    `
    SELECT DISTINCT p.id, p.display_name, p.name_norm
    FROM people p
    JOIN person_company_roles r ON r.person_id = p.id AND r.active
    WHERE r.extract_notes->>'source' = 'cse_company_profile'
       OR r.extract_notes->>'source' IS NULL
    LIMIT 4000
    `,
  );

  const mergedIds: number[] = [];
  let displayName = seedName;
  for (const row of candidates.rows) {
    const id = Number(row.id);
    const name = String(row.display_name ?? "");
    if (!Number.isFinite(id)) continue;
    if (softPersonKey(name) !== mergeKey) continue;
    mergedIds.push(id);
    displayName = pickInitialsDisplay(displayName, name);
  }
  if (!mergedIds.includes(personId)) mergedIds.push(personId);

  const rolesRes = await pool.query(
    `
    SELECT
      r.person_id,
      r.symbol,
      r.role,
      r.confidence,
      s.name AS company_name,
      s.sector,
      ps.market_cap,
      ps.price,
      ps.change_pct,
      ps.volume,
      ps.turnover
    FROM person_company_roles r
    LEFT JOIN stocks s ON s.symbol = r.symbol
    LEFT JOIN LATERAL (
      SELECT market_cap, price, change_pct, volume, turnover
      FROM price_snapshots x
      WHERE x.symbol = r.symbol
      ORDER BY x.ts DESC
      LIMIT 1
    ) ps ON TRUE
    WHERE r.person_id = ANY($1::bigint[])
      AND r.active
    ORDER BY r.symbol ASC
    `,
    [mergedIds],
  );

  type SeatAcc = {
    symbol: string;
    company_name: string | null;
    sector: string | null;
    roles: PersonRole[];
    market_cap: number | null;
    price: number | null;
    change_pct: number | null;
    volume: number | null;
    turnover: number | null;
    bestWeight: number;
  };
  const bySym = new Map<string, SeatAcc>();
  let topRole: PersonRole | null = null;
  let topWeight = -1;

  for (const row of rolesRes.rows) {
    const symbol = normalizeSymbol(row.symbol);
    if (!symbol) continue;
    const role = asRole(row.role);
    if (!role) continue;
    const mcap = toFiniteNumber(row.market_cap);
    const price = toFiniteNumber(row.price);
    const changePct = toFiniteNumber(row.change_pct);
    const volume = toFiniteNumber(row.volume);
    const turnover = toFiniteNumber(row.turnover);
    const w = roleRank(role);
    if (w > topWeight) {
      topWeight = w;
      topRole = role;
    }
    const prev = bySym.get(symbol);
    if (!prev) {
      bySym.set(symbol, {
        symbol,
        company_name:
          typeof row.company_name === "string"
            ? sanitizeDisclosureText(row.company_name, MAX_STOCK_NAME_LENGTH)
            : null,
        sector:
          typeof row.sector === "string"
            ? sanitizeDisclosureText(row.sector, 80)
            : null,
        roles: [role],
        market_cap: mcap,
        price,
        change_pct: changePct,
        volume,
        turnover,
        bestWeight: w,
      });
      continue;
    }
    if (!prev.roles.includes(role)) prev.roles.push(role);
    if (w > prev.bestWeight) prev.bestWeight = w;
    if ((mcap ?? 0) > (prev.market_cap ?? 0)) prev.market_cap = mcap;
    if (prev.price == null && price != null) prev.price = price;
    if (prev.change_pct == null && changePct != null) prev.change_pct = changePct;
    if (prev.volume == null && volume != null) prev.volume = volume;
    if (prev.turnover == null && turnover != null) prev.turnover = turnover;
  }

  const seatsRaw = Array.from(bySym.values()).map((s) => ({
    ...s,
    roles: [...s.roles].sort((a, b) => roleRank(b) - roleRank(a)),
  }));

  let influence = 0;
  let linkedVolume = 0;
  let linkedTurnover = 0;
  for (const s of seatsRaw) {
    influence += (s.market_cap ?? 0) * s.bestWeight;
    linkedVolume += s.volume ?? 0;
    linkedTurnover += s.turnover ?? 0;
  }

  const seats: DossierSeat[] = seatsRaw
    .map((s) => ({
      symbol: s.symbol,
      company_name: s.company_name,
      sector: s.sector,
      roles: s.roles,
      market_cap: s.market_cap,
      price: s.price,
      change_pct: s.change_pct,
      volume: s.volume,
      turnover: s.turnover,
      influence_share:
        influence > 0 ? ((s.market_cap ?? 0) * s.bestWeight) / influence : 0,
    }))
    .sort(
      (a, b) =>
        b.influence_share - a.influence_share ||
        (b.volume ?? 0) - (a.volume ?? 0) ||
        (b.market_cap ?? 0) - (a.market_cap ?? 0),
    );

  const symbols = seats.map((s) => s.symbol);
  const network: DossierCoDirector[] = [];

  if (symbols.length > 0) {
    const netRes = await pool.query(
      `
      SELECT
        p.id AS person_id,
        p.display_name,
        r.symbol,
        r.role,
        ps.market_cap
      FROM person_company_roles r
      JOIN people p ON p.id = r.person_id
      LEFT JOIN LATERAL (
        SELECT market_cap
        FROM price_snapshots x
        WHERE x.symbol = r.symbol AND x.market_cap IS NOT NULL
        ORDER BY x.ts DESC
        LIMIT 1
      ) ps ON TRUE
      WHERE r.active
        AND r.symbol = ANY($1::text[])
        AND NOT (r.person_id = ANY($2::bigint[]))
      `,
      [symbols, mergedIds],
    );

    type NetAcc = {
      id: number;
      name: string;
      symbols: Set<string>;
      topRole: PersonRole | null;
      topWeight: number;
      influence: number;
      perSym: Map<string, number>;
    };
    const byPerson = new Map<number, NetAcc>();
    for (const row of netRes.rows) {
      const id = Number(row.person_id);
      if (!Number.isFinite(id)) continue;
      const symbol = normalizeSymbol(row.symbol);
      if (!symbol) continue;
      const role = asRole(row.role);
      if (!role) continue;
      const name = sanitizeDisclosureText(
        String(row.display_name ?? ""),
        MAX_STOCK_NAME_LENGTH,
      );
      if (!name) continue;
      let acc = byPerson.get(id);
      if (!acc) {
        acc = {
          id,
          name,
          symbols: new Set(),
          topRole: null,
          topWeight: -1,
          influence: 0,
          perSym: new Map(),
        };
        byPerson.set(id, acc);
      }
      acc.name = pickInitialsDisplay(acc.name, name);
      acc.symbols.add(symbol);
      const w = roleRank(role);
      if (w > acc.topWeight) {
        acc.topWeight = w;
        acc.topRole = role;
      }
      const mcap = toFiniteNumber(row.market_cap) ?? 0;
      const score = mcap * w;
      const prev = acc.perSym.get(symbol) ?? 0;
      if (score > prev) acc.perSym.set(symbol, score);
    }

    // Soft-merge network peers
    const peerMerged = new Map<string, NetAcc>();
    for (const acc of byPerson.values()) {
      const key = softPersonKey(acc.name);
      const prev = peerMerged.get(key);
      if (!prev) {
        peerMerged.set(key, acc);
        continue;
      }
      prev.name = pickInitialsDisplay(prev.name, acc.name);
      for (const s of acc.symbols) prev.symbols.add(s);
      for (const [sym, score] of acc.perSym) {
        const p = prev.perSym.get(sym) ?? 0;
        if (score > p) prev.perSym.set(sym, score);
      }
      if (acc.topWeight > prev.topWeight) {
        prev.topWeight = acc.topWeight;
        prev.topRole = acc.topRole;
      }
    }

    for (const acc of peerMerged.values()) {
      let inf = 0;
      for (const v of acc.perSym.values()) inf += v;
      network.push({
        id: acc.id,
        name: acc.name,
        shared_symbols: Array.from(acc.symbols).sort(),
        shared_count: acc.symbols.size,
        top_role: acc.topRole,
        influence_score: inf,
      });
    }
    network.sort(
      (a, b) =>
        b.shared_count - a.shared_count ||
        b.influence_score - a.influence_score,
    );
  }

  const timeline: DossierTimelineEvent[] = [];
  if (symbols.length > 0) {
    const discRes = await pool.query(
      `
      SELECT id, symbol, title, category, url, published_at
      FROM disclosures
      WHERE symbol = ANY($1::text[])
      ORDER BY published_at DESC
      LIMIT 80
      `,
      [symbols],
    );

    for (const row of discRes.rows) {
      const symbol = normalizeSymbol(row.symbol);
      if (!symbol) continue;
      const title = sanitizeDisclosureText(
        String(row.title ?? ""),
        MAX_STOCK_NAME_LENGTH,
      );
      if (!title) continue;
      const category =
        typeof row.category === "string"
          ? sanitizeDisclosureText(row.category, 120)
          : null;
      const catOrTitle = `${category ?? ""} ${title}`;
      const isBoard = BOARD_EVENT_CAT.test(catOrTitle);
      // Cap issuer filings so board events (when present) stay visible.
      if (
        !isBoard &&
        timeline.filter((t) => t.kind === "issuer_filing").length >= 12
      ) {
        continue;
      }
      const at =
        row.published_at instanceof Date
          ? row.published_at.toISOString()
          : String(row.published_at ?? "");
      if (!at) continue;
      timeline.push({
        at,
        kind: isBoard ? "board_event" : "issuer_filing",
        symbol,
        title,
        category,
        url: typeof row.url === "string" && row.url ? row.url : null,
        disclosure_id: Number(row.id),
      });
      if (timeline.length >= 24) break;
    }

    timeline.sort((a, b) => b.at.localeCompare(a.at));
  }

  return {
    id: personId,
    name:
      sanitizeDisclosureText(displayName, MAX_STOCK_NAME_LENGTH) || "—",
    merged_ids: mergedIds,
    top_role: topRole,
    influence_score: influence,
    company_count: seats.length,
    linked_volume: linkedVolume,
    linked_turnover: linkedTurnover,
    seats,
    network: network.slice(0, 40),
    timeline: timeline.slice(0, 20),
    disclaimer:
      "Board seats from official CSE companyProfile. Influence / volume / turnover are linked company figures (latest snapshot) — not personal holdings. Not financial advice. Across-years lists issuer filings on seated companies; CSE has no historical board API.",
  };
}
