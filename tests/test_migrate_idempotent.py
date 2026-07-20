"""E8-Q01 / E5-C01: apply_migrations is idempotent when run twice.

Also pins wave3 migration 005/006 presence and wave12 continuum 001–008
(unit; no DB required). Idempotent apply requires DATABASE_URL and skips if
unset (unit CI parity).
"""

from __future__ import annotations

import os
import re

import psycopg
import pytest

from koel.config import migrations_dir
from koel.migrate import apply_migrations

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Wave12 continuum pin: no gaps / renames through sectors ingest.
EXPECTED_MIGRATIONS_001_008 = [
    "001_initial.sql",
    "002_alert_log_attempts.sql",
    "003_delivery_attempted_ok.sql",
    "004_delivery_lease.sql",
    "005_disclosure_briefs.sql",
    "006_alert_rule_category.sql",
    "007_brief_processing_status.sql",
    "008_sectors.sql",
]


def test_migrations_001_through_008_continuum() -> None:
    """Migrations 001–008 exist as an unbroken ordered continuum (wave12)."""
    files = sorted(p.name for p in migrations_dir().glob("*.sql") if p.is_file())
    assert files, "expected SQL migrations under db/migrations"
    assert all(re.match(r"^\d{3}_.+\.sql$", name) for name in files)
    assert files == sorted(files)
    assert files[:8] == EXPECTED_MIGRATIONS_001_008
    for name in EXPECTED_MIGRATIONS_001_008:
        path = migrations_dir() / name
        assert path.is_file(), f"missing migration file: {name}"
        assert path.stat().st_size > 0, f"empty migration file: {name}"


def test_migration_filenames_ordered_and_wave3_presence() -> None:
    """Filenames sort lexicographically; 005/006/007/008 presence pinned."""
    files = sorted(p.name for p in migrations_dir().glob("*.sql") if p.is_file())
    assert files, "expected SQL migrations under db/migrations"
    assert files == sorted(files)
    assert all(re.match(r"^\d{3}_.+\.sql$", name) for name in files)

    assert "005_disclosure_briefs.sql" in files
    assert "006_alert_rule_category.sql" in files
    assert "007_brief_processing_status.sql" in files
    assert "008_sectors.sql" in files
    assert files.index("005_disclosure_briefs.sql") < files.index("006_alert_rule_category.sql")
    assert files.index("006_alert_rule_category.sql") < files.index(
        "007_brief_processing_status.sql"
    )
    assert files.index("007_brief_processing_status.sql") < files.index("008_sectors.sql")

    briefs_sql = (migrations_dir() / "005_disclosure_briefs.sql").read_text(encoding="utf-8")
    assert "disclosure_briefs" in briefs_sql
    assert "pdf_url" in briefs_sql

    category_sql = (migrations_dir() / "006_alert_rule_category.sql").read_text(encoding="utf-8")
    assert "alert_rules" in category_sql
    assert re.search(r"ADD COLUMN IF NOT EXISTS\s+category\b", category_sql, re.IGNORECASE)

    processing_sql = (migrations_dir() / "007_brief_processing_status.sql").read_text(
        encoding="utf-8"
    )
    assert "processing" in processing_sql

    sectors_sql = (migrations_dir() / "008_sectors.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS sectors" in sectors_sql
    assert "sector_id" in sectors_sql


@pytest.mark.integration
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
def test_apply_migrations_twice_idempotent() -> None:
    assert DATABASE_URL
    first = apply_migrations(DATABASE_URL)
    second = apply_migrations(DATABASE_URL)

    assert second == []
    # First run applies pending files (or none if already current).
    assert isinstance(first, list)

    expected = sorted(p.name for p in migrations_dir().glob("*.sql") if p.is_file())
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute("SELECT filename FROM schema_migrations ORDER BY filename").fetchall()
    applied = [r[0] for r in rows]
    for name in expected:
        assert name in applied
    assert "005_disclosure_briefs.sql" in applied
    assert "006_alert_rule_category.sql" in applied
