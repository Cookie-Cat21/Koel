"""Wave14: cover remaining chime.__main__ branches (health helpers + runtime loops)."""

from __future__ import annotations

import asyncio
import runpy
import sys
import warnings
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chime import __main__ as main_mod
from chime.health import HealthState
from chime.notify import SendResult


def _fake_settings() -> MagicMock:
    s = MagicMock()
    s.database_url = "postgresql://unit"
    s.telegram_bot_token = "token"
    s.log_level = "INFO"
    s.cse_base_url = "https://www.cse.lk/api"
    s.http_timeout_seconds = 15.0
    s.circuit_fail_max = 5
    s.circuit_reset_seconds = 60.0
    s.health_host = "127.0.0.1"
    s.health_port = 0
    s.bot_cmd_rate_per_minute = 20
    return s


@pytest.mark.asyncio
async def test_refresh_bot_health_includes_brief_queue_hint() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    storage.count_pending_disclosure_briefs = AsyncMock(return_value=3)
    health = HealthState()

    await main_mod._refresh_bot_health(storage, health)

    assert health.details.get("brief_queue") == {"pending_briefs": 3}


def test_circuits_for_health_non_callable_returns_empty() -> None:
    poller = MagicMock()
    poller.cse = MagicMock()
    poller.cse.circuit_metrics = "not-callable"
    assert main_mod._circuits_for_health(poller) == {}

    poller_no_cse = MagicMock(spec=[])
    assert main_mod._circuits_for_health(poller_no_cse) == {}


def test_pool_for_health_rejects_non_dict_snapshot() -> None:
    storage = MagicMock()
    storage.pool_health_snapshot = MagicMock(return_value=["not", "a", "dict"])
    assert main_mod._pool_for_health(storage) == {}


def test_pool_for_health_rejects_async_snapshot() -> None:
    storage = MagicMock()

    async def _async_snap() -> dict[str, object]:
        return {"pool_max": 1}

    storage.pool_health_snapshot = _async_snap
    assert main_mod._pool_for_health(storage) == {}


def test_trade_summary_count_rejects_bool() -> None:
    poller = MagicMock()
    poller.trade_summary_count = True
    assert main_mod._trade_summary_count_for_health(poller) is None
    assert main_mod._trade_summary_for_health(poller)["count"] is None


def test_trade_summary_empty_ok_rejects_non_bool() -> None:
    poller = MagicMock()
    poller.trade_summary_empty_ok = 1
    assert main_mod._trade_summary_empty_ok_for_health(poller) is False


def _wire_runtime(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    storage = AsyncMock()
    storage.open = AsyncMock()
    storage.close = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    monkeypatch.setattr(main_mod, "Storage", lambda *a, **k: storage)

    cse = AsyncMock()
    cse.aclose = AsyncMock()
    monkeypatch.setattr(main_mod, "CSEClient", lambda *a, **k: cse)
    monkeypatch.setattr(main_mod, "Bot", lambda *a, **k: MagicMock())

    send_mock = AsyncMock(return_value=SendResult.OK)
    monkeypatch.setattr(main_mod, "send_message", send_mock)

    server = MagicMock()
    monkeypatch.setattr(main_mod, "start_health_server", lambda *a, **k: server)

    updater = AsyncMock()
    updater.start_polling = AsyncMock()
    updater.stop = AsyncMock()
    app = AsyncMock()
    app.updater = updater
    app.initialize = AsyncMock()
    app.start = AsyncMock()
    app.stop = AsyncMock()
    app.shutdown = AsyncMock()
    app.post_init = None
    monkeypatch.setattr(main_mod, "build_application", lambda *a, **k: app)

    return {
        "storage": storage,
        "cse": cse,
        "server": server,
        "app": app,
        "updater": updater,
        "send_mock": send_mock,
    }


@pytest.mark.asyncio
async def test_run_bot_health_loop_then_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    mocks = _wire_runtime(monkeypatch)
    refresh = AsyncMock()
    monkeypatch.setattr(main_mod, "_refresh_bot_health", refresh)

    def _arm_stop(stop: asyncio.Event) -> None:
        async def _set_soon() -> None:
            await asyncio.sleep(0)
            stop.set()

        asyncio.get_running_loop().create_task(_set_soon())

    monkeypatch.setattr(main_mod, "_install_stop_handler", _arm_stop)

    await main_mod._run_bot(_fake_settings())

    refresh.assert_awaited()
    mocks["storage"].close.assert_awaited()
    mocks["server"].shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_run_both_health_loop_post_init_and_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocks = _wire_runtime(monkeypatch)
    captured_send: list[Any] = []

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
    poller.trade_summary_empty_ok = False
    poller.trade_summary_count = 1
    poller.cse = MagicMock()
    poller.cse.circuit_metrics = MagicMock(return_value={})

    def _poller_factory(
        settings: object,
        storage: object,
        cse: object,
        send: Any,
    ) -> MagicMock:
        captured_send.append(send)
        return poller

    monkeypatch.setattr(main_mod, "Poller", _poller_factory)

    refresh = AsyncMock()
    monkeypatch.setattr(main_mod, "_refresh_both_health", refresh)

    def _arm_stop(stop: asyncio.Event) -> None:
        async def _set_soon() -> None:
            await asyncio.sleep(0)
            stop.set()

        asyncio.get_running_loop().create_task(_set_soon())

    monkeypatch.setattr(main_mod, "_install_stop_handler", _arm_stop)

    await main_mod._run_both(_fake_settings())

    refresh.assert_awaited()
    assert mocks["app"].post_init is not None
    await mocks["app"].post_init(mocks["app"])

    assert captured_send, "Poller should receive send callback"
    result = await captured_send[0](42, "hello")
    assert result is SendResult.OK
    mocks["send_mock"].assert_awaited()
    assert mocks["send_mock"].await_args.kwargs.get("block_on_retry_after") is True

    poller.shutdown.assert_awaited()
    mocks["server"].shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_run_poller_send_wrapper_honors_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocks = _wire_runtime(monkeypatch)
    captured_send: list[Any] = []

    async def _forever(
        settings: object,
        storage: object,
        cse: object,
        send: Any,
        health: object = None,
    ) -> None:
        captured_send.append(send)
        await send(7, "tick")

    monkeypatch.setattr(main_mod, "run_poller_forever", _forever)
    await main_mod._run_poller(_fake_settings())

    assert captured_send
    mocks["send_mock"].assert_awaited()
    assert mocks["send_mock"].await_args.kwargs.get("block_on_retry_after") is True
    mocks["storage"].close.assert_awaited()
    mocks["cse"].aclose.assert_awaited()


def test_main_tick_send_wrapper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(main_mod, "configure_logging", lambda *a, **k: None)
    monkeypatch.setattr(main_mod.Settings, "from_env", lambda **_: _fake_settings())

    storage = AsyncMock()
    storage.open = AsyncMock()
    storage.close = AsyncMock()
    monkeypatch.setattr(main_mod, "Storage", lambda *a, **k: storage)

    cse = AsyncMock()
    cse.aclose = AsyncMock()
    monkeypatch.setattr(main_mod, "CSEClient", lambda *a, **k: cse)
    monkeypatch.setattr(main_mod, "Bot", lambda *a, **k: MagicMock())

    send_mock = AsyncMock(return_value=SendResult.OK)
    monkeypatch.setattr(main_mod, "send_message", send_mock)

    captured_send: list[Any] = []

    class _Poller:
        def __init__(
            self,
            settings: object,
            storage: object,
            cse: object,
            send: Any,
        ) -> None:
            captured_send.append(send)

        async def run_once(self, *, force: bool = False) -> list[object]:
            assert captured_send
            await captured_send[0](99, "forced")
            return [{"id": 1}]

    monkeypatch.setattr(main_mod, "Poller", _Poller)

    main_mod.main(["tick", "--force"])
    out = capsys.readouterr().out
    assert "Fired 1 alert(s)" in out
    send_mock.assert_awaited()
    assert send_mock.await_args.kwargs.get("block_on_retry_after") is True


def test_module_main_guard_invokes_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["chime", "migrate"])
    monkeypatch.setattr(
        "chime.config.Settings.from_env",
        lambda **_: MagicMock(database_url="postgresql://unit"),
    )
    monkeypatch.setattr("chime.migrate.apply_migrations", lambda url: [])
    monkeypatch.setattr("chime.logging_setup.configure_logging", lambda *a, **k: None)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*chime\.__main__.*sys\.modules.*",
            category=RuntimeWarning,
        )
        runpy.run_module("chime", run_name="__main__")
    out = capsys.readouterr().out
    assert "Applied: (none)" in out
