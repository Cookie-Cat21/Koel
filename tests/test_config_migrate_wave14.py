"""Wave14: cover remaining config.py / migrate.py lines (_float parse, __main__)."""

from __future__ import annotations

import runpy
import sys
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest

import koel.migrate  # noqa: F401 — ensure module is cached before runpy swap
from koel.config import Settings, migrations_dir

_DSN = "postgresql://koel:koel@localhost:5432/koel"


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)


def test_float_env_parses_non_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hits config._float return float(raw) (line previously missing)."""
    _base_env(monkeypatch)
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "45.5")
    monkeypatch.setenv("POLL_JITTER_SECONDS", "2.25")
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("CIRCUIT_RESET_SECONDS", "90.0")
    monkeypatch.setenv("PDF_ENRICH_SLEEP_SECONDS", "1.5")

    settings = Settings.from_env(require_token=True)

    assert settings.poll_interval_seconds == 45.5
    assert settings.poll_jitter_seconds == 2.25
    assert settings.http_timeout_seconds == 30.0
    assert settings.circuit_reset_seconds == 90.0
    assert settings.pdf_enrich_sleep_seconds == 1.5


def test_float_env_blank_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "   ")
    settings = Settings.from_env(require_token=True)
    assert settings.poll_interval_seconds == 5.0


class _FakeCursor:
    def __init__(self, row: Any = None) -> None:
        self._row = row

    def fetchone(self) -> Any:
        return self._row


class _FakeConn:
    """Sync psycopg-like connection for apply_migrations under runpy."""

    def __init__(self, *, already: set[str] | None = None) -> None:
        self.already = set(already or [])

    def execute(self, sql: str, params: Any = None) -> _FakeCursor:
        if "SELECT 1 FROM schema_migrations" in sql and params:
            name = params[0]
            return _FakeCursor((1,) if name in self.already else None)
        return _FakeCursor()

    def commit(self) -> None:
        return None

    @contextmanager
    def transaction(self) -> Any:
        yield

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_migrate_module_dunder_main_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Execute koel.migrate as __main__ so sys.exit(main()) is covered.

    runpy reloads the module, so patch psycopg (shared) + env rather than
    attributes on the pre-imported koel.migrate module object. Restore the
    original module in sys.modules afterward so other tests' imported
    ``main`` still resolves against a patchable module.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://unit")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["koel.migrate"])

    already = {p.name for p in migrations_dir().glob("*.sql") if p.is_file()}
    conn = _FakeConn(already=already)
    original = sys.modules["koel.migrate"]

    try:
        sys.modules.pop("koel.migrate", None)
        with (
            patch("psycopg.connect", return_value=conn),
            pytest.raises(SystemExit) as excinfo,
        ):
            runpy.run_module("koel.migrate", run_name="__main__", alter_sys=True)
    finally:
        sys.modules["koel.migrate"] = original

    assert excinfo.value.code == 0
    assert "No pending migrations." in capsys.readouterr().out
