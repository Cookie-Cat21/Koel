"""E8-Q01 / E5-C01: apply_migrations is idempotent when run twice.

Requires DATABASE_URL. Skips if unset (unit CI parity).
"""

from __future__ import annotations

import os

import psycopg
import pytest

from chime.config import migrations_dir
from chime.migrate import apply_migrations

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


def test_apply_migrations_twice_idempotent() -> None:
    assert DATABASE_URL
    first = apply_migrations(DATABASE_URL)
    second = apply_migrations(DATABASE_URL)

    assert second == []
    # First run applies pending files (or none if already current).
    assert isinstance(first, list)

    expected = sorted(p.name for p in migrations_dir().glob("*.sql") if p.is_file())
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT filename FROM schema_migrations ORDER BY filename"
        ).fetchall()
    applied = [r[0] for r in rows]
    for name in expected:
        assert name in applied
