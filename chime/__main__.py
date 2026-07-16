"""Chime entrypoint: bot, poller, migrate, or both."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import inspect
import signal

from telegram import Bot

from chime.adapters.cse import CSEClient
from chime.bot import build_application
from chime.config import Settings
from chime.drain import drain_briefs, drain_metrics, drain_pdfs
from chime.health import HealthState, brief_queue_health_hint, start_health_server
from chime.logging_setup import configure_logging, get_logger
from chime.migrate import apply_migrations
from chime.notify import SendResult, send_message
from chime.path_backfill import run_path_backfill
from chime.poller import Poller, run_poller_forever
from chime.sector_backfill import run_sector_backfill
from chime.signals import run_signal_score_job
from chime.storage import Storage

log = get_logger(__name__)

POOL_CHECKOUT_WAIT_ELEVATED_MS = 250.0


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
    details: dict[str, object] = dict(ok=db_ok, db_ok=db_ok, last_error=last_error)
    brief_queue = await brief_queue_health_hint(storage=storage)
    if brief_queue:
        details["brief_queue"] = brief_queue
    health.update(**details)


def _circuits_for_health(poller: Poller) -> dict[str, object]:
    """Safe circuit snapshots for health JSON (MagicMock-safe)."""
    cse = getattr(poller, "cse", None)
    fn = getattr(cse, "circuit_metrics", None) if cse is not None else None
    if not callable(fn):
        return {}
    raw = fn()
    return raw if isinstance(raw, dict) else {}


def _pool_for_health(storage: Storage) -> dict[str, object]:
    """Safe storage pool snapshot for health JSON (mock-safe, real metrics only)."""
    fn = getattr(storage, "pool_health_snapshot", None)
    if not callable(fn) or inspect.iscoroutinefunction(fn):
        return {}
    raw = fn()
    if not isinstance(raw, dict):
        return {}

    health_checkout_wait = raw.get("health_checkout_wait_ms")
    checkout_wait_elevated = (
        isinstance(health_checkout_wait, int | float)
        and not isinstance(health_checkout_wait, bool)
        and health_checkout_wait >= POOL_CHECKOUT_WAIT_ELEVATED_MS
    )
    requests_waiting = raw.get("requests_waiting")
    waiting_requests = (
        isinstance(requests_waiting, int | float)
        and not isinstance(requests_waiting, bool)
        and requests_waiting > 0
    )

    snapshot: dict[str, object] = {
        "checkout_wait_elevated": checkout_wait_elevated,
        "checkout_wait_elevated_after_ms": POOL_CHECKOUT_WAIT_ELEVATED_MS,
        "contention": checkout_wait_elevated or waiting_requests,
    }
    for key in (
        "health_checkout_wait_ms",
        "pool_min",
        "pool_max",
        "pool_size",
        "pool_available",
        "requests_waiting",
    ):
        value = raw.get(key)
        if value is None or (isinstance(value, int | float) and not isinstance(value, bool)):
            snapshot[key] = value
    return snapshot


def _trade_summary_empty_ok_for_health(poller: Poller) -> bool:
    value = getattr(poller, "trade_summary_empty_ok", False)
    return value if isinstance(value, bool) else False


def _trade_summary_count_for_health(poller: Poller) -> int | None:
    value = getattr(poller, "trade_summary_count", None)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _trade_summary_for_health(poller: Poller) -> dict[str, object]:
    return {
        "empty_ok": _trade_summary_empty_ok_for_health(poller),
        "count": _trade_summary_count_for_health(poller),
    }


async def _refresh_both_health(storage: Storage, health: HealthState, poller: Poller) -> None:
    db_ok = False
    try:
        db_ok = await storage.health_check()
    except Exception as exc:
        log.warning("health_db_failed", error=str(exc))
    missing = list(poller.watched_missing)
    trade_summary = _trade_summary_for_health(poller)
    trade_summary_empty_ok = bool(trade_summary["empty_ok"])
    trade_summary_count = trade_summary["count"]
    pool = _pool_for_health(storage)
    pool_contention = bool(pool.get("contention"))
    # E8-Q02: non-empty watched_missing is always degraded (not only via last_tick_ok).
    details: dict[str, object] = dict(
        ok=(
            db_ok
            and poller.last_tick_ok
            and not missing
            and not trade_summary_empty_ok
            and not pool_contention
        ),
        db_ok=db_ok,
        last_tick_at=poller.last_tick_at.isoformat() if poller.last_tick_at else None,
        last_tick_ok=poller.last_tick_ok,
        price_poll_ok=poller.price_poll_ok,
        disclosure_poll_ok=poller.disclosure_poll_ok,
        lock_held_skip=poller.lock_held_skip,
        watched_missing=missing,
        trade_summary_empty_ok=trade_summary_empty_ok,
        trade_summary_count=trade_summary_count,
        tradeSummary=trade_summary,
        circuits=_circuits_for_health(poller),
        last_error=poller.last_error,
    )
    if pool:
        details["db_pool"] = pool
    brief_queue = await brief_queue_health_hint(storage=storage, poller=poller)
    if brief_queue:
        details["brief_queue"] = brief_queue
    health.update(**details)


async def _run_both(settings: Settings) -> None:
    storage = Storage(settings.database_url)
    await storage.open()
    cse = CSEClient(
        base_url=settings.cse_base_url,
        timeout=settings.http_timeout_seconds,
        fail_max=settings.circuit_fail_max,
        reset_timeout=settings.circuit_reset_seconds,
        min_interval_seconds=settings.cse_min_interval_seconds,
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
        min_interval_seconds=settings.cse_min_interval_seconds,
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
        min_interval_seconds=settings.cse_min_interval_seconds,
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
        choices=[
            "bot",
            "poller",
            "both",
            "migrate",
            "tick",
            "drain-pdfs",
            "drain-briefs",
            "drain-metrics",
            "path-backfill",
            "score-signals",
            "eval-signals",
            "sector-backfill",
        ],
        help=(
            "bot | poller | both | migrate | tick | "
            "drain-pdfs | drain-briefs | drain-metrics | "
            "path-backfill | score-signals | eval-signals | sector-backfill"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "tick: ignore market hours; "
            "path-backfill/sector-backfill: run even if flag off"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="For drain-* / path-backfill: max rows/symbols (default 20)",
    )
    parser.add_argument(
        "--all-symbols",
        action="store_true",
        help="For drain-pdfs/drain-metrics: include non-watchlist symbols",
    )
    parser.add_argument(
        "--period",
        type=int,
        default=None,
        help="For path-backfill: CSE chart period 2–5 (default PATH_BACKFILL_PERIOD/5)",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="For path-backfill: skip tradeSummary id seed",
    )
    args = parser.parse_args(argv)
    if args.force and args.command not in ("tick", "path-backfill", "sector-backfill"):
        parser.error("--force is only valid for tick, path-backfill, or sector-backfill")
    if args.period is not None and args.command != "path-backfill":
        parser.error("--period is only valid for path-backfill")
    if args.no_seed and args.command != "path-backfill":
        parser.error("--no-seed is only valid for path-backfill")

    if args.command == "migrate":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        applied = apply_migrations(settings.database_url)
        print("Applied:", ", ".join(applied) if applied else "(none)")
        return

    if args.command in ("drain-pdfs", "drain-briefs", "drain-metrics"):
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else 20
        watched_only = not args.all_symbols

        async def _drain() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            try:
                if args.command == "drain-briefs":
                    result = await drain_briefs(storage=storage, limit=limit)
                elif args.command == "drain-pdfs":
                    cse = CSEClient(
                        base_url=settings.cse_base_url,
                        timeout=settings.http_timeout_seconds,
                        fail_max=settings.circuit_fail_max,
                        reset_timeout=settings.circuit_reset_seconds,
                        min_interval_seconds=settings.cse_min_interval_seconds,
                    )
                    try:
                        result = await drain_pdfs(
                            storage=storage,
                            cse=cse,
                            settings=settings,
                            limit=limit,
                            watched_only=watched_only,
                        )
                    finally:
                        await cse.aclose()
                else:
                    result = await drain_metrics(
                        storage=storage,
                        limit=limit,
                        watched_only=watched_only,
                    )
                print(
                    f"{result.command}: examined={result.examined} "
                    f"updated={result.updated} skipped={result.skipped} "
                    f"errors={result.errors}"
                )
            finally:
                await storage.close()

        asyncio.run(_drain())
        return

    if args.command == "path-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else None

        async def _path_bf() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            cse = CSEClient(
                base_url=settings.cse_base_url,
                timeout=settings.http_timeout_seconds,
                fail_max=settings.circuit_fail_max,
                reset_timeout=settings.circuit_reset_seconds,
                min_interval_seconds=settings.cse_min_interval_seconds,
            )
            try:
                result = await run_path_backfill(
                    settings=settings,
                    storage=storage,
                    cse=cse,
                    period=args.period,
                    limit=limit,
                    seed_ids=not args.no_seed,
                    force=args.force,
                )
                print(
                    "path-backfill: "
                    f"targeted={result.symbols_targeted} "
                    f"ok={result.symbols_ok} "
                    f"skipped={result.symbols_skipped} "
                    f"failed={result.symbols_failed} "
                    f"bars={result.bars_upserted}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_path_bf())
        return

    if args.command == "sector-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else None

        async def _sector_bf() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            cse = CSEClient(
                base_url=settings.cse_base_url,
                timeout=settings.http_timeout_seconds,
                fail_max=settings.circuit_fail_max,
                reset_timeout=settings.circuit_reset_seconds,
                min_interval_seconds=settings.cse_min_interval_seconds,
            )
            try:
                result = await run_sector_backfill(
                    settings=settings,
                    storage=storage,
                    cse=cse,
                    limit=limit,
                    force=args.force,
                )
                print(
                    "sector-backfill: "
                    f"targeted={result.symbols_targeted} "
                    f"updated={result.symbols_updated} "
                    f"skipped={result.symbols_skipped} "
                    f"failed={result.symbols_failed}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_sector_bf())
        return

    if args.command == "score-signals":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else None

        async def _score() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_signal_score_job(storage=storage, limit=limit)
                print(
                    "score-signals: "
                    f"targeted={result.symbols_targeted} "
                    f"scored={result.symbols_scored} "
                    f"skipped={result.symbols_skipped} "
                    f"forecast_pts={result.forecasts_written} "
                    f"model={result.model_version}"
                )
            finally:
                await storage.close()

        asyncio.run(_score())
        return

    if args.command == "eval-signals":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else 40

        async def _eval() -> None:
            from chime.signals.eval import evaluate_walk_forward

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                symbols = await storage.list_symbols_with_daily_bars()
                symbols = symbols[:limit]
                series = {}
                for symbol in symbols:
                    series[symbol] = await storage.list_daily_bars(symbol)
                report = evaluate_walk_forward(series, horizon=5, min_history=30, step=5)
                print(
                    "eval-signals: "
                    f"symbols={report.symbols} origins={report.origins} "
                    f"dir_hits={report.direction_hits}/{report.direction_total} "
                    f"hit_rate={report.hit_rate!s} mae={report.mae!s} "
                    f"horizon={report.horizon}"
                )
            finally:
                await storage.close()

        asyncio.run(_eval())
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
            cse = CSEClient(
                base_url=settings.cse_base_url,
                timeout=settings.http_timeout_seconds,
                fail_max=settings.circuit_fail_max,
                reset_timeout=settings.circuit_reset_seconds,
                min_interval_seconds=settings.cse_min_interval_seconds,
            )
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
