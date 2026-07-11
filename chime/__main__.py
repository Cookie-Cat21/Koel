"""Chime entrypoint: bot, poller, migrate, or both."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal

from telegram import Bot

from chime.adapters.cse import CSEClient
from chime.bot import build_application
from chime.config import Settings
from chime.health import HealthState, start_health_server
from chime.logging_setup import configure_logging, get_logger
from chime.migrate import apply_migrations
from chime.notify import SendResult, send_message
from chime.poller import Poller, run_poller_forever
from chime.storage import Storage

log = get_logger(__name__)


def _install_stop_handler(stop: asyncio.Event) -> None:
    def _handle_sig(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handle_sig)


async def _refresh_bot_health(storage: Storage, health: HealthState) -> None:
    """Bot-only health: DB reachability (no poller tick fields)."""
    db_ok = False
    last_error: str | None = None
    try:
        db_ok = await storage.health_check()
        if not db_ok:
            last_error = "db_unhealthy"
    except Exception as exc:
        last_error = str(exc)
        log.warning("health_db_failed", error=str(exc))
    health.update(ok=db_ok, db_ok=db_ok, last_error=last_error)


def _circuits_for_health(poller: Poller) -> dict[str, object]:
    """Safe circuit snapshots for health JSON (MagicMock-safe)."""
    cse = getattr(poller, "cse", None)
    fn = getattr(cse, "circuit_metrics", None) if cse is not None else None
    if not callable(fn):
        return {}
    raw = fn()
    return raw if isinstance(raw, dict) else {}


async def _refresh_both_health(storage: Storage, health: HealthState, poller: Poller) -> None:
    db_ok = False
    try:
        db_ok = await storage.health_check()
    except Exception as exc:
        log.warning("health_db_failed", error=str(exc))
    missing = list(poller.watched_missing)
    # E8-Q02: non-empty watched_missing is always degraded (not only via last_tick_ok).
    health.update(
        ok=db_ok and poller.last_tick_ok and not missing,
        db_ok=db_ok,
        last_tick_at=poller.last_tick_at.isoformat() if poller.last_tick_at else None,
        last_tick_ok=poller.last_tick_ok,
        price_poll_ok=poller.price_poll_ok,
        disclosure_poll_ok=poller.disclosure_poll_ok,
        lock_held_skip=poller.lock_held_skip,
        watched_missing=missing,
        circuits=_circuits_for_health(poller),
        last_error=poller.last_error,
    )


async def _run_both(settings: Settings) -> None:
    storage = Storage(settings.database_url)
    await storage.open()
    cse = CSEClient(
        base_url=settings.cse_base_url,
        timeout=settings.http_timeout_seconds,
        fail_max=settings.circuit_fail_max,
        reset_timeout=settings.circuit_reset_seconds,
    )
    bot = Bot(settings.telegram_bot_token)

    async def send(chat_id: int, text: str) -> SendResult:
        # Lock is released before Telegram I/O (CORE-004) — honor RetryAfter.
        return await send_message(bot, chat_id, text, block_on_retry_after=True)

    health = HealthState()
    server = start_health_server(settings.health_host, settings.health_port, health)

    poller = Poller(settings, storage, cse, send)
    poller.start_scheduler()

    app = build_application(
        settings.telegram_bot_token,
        storage,
        cse,
        cmd_rate_per_minute=settings.bot_cmd_rate_per_minute,
    )

    async def _post_init(application: object) -> None:
        log.info("bot_started")

    app.post_init = _post_init

    stop = asyncio.Event()
    _install_stop_handler(stop)

    try:
        await app.initialize()
        await app.start()
        assert app.updater is not None
        await app.updater.start_polling(drop_pending_updates=True)

        # Keep health fresh until SIGINT/SIGTERM
        while not stop.is_set():
            await _refresh_both_health(storage, health, poller)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=10)
    finally:
        await poller.shutdown()
        if app.updater is not None:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await cse.aclose()
        await storage.close()
        server.shutdown()


async def _run_poller(settings: Settings) -> None:
    storage = Storage(settings.database_url)
    await storage.open()
    cse = CSEClient(
        base_url=settings.cse_base_url,
        timeout=settings.http_timeout_seconds,
        fail_max=settings.circuit_fail_max,
        reset_timeout=settings.circuit_reset_seconds,
    )
    bot = Bot(settings.telegram_bot_token)

    async def send(chat_id: int, text: str) -> SendResult:
        # Lock is released before Telegram I/O (CORE-004) — honor RetryAfter.
        return await send_message(bot, chat_id, text, block_on_retry_after=True)

    health = HealthState()
    server = start_health_server(settings.health_host, settings.health_port, health)
    try:
        await run_poller_forever(settings, storage, cse, send, health=health)
    finally:
        await cse.aclose()
        await storage.close()
        server.shutdown()


async def _run_bot(settings: Settings) -> None:
    storage = Storage(settings.database_url)
    await storage.open()
    cse = CSEClient(
        base_url=settings.cse_base_url,
        timeout=settings.http_timeout_seconds,
        fail_max=settings.circuit_fail_max,
        reset_timeout=settings.circuit_reset_seconds,
    )
    health = HealthState()
    server = start_health_server(settings.health_host, settings.health_port, health)
    app = build_application(
        settings.telegram_bot_token,
        storage,
        cse,
        cmd_rate_per_minute=settings.bot_cmd_rate_per_minute,
    )

    stop = asyncio.Event()
    _install_stop_handler(stop)

    try:
        await app.initialize()
        await app.start()
        assert app.updater is not None
        await app.updater.start_polling(drop_pending_updates=True)
        log.info("bot_started")

        while not stop.is_set():
            await _refresh_bot_health(storage, health)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=10)
    finally:
        if app.updater is not None:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await cse.aclose()
        await storage.close()
        server.shutdown()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="chime", description="CSE Telegram alerting")
    parser.add_argument(
        "command",
        choices=["bot", "poller", "both", "migrate", "tick"],
        help="bot | poller | both | migrate | tick (one forced poll)",
    )
    parser.add_argument("--force", action="store_true", help="For tick: ignore market hours")
    args = parser.parse_args(argv)

    if args.command == "migrate":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        applied = apply_migrations(settings.database_url)
        print("Applied:", ", ".join(applied) if applied else "(none)")
        return

    settings = Settings.from_env(require_token=True)
    configure_logging(settings.log_level)

    if args.command == "bot":
        asyncio.run(_run_bot(settings))
    elif args.command == "poller":
        asyncio.run(_run_poller(settings))
    elif args.command == "both":
        asyncio.run(_run_both(settings))
    elif args.command == "tick":

        async def _tick() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            cse = CSEClient(base_url=settings.cse_base_url)
            bot = Bot(settings.telegram_bot_token)

            async def send(chat_id: int, text: str) -> SendResult:
                return await send_message(bot, chat_id, text, block_on_retry_after=True)

            poller = Poller(settings, storage, cse, send)
            try:
                events = await poller.run_once(force=args.force)
                print(f"Fired {len(events)} alert(s)")
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_tick())


if __name__ == "__main__":
    main()
