"""Wave13: migrate sanity — SQL files parse without a live DB.

When DATABASE_URL is set, also prove apply_migrations is a no-op on the
second run (same gate as E8-Q01 / E5-C01). Unit CI clears DATABASE_URL, so
the parse path is the default proof.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from koel.config import migrations_dir
from koel.migrate import apply_migrations

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# DDL / DML keywords used across db/migrations/*.sql
_STMT_START = re.compile(
    r"^(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|COMMENT|SELECT|DO|SET|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _strip_sql_comments(sql: str) -> str:
    """Remove -- line comments and /* */ block comments; keep string literals."""
    out: list[str] = []
    i = 0
    n = len(sql)
    in_single = False
    in_double = False
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if in_single:
            out.append(ch)
            if ch == "'" and nxt == "'":
                out.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            out.append(ch)
            if ch == '"' and nxt == '"':
                out.append(nxt)
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            out.append(ch)
            i += 1
            continue
        if ch == "-" and nxt == "-":
            i += 2
            while i < n and sql[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_sql_statements(sql: str) -> list[str]:
    """Split on ';' outside string literals after comment strip."""
    cleaned = _strip_sql_comments(sql)
    stmts: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    i = 0
    n = len(cleaned)
    while i < n:
        ch = cleaned[i]
        nxt = cleaned[i + 1] if i + 1 < n else ""
        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            buf.append(ch)
            if ch == '"' and nxt == '"':
                buf.append(nxt)
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue
        if ch == ";":
            text = "".join(buf).strip()
            if text:
                stmts.append(text)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def _migration_files() -> list[Path]:
    files = sorted(p for p in migrations_dir().glob("*.sql") if p.is_file())
    assert files, "expected SQL migrations under db/migrations"
    return files


def test_migration_sql_files_parse() -> None:
    """Each migration is UTF-8, non-empty, and splits into keyword-led statements."""
    files = _migration_files()
    assert all(re.match(r"^\d{3}_.+\.sql$", p.name) for p in files)
    assert [p.name for p in files] == sorted(p.name for p in files)

    for path in files:
        raw = path.read_bytes()
        assert raw, f"{path.name}: empty file"
        assert b"\x00" not in raw, f"{path.name}: unexpected NUL byte"
        text = raw.decode("utf-8")
        assert text.strip(), f"{path.name}: whitespace-only"

        statements = _split_sql_statements(text)
        assert statements, f"{path.name}: no SQL statements after comment strip"
        for stmt in statements:
            head = stmt.lstrip()
            assert _STMT_START.match(head), (
                f"{path.name}: statement does not start with a known SQL keyword: "
                f"{head[:80]!r}"
            )
            # Parentheses / quotes should balance enough to catch truncated dumps.
            assert head.count("(") == head.count(")"), (
                f"{path.name}: unbalanced parentheses in statement starting "
                f"{head[:60]!r}"
            )
            assert head.count("'") % 2 == 0, (
                f"{path.name}: unbalanced single quotes in statement starting "
                f"{head[:60]!r}"
            )


def test_migration_sql_parse_helpers_roundtrip() -> None:
    """Comment strip + split keep real DDL and ignore comment-only ';' noise."""
    sample = """
    -- leading comment with ; inside
    /* block ; comment */
    CREATE TABLE IF NOT EXISTS t (id INT, name TEXT DEFAULT 'a;b');
    ALTER TABLE t ADD COLUMN IF NOT EXISTS x TEXT;
    """
    stmts = _split_sql_statements(sample)
    assert len(stmts) == 2
    assert stmts[0].upper().startswith("CREATE TABLE")
    assert stmts[1].upper().startswith("ALTER TABLE")
    assert "a;b" in stmts[0]


@pytest.mark.integration
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
def test_apply_migrations_twice_when_database_url() -> None:
    """Live DB path: migrate twice; second apply is empty (idempotent)."""
    assert DATABASE_URL
    first = apply_migrations(DATABASE_URL)
    second = apply_migrations(DATABASE_URL)
    assert second == []
    assert isinstance(first, list)
