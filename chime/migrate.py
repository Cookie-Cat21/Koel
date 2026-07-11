"""Tiny SQL migration runner — applies db/migrations/*.sql in sorted order."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from chime.config import Settings, migrations_dir
from chime.logging_setup import configure_logging, get_logger

log = get_logger(__name__)


def apply_migrations(database_url: str, directory: Path | None = None) -> list[str]:
    mig_dir = directory or migrations_dir()
    files = sorted(p for p in mig_dir.glob("*.sql") if p.is_file())
    applied: list[str] = []
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()
        for path in files:
            row = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE filename = %s",
                (path.name,),
            ).fetchone()
            if row:
                continue
            sql = path.read_text(encoding="utf-8")
            log.info("applying_migration", filename=path.name)
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
            applied.append(path.name)
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Chime SQL migrations")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Postgres URL (default: DATABASE_URL env)",
    )
    args = parser.parse_args(argv)
    configure_logging()
    url = args.database_url or Settings.from_env(require_token=False).database_url
    applied = apply_migrations(url)
    if applied:
        print(f"Applied: {', '.join(applied)}")
    else:
        print("No pending migrations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
