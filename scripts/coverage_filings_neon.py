#!/usr/bin/env python3
"""Print Neon disclosure/metrics/brief coverage for the CSE board."""
from __future__ import annotations
import os, psycopg
def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set")
    with psycopg.connect(url) as conn:
        stocks = conn.execute("SELECT count(*) FROM stocks").fetchone()[0]
        disc = conn.execute("SELECT count(DISTINCT symbol) FROM disclosures").fetchone()[0]
        fin = conn.execute(
            "SELECT count(DISTINCT symbol) FROM disclosures WHERE external_id LIKE 'fin-%'"
        ).fetchone()[0]
        ok = conn.execute(
            "SELECT count(DISTINCT symbol) FROM filing_metrics WHERE extract_ok"
        ).fetchone()[0]
        ready = conn.execute(
            """
            SELECT count(DISTINCT d.symbol) FROM disclosure_briefs b
            JOIN disclosures d ON d.id=b.disclosure_id
            WHERE b.status='ready'
              AND (d.external_id LIKE 'fin-%' OR d.title ILIKE '%financial%'
                   OR d.title ILIKE '%interim%')
            """
        ).fetchone()[0]
        missing = conn.execute(
            """
            SELECT s.symbol FROM stocks s
            WHERE NOT EXISTS (
              SELECT 1 FROM filing_metrics fm
              WHERE fm.symbol=s.symbol AND fm.extract_ok
            )
            ORDER BY 1 LIMIT 40
            """
        ).fetchall()
        print(
            f"stocks={stocks} disclosures={disc} fin_disc={fin} "
            f"metrics_ok={ok} financial_briefs={ready}"
        )
        print("missing_metrics_sample:", ", ".join(r[0] for r in missing))
if __name__ == "__main__":
    main()
