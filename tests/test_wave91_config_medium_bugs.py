"""Wave91: config/migrate/__main__ CLI args fail closed.

1. ``koel.migrate --database-url ""`` must not silently fall back to
   ``DATABASE_URL`` (an explicit blank target could migrate the wrong DB).
2. Top-level ``--force`` is only meaningful for ``tick``; other commands must
   reject it instead of no-op soft-accepting operator intent.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from koel import __main__ as main_mod
from koel.migrate import main as migrate_main


def test_migrate_cli_rejects_blank_database_url_before_env_fallback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "koel.migrate.Settings.from_env",
        lambda **_: pytest.fail("blank CLI database URL must not fall back to env"),
    )
    monkeypatch.setattr(
        "koel.migrate.apply_migrations",
        lambda _url: pytest.fail("blank CLI database URL must not apply migrations"),
    )

    with pytest.raises(SystemExit) as excinfo:
        migrate_main(["--database-url", "   "])

    assert excinfo.value.code == 2
    assert "must not be blank" in capsys.readouterr().err


def test_migrate_cli_strips_explicit_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr("koel.migrate.configure_logging", lambda: None)
    monkeypatch.setattr(
        "koel.migrate.Settings.from_env",
        lambda **_: pytest.fail("explicit CLI database URL must not read env"),
    )
    monkeypatch.setattr(
        "koel.migrate.apply_migrations",
        lambda url: seen.append(url) or [],
    )

    assert migrate_main(["--database-url", "  postgresql://from-cli  "]) == 0
    assert seen == ["postgresql://from-cli"]


@pytest.mark.parametrize("cmd", ["bot", "poller", "both", "migrate"])
def test_main_force_flag_rejected_for_non_tick_commands(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    cmd: str,
) -> None:
    monkeypatch.setattr(main_mod, "configure_logging", lambda *a, **k: None)
    monkeypatch.setattr(
        main_mod.Settings,
        "from_env",
        lambda **_: pytest.fail("--force must reject before Settings load"),
    )
    monkeypatch.setattr(
        main_mod,
        "apply_migrations",
        lambda _url: pytest.fail("--force must reject before migrations"),
    )
    monkeypatch.setattr(main_mod, "_run_bot", MagicMock())
    monkeypatch.setattr(main_mod, "_run_poller", MagicMock())
    monkeypatch.setattr(main_mod, "_run_both", MagicMock())

    with pytest.raises(SystemExit) as excinfo:
        main_mod.main([cmd, "--force"])

    assert excinfo.value.code == 2
    assert "--force is only valid for tick" in capsys.readouterr().err
