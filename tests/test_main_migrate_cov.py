"""E5-C02: Unit coverage for koel.migrate and koel.__main__ dispatch paths."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel import __main__ as main_mod
from koel.health import HealthState
from koel.migrate import apply_migrations
from koel.migrate import main as migrate_main
from koel.poller import Poller

# --- migrate: pure unit (no DATABASE_URL) ---------------------------------


class _FakeCursor:
    def __init__(self, row: Any = None) -> None:
        self._row = row

    def fetchone(self) -> Any:
        return self._row


class _FakeConn:
    """Sync psycopg-like connection for apply_migrations."""

    def __init__(self, *, already: set[str] | None = None) -> None:
        self.already = set(already or [])
        self.sql: list[str] = []
        self.inserted: list[str] = []
        self.commits = 0

    def execute(self, sql: str, params: Any = None) -> _FakeCursor:
        self.sql.append(sql)
        if "SELECT 1 FROM schema_migrations" in sql and params:
            name = params[0]
            return _FakeCursor((1,) if name in self.already else None)
        if "INSERT INTO schema_migrations" in sql and params:
            self.inserted.append(params[0])
            self.already.add(params[0])
        return _FakeCursor()

    def commit(self) -> None:
        self.commits += 1

    @contextmanager
    def transaction(self) -> Any:
        yield

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_apply_migrations_skips_already_applied(tmp_path: Path) -> None:
    (tmp_path / "001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "002_b.sql").write_text("SELECT 2;", encoding="utf-8")
    conn = _FakeConn(already={"001_a.sql"})

    with patch("koel.migrate.psycopg.connect", return_value=conn):
        applied = apply_migrations("postgresql://fake", directory=tmp_path)

    assert applied == ["002_b.sql"]
    assert conn.inserted == ["002_b.sql"]
    assert conn.commits == 1


def test_apply_migrations_applies_all_when_empty(tmp_path: Path) -> None:
    (tmp_path / "001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "002_b.sql").write_text("SELECT 2;", encoding="utf-8")
    conn = _FakeConn()

    with patch("koel.migrate.psycopg.connect", return_value=conn):
        applied = apply_migrations("postgresql://fake", directory=tmp_path)

    assert applied == ["001_a.sql", "002_b.sql"]
    assert conn.inserted == ["001_a.sql", "002_b.sql"]


def test_apply_migrations_noop_when_all_applied(tmp_path: Path) -> None:
    (tmp_path / "001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    conn = _FakeConn(already={"001_a.sql"})

    with patch("koel.migrate.psycopg.connect", return_value=conn):
        applied = apply_migrations("postgresql://fake", directory=tmp_path)

    assert applied == []
    assert conn.inserted == []


def test_migrate_main_prints_applied(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "koel.migrate.Settings.from_env",
        lambda **_: MagicMock(database_url="postgresql://unit"),
    )
    monkeypatch.setattr("koel.migrate.apply_migrations", lambda url: ["001_initial.sql"])
    monkeypatch.setattr("koel.migrate.configure_logging", lambda: None)

    assert migrate_main([]) == 0
    out = capsys.readouterr().out
    assert "Applied: 001_initial.sql" in out


def test_migrate_main_prints_no_pending(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "koel.migrate.Settings.from_env",
        lambda **_: MagicMock(database_url="postgresql://unit"),
    )
    monkeypatch.setattr("koel.migrate.apply_migrations", lambda url: [])
    monkeypatch.setattr("koel.migrate.configure_logging", lambda: None)

    assert migrate_main(["--database-url", "postgresql://cli"]) == 0
    out = capsys.readouterr().out
    assert "No pending migrations." in out


def test_migrate_main_uses_cli_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    monkeypatch.setattr("koel.migrate.configure_logging", lambda: None)
    monkeypatch.setattr(
        "koel.migrate.apply_migrations",
        lambda url: seen.append(url) or [],
    )

    assert migrate_main(["--database-url", "postgresql://from-cli"]) == 0
    assert seen == ["postgresql://from-cli"]


# --- __main__: health exception paths + CLI dispatch ----------------------


@pytest.mark.asyncio
async def test_refresh_bot_health_exception_sets_last_error() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(side_effect=RuntimeError("boom"))
    health = HealthState()

    await main_mod._refresh_bot_health(storage, health)

    assert health.ok is False
    assert health.details.get("db_ok") is False
    assert health.details.get("last_error") == "boom"


@pytest.mark.asyncio
async def test_refresh_both_health_db_exception_still_updates() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(side_effect=RuntimeError("db down"))
    health = HealthState()
    poller = AsyncMock(spec=Poller)
    poller.last_tick_ok = True
    poller.last_tick_at = None
    poller.price_poll_ok = True
    poller.disclosure_poll_ok = True
    poller.lock_held_skip = False
    poller.watched_missing = []
    poller.last_error = None
    poller.cse = MagicMock()
    poller.cse.circuit_metrics = MagicMock(return_value={})

    await main_mod._refresh_both_health(storage, health, poller)

    assert health.ok is False  # db_ok False and tick ok → ok False
    assert health.details.get("db_ok") is False
    assert health.details.get("last_tick_ok") is True


@pytest.mark.asyncio
async def test_install_stop_handler_sets_event_on_sig() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    handlers: list[Any] = []

    def _capture(sig: object, callback: Any) -> None:
        handlers.append(callback)

    with patch.object(loop, "add_signal_handler", side_effect=_capture):
        main_mod._install_stop_handler(stop)

    assert len(handlers) >= 1
    handlers[0]()
    assert stop.is_set()


@pytest.mark.asyncio
async def test_install_stop_handler_suppresses_unsupported_signals() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _raise(*_a: object, **_k: object) -> None:
        raise NotImplementedError

    with patch.object(loop, "add_signal_handler", side_effect=_raise):
        main_mod._install_stop_handler(stop)  # must not raise
    assert not stop.is_set()


def _fake_settings() -> MagicMock:
    s = MagicMock()
    s.database_url = "postgresql://unit"
    s.telegram_bot_token = "token"
    s.log_level = "INFO"
    s.cse_base_url = "https://www.cse.lk/api"
    s.http_timeout_seconds = 15.0
    s.circuit_fail_max = 5
    s.circuit_reset_seconds = 60.0
    s.cse_min_interval_seconds = 0.0
    s.health_host = "127.0.0.1"
    s.health_port = 0
    s.bot_cmd_rate_per_minute = 20
    return s


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch, settings: MagicMock | None = None
) -> MagicMock:
    s = settings or _fake_settings()

    def _from_env(**_k: object) -> MagicMock:
        return s

    monkeypatch.setattr(main_mod, "configure_logging", lambda *a, **k: None)
    monkeypatch.setattr(main_mod.Settings, "from_env", _from_env)
    return s


def test_main_migrate_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_settings(monkeypatch)
    monkeypatch.setattr(main_mod, "apply_migrations", lambda url: ["001_initial.sql", "002_x.sql"])

    main_mod.main(["migrate"])
    out = capsys.readouterr().out
    assert "Applied: 001_initial.sql, 002_x.sql" in out


def test_main_migrate_none_pending(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_settings(monkeypatch)
    monkeypatch.setattr(main_mod, "apply_migrations", lambda url: [])

    main_mod.main(["migrate"])
    out = capsys.readouterr().out
    assert "Applied: (none)" in out


@pytest.mark.parametrize("cmd", ["bot", "poller", "both"])
def test_main_dispatches_long_runners(cmd: str, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    async def _bot(settings: object) -> None:
        called.append("bot")

    async def _poller(settings: object) -> None:
        called.append("poller")

    async def _both(settings: object) -> None:
        called.append("both")

    _patch_settings(monkeypatch)
    monkeypatch.setattr(main_mod, "_run_bot", _bot)
    monkeypatch.setattr(main_mod, "_run_poller", _poller)
    monkeypatch.setattr(main_mod, "_run_both", _both)

    main_mod.main([cmd])
    assert called == [cmd]


def test_main_tick_force(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_settings(monkeypatch)

    storage = AsyncMock()
    storage.open = AsyncMock()
    storage.close = AsyncMock()
    monkeypatch.setattr(main_mod, "Storage", lambda *a, **k: storage)

    cse = AsyncMock()
    cse.aclose = AsyncMock()
    monkeypatch.setattr(main_mod, "CSEClient", lambda *a, **k: cse)

    monkeypatch.setattr(main_mod, "Bot", lambda *a, **k: MagicMock())

    poller = AsyncMock()
    poller.run_once = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
    monkeypatch.setattr(main_mod, "Poller", lambda *a, **k: poller)

    async def _send(*a: object, **k: object) -> object:
        return MagicMock()

    monkeypatch.setattr(main_mod, "send_message", _send)

    main_mod.main(["tick", "--force"])
    out = capsys.readouterr().out
    assert "Fired 2 alert(s)" in out
    poller.run_once.assert_awaited_once_with(force=True)
    storage.close.assert_awaited()
    cse.aclose.assert_awaited()


def test_main_tick_without_force(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_settings(monkeypatch)

    storage = AsyncMock()
    storage.open = AsyncMock()
    storage.close = AsyncMock()
    monkeypatch.setattr(main_mod, "Storage", lambda *a, **k: storage)

    cse = AsyncMock()
    cse.aclose = AsyncMock()
    monkeypatch.setattr(main_mod, "CSEClient", lambda *a, **k: cse)
    monkeypatch.setattr(main_mod, "Bot", lambda *a, **k: MagicMock())

    poller = AsyncMock()
    poller.run_once = AsyncMock(return_value=[])
    monkeypatch.setattr(main_mod, "Poller", lambda *a, **k: poller)
    monkeypatch.setattr(main_mod, "send_message", AsyncMock())

    main_mod.main(["tick"])
    out = capsys.readouterr().out
    assert "Fired 0 alert(s)" in out
    poller.run_once.assert_awaited_once_with(force=False)


def _wire_runtime_mocks(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Shared mocks for _run_bot / _run_poller / _run_both short-circuit tests."""
    storage = AsyncMock()
    storage.open = AsyncMock()
    storage.close = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    monkeypatch.setattr(main_mod, "Storage", lambda *a, **k: storage)

    cse = AsyncMock()
    cse.aclose = AsyncMock()
    monkeypatch.setattr(main_mod, "CSEClient", lambda *a, **k: cse)
    monkeypatch.setattr(main_mod, "Bot", lambda *a, **k: MagicMock())
    monkeypatch.setattr(main_mod, "send_message", AsyncMock(return_value=MagicMock()))

    server = MagicMock()
    monkeypatch.setattr(main_mod, "start_health_server", lambda *a, **k: server)

    def _stop_now(stop: asyncio.Event) -> None:
        stop.set()

    monkeypatch.setattr(main_mod, "_install_stop_handler", _stop_now)

    updater = AsyncMock()
    updater.start_polling = AsyncMock()
    updater.stop = AsyncMock()
    app = AsyncMock()
    app.updater = updater
    app.initialize = AsyncMock()
    app.start = AsyncMock()
    app.stop = AsyncMock()
    app.shutdown = AsyncMock()
    monkeypatch.setattr(main_mod, "build_application", lambda *a, **k: app)

    return {"storage": storage, "cse": cse, "server": server, "app": app, "updater": updater}


@pytest.mark.asyncio
async def test_run_bot_exits_when_stop_set(monkeypatch: pytest.MonkeyPatch) -> None:
    mocks = _wire_runtime_mocks(monkeypatch)
    await main_mod._run_bot(_fake_settings())
    mocks["storage"].close.assert_awaited()
    mocks["cse"].aclose.assert_awaited()
    mocks["server"].shutdown.assert_called_once()
    mocks["app"].shutdown.assert_awaited()


@pytest.mark.asyncio
async def test_run_poller_closes_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    mocks = _wire_runtime_mocks(monkeypatch)

    async def _forever(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(main_mod, "run_poller_forever", _forever)
    await main_mod._run_poller(_fake_settings())
    mocks["storage"].close.assert_awaited()
    mocks["cse"].aclose.assert_awaited()
    mocks["server"].shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_run_both_exits_when_stop_set(monkeypatch: pytest.MonkeyPatch) -> None:
    mocks = _wire_runtime_mocks(monkeypatch)

    poller = MagicMock()
    poller.start_scheduler = MagicMock()
    poller.shutdown = AsyncMock()
    poller.last_tick_ok = True
    poller.last_tick_at = None
    poller.price_poll_ok = True
    poller.disclosure_poll_ok = True
    poller.lock_held_skip = False
    poller.watched_missing = []
    poller.last_error = None
    monkeypatch.setattr(main_mod, "Poller", lambda *a, **k: poller)

    await main_mod._run_both(_fake_settings())
    poller.shutdown.assert_awaited()
    mocks["storage"].close.assert_awaited()
    mocks["cse"].aclose.assert_awaited()
    mocks["server"].shutdown.assert_called_once()
