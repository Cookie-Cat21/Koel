#!/usr/bin/env python3
"""Copy denser company/people graph rows from a local Postgres into DATABASE_URL.

Used to densify production Neon after local seed/drain produced richer edges
and director seats. Disclosure FKs are cleared (IDs do not transfer).

Env:
  SOURCE_DATABASE_URL  default postgresql://chime:chime@localhost:5432/chime
  DATABASE_URL         target (required) — typically Neon production
"""

from __future__ import annotations

import json
import os
import sys

import psycopg


def _connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=False)


def sync_company_graph(src: psycopg.Connection, dst: psycopg.Connection) -> None:
    with src.cursor() as cur:
        cur.execute(
            """
            SELECT symbol, display_name, name_norm, node_kind,
                   equity, equity_as_of, equity_scale, equity_currency,
                   equity_confidence
            FROM company_graph_nodes
            WHERE symbol IS NOT NULL
            ORDER BY symbol
            """
        )
        nodes = cur.fetchall()

    ensured = 0
    skipped_stock = 0
    with dst.cursor() as cur:
        for (
            symbol,
            display_name,
            name_norm,
            node_kind,
            equity,
            equity_as_of,
            equity_scale,
            equity_currency,
            equity_confidence,
        ) in nodes:
            cur.execute("SELECT 1 FROM stocks WHERE symbol = %s", (symbol,))
            if cur.fetchone() is None:
                skipped_stock += 1
                continue
            cur.execute(
                """
                INSERT INTO company_graph_nodes (
                    symbol, display_name, name_norm, node_kind,
                    equity, equity_as_of, equity_scale, equity_currency,
                    equity_disclosure_id, equity_confidence
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    NULL, %s
                )
                ON CONFLICT (symbol) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    name_norm = EXCLUDED.name_norm,
                    equity = COALESCE(EXCLUDED.equity, company_graph_nodes.equity),
                    equity_as_of = COALESCE(
                        EXCLUDED.equity_as_of, company_graph_nodes.equity_as_of
                    ),
                    equity_scale = CASE
                        WHEN EXCLUDED.equity IS NOT NULL THEN EXCLUDED.equity_scale
                        ELSE company_graph_nodes.equity_scale
                    END,
                    equity_currency = CASE
                        WHEN EXCLUDED.equity IS NOT NULL THEN EXCLUDED.equity_currency
                        ELSE company_graph_nodes.equity_currency
                    END,
                    equity_confidence = CASE
                        WHEN EXCLUDED.equity IS NOT NULL THEN EXCLUDED.equity_confidence
                        ELSE company_graph_nodes.equity_confidence
                    END,
                    updated_at = now()
                """,
                (
                    symbol,
                    display_name,
                    name_norm,
                    node_kind,
                    equity,
                    equity_as_of,
                    equity_scale or "unknown",
                    equity_currency or "LKR",
                    equity_confidence or "none",
                ),
            )
            ensured += 1
    dst.commit()
    print(f"company nodes upserted={ensured} skipped_missing_stock={skipped_stock}")

    with src.cursor() as cur:
        cur.execute(
            """
            SELECT a.symbol, b.symbol, e.relation, e.ownership_pct,
                   e.ownership_pct_confidence, e.confidence,
                   e.evidence_page, e.evidence_snippet, e.extract_notes, e.active
            FROM company_graph_edges e
            JOIN company_graph_nodes a ON a.id = e.src_node_id
            JOIN company_graph_nodes b ON b.id = e.dst_node_id
            WHERE e.active
              AND a.symbol IS NOT NULL
              AND b.symbol IS NOT NULL
            ORDER BY a.symbol, b.symbol, e.relation
            """
        )
        edges = cur.fetchall()

    wrote = 0
    skipped = 0
    with dst.cursor() as cur:
        for (
            src_sym,
            dst_sym,
            relation,
            ownership_pct,
            ownership_pct_confidence,
            confidence,
            evidence_page,
            evidence_snippet,
            extract_notes,
            active,
        ) in edges:
            cur.execute(
                "SELECT id FROM company_graph_nodes WHERE symbol = %s",
                (src_sym,),
            )
            src_row = cur.fetchone()
            cur.execute(
                "SELECT id FROM company_graph_nodes WHERE symbol = %s",
                (dst_sym,),
            )
            dst_row = cur.fetchone()
            if src_row is None or dst_row is None:
                skipped += 1
                continue
            notes = extract_notes
            if notes is not None and not isinstance(notes, str):
                notes = json.dumps(notes)
            elif notes is None:
                notes = "{}"
            cur.execute(
                """
                INSERT INTO company_graph_edges (
                    src_node_id, dst_node_id, relation,
                    ownership_pct, ownership_pct_confidence, confidence,
                    evidence_disclosure_id, evidence_page, evidence_snippet,
                    extract_notes, active
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    NULL, %s, %s,
                    %s::jsonb, %s
                )
                ON CONFLICT (src_node_id, dst_node_id, relation) DO UPDATE SET
                    ownership_pct = COALESCE(
                        EXCLUDED.ownership_pct, company_graph_edges.ownership_pct
                    ),
                    ownership_pct_confidence = CASE
                        WHEN EXCLUDED.ownership_pct IS NOT NULL
                        THEN EXCLUDED.ownership_pct_confidence
                        ELSE company_graph_edges.ownership_pct_confidence
                    END,
                    confidence = CASE
                        WHEN company_graph_edges.confidence = 'high' THEN 'high'
                        WHEN EXCLUDED.confidence = 'high' THEN 'high'
                        WHEN company_graph_edges.confidence = 'medium'
                          OR EXCLUDED.confidence = 'medium'
                        THEN 'medium'
                        ELSE EXCLUDED.confidence
                    END,
                    evidence_page = COALESCE(
                        EXCLUDED.evidence_page, company_graph_edges.evidence_page
                    ),
                    evidence_snippet = COALESCE(
                        EXCLUDED.evidence_snippet,
                        company_graph_edges.evidence_snippet
                    ),
                    extract_notes = EXCLUDED.extract_notes,
                    active = EXCLUDED.active,
                    updated_at = now()
                """,
                (
                    src_row[0],
                    dst_row[0],
                    relation,
                    ownership_pct,
                    ownership_pct_confidence or "none",
                    confidence,
                    evidence_page,
                    evidence_snippet,
                    notes,
                    active,
                ),
            )
            wrote += 1
    dst.commit()
    print(f"company edges upserted={wrote} skipped={skipped}")


def sync_people(src: psycopg.Connection, dst: psycopg.Connection) -> None:
    with src.cursor() as cur:
        cur.execute(
            """
            SELECT display_name, name_norm
            FROM people
            ORDER BY name_norm
            """
        )
        people = cur.fetchall()

    with dst.cursor() as cur:
        for display_name, name_norm in people:
            cur.execute(
                """
                INSERT INTO people (display_name, name_norm)
                VALUES (%s, %s)
                ON CONFLICT (name_norm) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    updated_at = now()
                """,
                (display_name, name_norm),
            )
    dst.commit()
    print(f"people upserted={len(people)}")

    with src.cursor() as cur:
        cur.execute(
            """
            SELECT p.name_norm, r.symbol, r.role, r.confidence,
                   r.evidence_page, r.evidence_snippet, r.extract_notes, r.active
            FROM person_company_roles r
            JOIN people p ON p.id = r.person_id
            WHERE r.active
            ORDER BY p.name_norm, r.symbol, r.role
            """
        )
        roles = cur.fetchall()

    wrote = 0
    skipped = 0
    with dst.cursor() as cur:
        for (
            name_norm,
            symbol,
            role,
            confidence,
            evidence_page,
            evidence_snippet,
            extract_notes,
            active,
        ) in roles:
            cur.execute("SELECT 1 FROM stocks WHERE symbol = %s", (symbol,))
            if cur.fetchone() is None:
                skipped += 1
                continue
            cur.execute(
                "SELECT id FROM people WHERE name_norm = %s",
                (name_norm,),
            )
            person = cur.fetchone()
            if person is None:
                skipped += 1
                continue
            notes = extract_notes
            if notes is not None and not isinstance(notes, str):
                notes = json.dumps(notes)
            elif notes is None:
                notes = "{}"
            cur.execute(
                """
                INSERT INTO person_company_roles (
                    person_id, symbol, role, confidence,
                    evidence_disclosure_id, evidence_page, evidence_snippet,
                    extract_notes, active
                ) VALUES (
                    %s, %s, %s, %s,
                    NULL, %s, %s,
                    %s::jsonb, %s
                )
                ON CONFLICT (person_id, symbol, role) DO UPDATE SET
                    confidence = CASE
                        WHEN person_company_roles.confidence = 'high' THEN 'high'
                        WHEN EXCLUDED.confidence = 'high' THEN 'high'
                        WHEN person_company_roles.confidence = 'medium'
                          OR EXCLUDED.confidence = 'medium'
                        THEN 'medium'
                        ELSE EXCLUDED.confidence
                    END,
                    evidence_page = COALESCE(
                        EXCLUDED.evidence_page, person_company_roles.evidence_page
                    ),
                    evidence_snippet = COALESCE(
                        EXCLUDED.evidence_snippet,
                        person_company_roles.evidence_snippet
                    ),
                    extract_notes = EXCLUDED.extract_notes,
                    active = EXCLUDED.active,
                    updated_at = now()
                """,
                (
                    person[0],
                    symbol,
                    role,
                    confidence,
                    evidence_page,
                    evidence_snippet,
                    notes,
                    active,
                ),
            )
            wrote += 1
    dst.commit()
    print(f"roles upserted={wrote} skipped={skipped}")


def main() -> int:
    source = os.environ.get(
        "SOURCE_DATABASE_URL",
        "postgresql://chime:chime@localhost:5432/chime",
    )
    target = os.environ.get("DATABASE_URL")
    if not target:
        print("DATABASE_URL is required", file=sys.stderr)
        return 1
    if "localhost" in target or "127.0.0.1" in target:
        print(
            "Refusing to write when DATABASE_URL looks local; "
            "point it at Neon (or set TARGET_DATABASE_URL).",
            file=sys.stderr,
        )
        # Allow explicit override
        target = os.environ.get("TARGET_DATABASE_URL", target)
        if "localhost" in target or "127.0.0.1" in target:
            return 2

    print(f"source={source.split('@')[-1]}")
    print(f"target={target.split('@')[-1]}")
    with _connect(source) as src, _connect(target) as dst:
        sync_company_graph(src, dst)
        sync_people(src, dst)

        with dst.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM company_graph_edges WHERE active"
            )
            edges = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*) FROM company_graph_edges e
                JOIN company_graph_nodes a ON a.id = e.src_node_id
                JOIN company_graph_nodes b ON b.id = e.dst_node_id
                WHERE e.active
                  AND a.symbol IS NOT NULL AND b.symbol IS NOT NULL
                  AND e.confidence IN ('medium', 'high')
                """
            )
            listed = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM people")
            people = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM person_company_roles WHERE active"
            )
            roles = cur.fetchone()[0]
            cur.execute(
                "SELECT count(DISTINCT symbol) FROM person_company_roles WHERE active"
            )
            symbols = cur.fetchone()[0]
        print(
            f"target totals: edges_active={edges} listed_med_high={listed} "
            f"people={people} roles={roles} symbols_with_roles={symbols}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
