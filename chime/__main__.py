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
from chime.notices_backfill import run_notices_backfill
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
            "drain-briefs-local",
            "drain-metrics",
            "path-backfill",
            "hybrid-backfill",
            "score-signals",
            "eval-signals",
            "sector-backfill",
            "notices-backfill",
            "ml-experiment",
            "ml-forecast",
            "ml-transfer",
            "ml-harden",
            "ml-diagnose",
            "ml-iterate",
            "ml-precision90",
            "ml-hpe",
            "ml-forecast-unified",
            "ml-always-on",
            "disclosures-backfill",
            "financials-backfill",
            "aspi-backfill",
            "ml-score-outcomes",
            "ml-backfill-outcomes",
            "ml-loop-nightly",
            "ml-loop-retrain",
            "ml-loop-research",
            "market-summary-backfill",
        ],
        help=(
            "bot | poller | both | migrate | tick | "
            "drain-pdfs | drain-briefs | drain-briefs-local | drain-metrics | "
            "path-backfill | hybrid-backfill | score-signals | eval-signals | "
            "sector-backfill | notices-backfill | disclosures-backfill | "
            "financials-backfill | aspi-backfill | market-summary-backfill | "
            "ml-experiment | "
            "ml-forecast | ml-transfer | ml-harden | ml-diagnose | "
            "ml-iterate | ml-precision90 | ml-hpe | ml-forecast-unified | "
            "ml-always-on | ml-score-outcomes | ml-backfill-outcomes | "
            "ml-loop-nightly | ml-loop-retrain | ml-loop-research"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "tick: ignore market hours; "
            "path-backfill/hybrid-backfill/sector-backfill/notices-backfill: "
            "run even if flag off"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="For drain-* / path-backfill / hybrid-backfill: max rows/symbols (default 20)",
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
    parser.add_argument(
        "--horizons",
        type=str,
        default="1,5",
        help="For ml-experiment/ml-transfer/ml-harden: comma-separated horizons (default 1,5)",
    )
    parser.add_argument(
        "--panel",
        type=str,
        default="data/transfer_ohlcv/panel_daily.csv",
        help="For ml-transfer: path to foreign OHLCV CSV panel",
    )
    parser.add_argument(
        "--events",
        action="store_true",
        help="For ml-always-on: append disclosure/notice features and compare to baseline",
    )
    parser.add_argument(
        "--sector-rs",
        action="store_true",
        help="For ml-always-on: fill sector relative-strength features",
    )
    parser.add_argument(
        "--aspi",
        action="store_true",
        help="For ml-always-on: join ASPI daily regime from POST /chartData",
    )
    parser.add_argument(
        "--financials",
        action="store_true",
        help="For ml-always-on: join quarterly/annual filing-date features from POST /financials",
    )
    parser.add_argument(
        "--yoy",
        action="store_true",
        help="For ml-always-on: join extracted filing YoY deltas (requires drain-metrics)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="hpe_with_fallback",
        help=(
            "For ml-forecast-unified: hpe_only | hpe_with_fallback | "
            "always_on | gated | gated_p90"
        ),
    )
    args = parser.parse_args(argv)
    if args.force and args.command not in (
        "tick",
        "path-backfill",
        "hybrid-backfill",
        "sector-backfill",
        "notices-backfill",
        "ml-forecast",
        "ml-hpe",
        "ml-forecast-unified",
        "disclosures-backfill",
        "financials-backfill",
        "aspi-backfill",
        "ml-loop-nightly",
        "ml-loop-retrain",
        "ml-loop-research",
    ):
        parser.error(
            "--force is only valid for tick, path-backfill, hybrid-backfill, "
            "sector-backfill, notices-backfill, disclosures-backfill, "
            "financials-backfill, aspi-backfill, ml-forecast, ml-hpe, "
            "ml-forecast-unified, ml-loop-nightly, ml-loop-retrain, "
            "or ml-loop-research"
        )
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

    if args.command == "drain-briefs-local":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else 50

        async def _local_briefs() -> None:
            from chime.briefs.local_fill import fill_pending_briefs_local

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await fill_pending_briefs_local(
                    storage=storage,
                    limit=limit,
                    extract_ok_only=True,
                )
                print(
                    "drain-briefs-local: "
                    f"examined={result.examined} ready={result.ready} "
                    f"skipped={result.skipped} errors={result.errors}"
                )
            finally:
                await storage.close()

        asyncio.run(_local_briefs())
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

    if args.command == "hybrid-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else None

        async def _hybrid_bf() -> None:
            from chime.hybrid_backfill import run_hybrid_backfill

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_hybrid_backfill(
                    settings=settings,
                    storage=storage,
                    force=args.force,
                    limit=limit,
                )
                print(
                    "hybrid-backfill: "
                    f"targeted={result.symbols_targeted} "
                    f"ok={result.symbols_ok} "
                    f"skipped={result.symbols_skipped} "
                    f"failed={result.symbols_failed} "
                    f"bars={result.bars_upserted} "
                    f"yahoo_kept={result.yahoo_bars_kept} "
                    f"cse_copied={result.cse_bars_copied}"
                )
            finally:
                await storage.close()

        asyncio.run(_hybrid_bf())
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

    if args.command == "notices-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _notices_bf() -> None:
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
                result = await run_notices_backfill(
                    settings=settings,
                    storage=storage,
                    cse=cse,
                    force=args.force,
                )
                print(
                    "notices-backfill: "
                    f"fetched={result.fetched} "
                    f"persisted={result.persisted} "
                    f"resolved={result.resolved_symbols} "
                    f"failed={result.failed}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_notices_bf())
        return

    if args.command == "score-signals":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else None

        async def _score() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_signal_score_job(
                    storage=storage,
                    limit=limit,
                    ml_forecast=settings.ml_forecast_enabled,
                )
                print(
                    "score-signals: "
                    f"targeted={result.symbols_targeted} "
                    f"scored={result.symbols_scored} "
                    f"skipped={result.symbols_skipped} "
                    f"forecast_pts={result.forecasts_written} "
                    f"model={result.model_version} "
                    f"ml_forecast={int(settings.ml_forecast_enabled)}"
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

    if args.command == "ml-experiment":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = (
            args.limit
            if isinstance(args.limit, int) and args.limit > 0
            else None
        )
        # Default argparse limit is 20 — treat 20 as "full board" unless user
        # passed an explicit smaller smoke size via env? Better: 0 means all.
        # For ml-experiment, --limit 0 or omitted-full: use None when limit==20
        # and user didn't care — actually plan says full board. Use:
        # --limit default stays 20 for other cmds; for ml, if limit is default
        # 20, run ALL (None). Explicit --limit N for smoke.
        raw_horizons = args.horizons if isinstance(args.horizons, str) else "1,5"
        horizons: list[int] = []
        for part in raw_horizons.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                h = int(part)
            except ValueError:
                continue
            if h >= 1:
                horizons.append(h)
        if not horizons:
            horizons = [1, 5]

        async def _ml() -> None:
            from pathlib import Path

            from chime.ml.experiment import ExperimentConfig, run_ml_experiment

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                # Smoke: --limit with value other than default 20; full if 20.
                lim = None if limit == 20 else limit
                result = await run_ml_experiment(
                    storage=storage,
                    config=ExperimentConfig(
                        horizons=tuple(horizons),
                        limit_symbols=lim,
                        out_dir=Path("docs/experiments"),
                    ),
                )
                print(
                    "ml-experiment: "
                    f"decision={result.decision} "
                    f"metrics={len(result.metrics)} "
                    f"reasons={'; '.join(result.reasons) or '-'}"
                )
            finally:
                await storage.close()

        asyncio.run(_ml())
        return

    if args.command == "ml-forecast":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        if not settings.ml_forecast_enabled and not args.force:
            print(
                "ml-forecast: disabled "
                "(set ML_FORECAST_ENABLED=1 or pass --force)"
            )
            return
        limit = (
            None
            if not isinstance(args.limit, int)
            or isinstance(args.limit, bool)
            or args.limit == 20
            else args.limit
        )

        async def _ml_fc() -> None:
            from chime.ml.serve import write_ml_forecasts

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await write_ml_forecasts(
                    storage=storage,
                    limit_symbols=limit if limit and limit > 0 else None,
                )
                print(
                    "ml-forecast: "
                    f"targeted={result.symbols_targeted} "
                    f"ok={result.symbols_ok} "
                    f"skipped={result.symbols_skipped} "
                    f"points={result.points_written} "
                    f"model={result.model_version}"
                )
            finally:
                await storage.close()

        asyncio.run(_ml_fc())
        return

    if args.command == "ml-transfer":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = (
            None
            if not isinstance(args.limit, int)
            or isinstance(args.limit, bool)
            or args.limit == 20
            else args.limit
        )
        raw_horizons = args.horizons if isinstance(args.horizons, str) else "1,5"
        horizons: list[int] = []
        for part in raw_horizons.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                h = int(part)
            except ValueError:
                continue
            if h >= 1:
                horizons.append(h)
        if not horizons:
            horizons = [1, 5]

        async def _xfer() -> None:
            import json
            from datetime import UTC, datetime
            from pathlib import Path

            from chime.ml.transfer import (
                render_transfer_markdown,
                run_transfer_experiment,
            )

            panel = Path(args.panel)
            if not panel.is_file():
                print(f"ml-transfer: panel not found: {panel}")
                return
            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_transfer_experiment(
                    storage=storage,
                    panel_csv=panel,
                    horizons=tuple(horizons),
                    limit_cse_symbols=limit if limit and limit > 0 else None,
                )
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                out_dir = Path("docs/experiments")
                out_dir.mkdir(parents=True, exist_ok=True)
                out_md = out_dir / f"ml_transfer_{stamp}.md"
                out_json = out_md.with_suffix(".json")
                out_md.write_text(render_transfer_markdown(result), encoding="utf-8")
                out_json.write_text(
                    json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8"
                )
                print(
                    "ml-transfer: "
                    f"decision={result.decision} "
                    f"panel_syms={result.panel_symbols} "
                    f"cse_syms={result.cse_symbols} "
                    f"report={out_md}"
                )
                for r in result.reasons:
                    print(" ", r)
            finally:
                await storage.close()

        asyncio.run(_xfer())
        return

    if args.command == "ml-harden":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = (
            None
            if not isinstance(args.limit, int)
            or isinstance(args.limit, bool)
            or args.limit == 20
            else args.limit
        )
        raw_horizons = args.horizons if isinstance(args.horizons, str) else "1,5"
        horizons_h: list[int] = []
        for part in raw_horizons.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                h = int(part)
            except ValueError:
                continue
            if h >= 1:
                horizons_h.append(h)
        if not horizons_h:
            horizons_h = [1, 5]

        async def _harden() -> None:
            from pathlib import Path

            from chime.ml.harden import run_harden_experiment

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_harden_experiment(
                    storage=storage,
                    horizons=tuple(horizons_h),
                    limit_symbols=limit if limit and limit > 0 else None,
                    out_dir=Path("docs/experiments"),
                )
                print(
                    "ml-harden: "
                    f"decision={result.decision} "
                    f"metrics={len(result.metrics)} "
                    f"symbols={result.cse_symbols}"
                )
                for r in result.reasons:
                    print(" ", r)
            finally:
                await storage.close()

        asyncio.run(_harden())
        return

    if args.command == "ml-diagnose":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = (
            None
            if not isinstance(args.limit, int)
            or isinstance(args.limit, bool)
            or args.limit == 20
            else args.limit
        )

        async def _diagnose() -> None:
            from pathlib import Path

            from chime.ml.diagnose import run_diagnose

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_diagnose(
                    storage=storage,
                    horizon=1,
                    panel=True,
                    model_id="M1_hgb_clf",
                    limit_symbols=limit if limit and limit > 0 else None,
                    out_dir=Path("docs/experiments"),
                )
                print(
                    "ml-diagnose: "
                    f"rows={result.n_rows} "
                    f"pooled_hit={result.pooled_hit} "
                    f"mean_symbol_hit={result.mean_symbol_hit} "
                    f"ge70={result.symbols_ge_070}/{result.n_symbols}"
                )
                for r in result.recommendations[:8]:
                    print(" ", r)
            finally:
                await storage.close()

        asyncio.run(_diagnose())
        return

    if args.command == "ml-iterate":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = (
            None
            if not isinstance(args.limit, int)
            or isinstance(args.limit, bool)
            or args.limit == 20
            else args.limit
        )

        async def _iterate() -> None:
            from pathlib import Path

            from chime.ml.iterate import run_iterate

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_iterate(
                    storage=storage,
                    limit_symbols=limit if limit and limit > 0 else None,
                    out_dir=Path("docs/experiments"),
                )
                print(
                    "ml-iterate: "
                    f"target_met={result.target_met} "
                    f"best={result.best_lever} "
                    f"mean_symbol_hit={result.best_mean_symbol_hit} "
                    f"baseline={result.baseline_mean_symbol_hit}"
                )
                for r in result.recommendations:
                    print(" ", r)
            finally:
                await storage.close()

        asyncio.run(_iterate())
        return

    if args.command == "ml-precision90":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = (
            None
            if not isinstance(args.limit, int)
            or isinstance(args.limit, bool)
            or args.limit == 20
            else args.limit
        )

        async def _p90() -> None:
            from pathlib import Path

            from chime.ml.precision90 import run_precision90

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_precision90(
                    storage=storage,
                    limit_symbols=limit if limit and limit > 0 else None,
                    out_dir=Path("docs/experiments"),
                )
                print(
                    "ml-precision90: "
                    f"target_met={result.target_met} "
                    f"best={result.best_gate} "
                    f"prec={result.best_precision} "
                    f"emits={result.best_n_emits}"
                )
                for r in result.recommendations:
                    print(" ", r)
            finally:
                await storage.close()

        asyncio.run(_p90())
        return

    if args.command == "ml-hpe":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        if not settings.ml_hpe_enabled and not args.force:
            print(
                "ml-hpe: disabled "
                "(set ML_HPE_ENABLED=1 or pass --force)"
            )
            return

        async def _hpe() -> None:
            from chime.ml.hpe import run_hpe_forecast

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_hpe_forecast(
                    storage=storage, force=args.force
                )
                print(
                    "ml-hpe: "
                    f"scanned={result.symbols_scanned} "
                    f"emits={result.emits} "
                    f"points={result.points_written} "
                    f"model={result.model_version}"
                )
            finally:
                await storage.close()

        asyncio.run(_hpe())
        return

    if args.command == "ml-forecast-unified":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        mode = (
            args.mode
            if isinstance(args.mode, str)
            and args.mode
            in {
                "hpe_only",
                "hpe_with_fallback",
                "always_on",
                "gated",
                "gated_p90",
            }
            else "hpe_with_fallback"
        )

        async def _uni() -> None:
            from chime.ml.forecast_serve import run_unified_forecast

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
                result = await run_unified_forecast(
                    storage=storage, mode=mode, cse=cse
                )
                print(
                    "ml-forecast-unified: "
                    f"mode={result.mode} "
                    f"hpe_emits={result.hpe_emits} "
                    f"fallback_emits={result.fallback_emits} "
                    f"points={result.points_written}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_uni())
        return

    if args.command == "aspi-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _aspi() -> None:
            from datetime import UTC, datetime

            from chime.domain import DailyBar

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
                await storage.upsert_stock("ASPI", "All Share Price Index")
                series = await cse.fetch_index_chart(period=5)
                bars = [
                    DailyBar(
                        symbol="ASPI",
                        trade_date=d,
                        price=v,
                        high=None,
                        low=None,
                        open=None,
                        volume=None,
                        source_period=5,
                        bar_ts=datetime(d.year, d.month, d.day, 18, 30, tzinfo=UTC),
                    )
                    for d, v, _pc in series
                ]
                n = await storage.persist_daily_bars(bars) if bars else 0
                print(f"aspi-backfill: points={len(series)} upserted={n}")
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_aspi())
        return

    if args.command == "ml-score-outcomes":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _score() -> None:
            from chime.ml.outcomes import score_due_outcomes

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await score_due_outcomes(storage)
                print(
                    "ml-score-outcomes: "
                    f"examined={result.examined} scored={result.scored} "
                    f"skipped={result.skipped}"
                )
            finally:
                await storage.close()

        asyncio.run(_score())
        return

    if args.command == "ml-backfill-outcomes":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _bf_out() -> None:
            from chime.ml.backfill_outcomes import backfill_walkforward_outcomes

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await backfill_walkforward_outcomes(storage)
                print(
                    "ml-backfill-outcomes: "
                    f"rows={result.rows} folds={result.folds}"
                )
            finally:
                await storage.close()

        asyncio.run(_bf_out())
        return

    if args.command == "ml-loop-nightly":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        if not settings.ml_loop_enabled and not args.force:
            print(
                "ml-loop-nightly: disabled "
                "(set ML_LOOP_ENABLED=1 or pass --force)"
            )
            return

        async def _nightly() -> None:
            from chime.ml.loop_nightly import run_loop_nightly

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
                # B-011: accrue dailyMarketSummery (CSE only returns ~2 latest days)
                try:
                    mkt = await cse.fetch_daily_market_summary()
                    n_mkt = await storage.upsert_market_daily_summary(mkt)
                    print(f"ml-loop-nightly: market_summary_upserted={n_mkt}")
                except Exception as exc:
                    print(f"ml-loop-nightly: market_summary_failed={exc!s}"[:120])
                # B-001: accrue order-book snapshots (empty outside market hours)
                try:
                    async with storage._pool.connection() as conn:
                        sym_rows = await (
                            await conn.execute(
                                """
                                SELECT symbol FROM daily_bars
                                WHERE trade_date = (
                                    SELECT MAX(trade_date) FROM daily_bars
                                )
                                  AND volume IS NOT NULL
                                ORDER BY volume DESC NULLS LAST
                                LIMIT 25
                                """
                            )
                        ).fetchall()
                    ob_ok = 0
                    for sr in sym_rows:
                        sym = str(dict(sr).get("symbol") or "").strip().upper()
                        if not sym:
                            continue
                        book = await cse.fetch_order_book(sym)
                        if book is not None:
                            await storage.persist_order_book(book)
                            ob_ok += 1
                    print(
                        f"ml-loop-nightly: order_book_ok={ob_ok}/"
                        f"{len(sym_rows)}"
                    )
                except Exception as exc:
                    print(f"ml-loop-nightly: order_book_failed={exc!s}"[:120])
                result = await run_loop_nightly(storage)
                print(
                    "ml-loop-nightly: "
                    f"emitted={result.emitted} scored={result.scored} "
                    f"alerts={list(result.drift_alerts) or '-'} "
                    f"scoreboard={result.scoreboard_path}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_nightly())
        return

    if args.command == "market-summary-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _mkt() -> None:
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
                rows = await cse.fetch_daily_market_summary()
                n = await storage.upsert_market_daily_summary(rows)
                print(f"market-summary-backfill: fetched={len(rows)} upserted={n}")
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_mkt())
        return

    if args.command == "ml-loop-research":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        if not settings.ml_loop_enabled and not args.force:
            print(
                "ml-loop-research: disabled "
                "(set ML_LOOP_ENABLED=1 or pass --force)"
            )
            return

        async def _research() -> None:
            from chime.ml.loop_research import run_loop_research

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                results = await run_loop_research(storage)
                for r in results:
                    print(
                        "ml-loop-research: "
                        f"{r.experiment_id} {r.status} "
                        f"mean={r.mean_symbol_hit} "
                        f"gated={r.gated_hit_055} cov={r.gated_cov_055} "
                        f"delta={r.delta_vs_baseline}"
                    )
            finally:
                await storage.close()

        asyncio.run(_research())
        return

    if args.command == "ml-loop-retrain":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        if not settings.ml_loop_enabled and not args.force:
            print(
                "ml-loop-retrain: disabled "
                "(set ML_LOOP_ENABLED=1 or pass --force)"
            )
            return

        async def _retrain() -> None:
            from chime.ml.loop_retrain import run_loop_retrain
            from chime.ml.registry import get_champion

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                champ = await get_champion(storage)
                result = await run_loop_retrain(
                    storage, force_promote_first=champ is None
                )
                print(
                    "ml-loop-retrain: "
                    f"challenger={result.challenger_id} "
                    f"promoted={result.promoted} "
                    f"challenger_hit={result.challenger_hit} "
                    f"champion_hit={result.champion_hit}"
                )
                for r in result.reasons:
                    print(" ", r)
            finally:
                await storage.close()

        asyncio.run(_retrain())
        return

    if args.command == "disclosures-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else None

        async def _disc_bf() -> None:
            from chime.disclosures_backfill import run_disclosures_backfill

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
                result = await run_disclosures_backfill(
                    settings=settings,
                    storage=storage,
                    cse=cse,
                    limit=limit,
                    force=args.force,
                )
                print(
                    "disclosures-backfill: "
                    f"targeted={result.symbols_targeted} "
                    f"ok={result.symbols_ok} "
                    f"failed={result.symbols_failed} "
                    f"upserted={result.disclosures_upserted}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_disc_bf())
        return

    if args.command == "financials-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else None

        async def _fin_bf() -> None:
            from chime.financials_backfill import run_financials_backfill

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
                result = await run_financials_backfill(
                    settings=settings,
                    storage=storage,
                    cse=cse,
                    limit=limit,
                    force=args.force,
                )
                print(
                    "financials-backfill: "
                    f"targeted={result.symbols_targeted} "
                    f"ok={result.symbols_ok} "
                    f"failed={result.symbols_failed} "
                    f"upserted={result.disclosures_upserted}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_fin_bf())
        return

    if args.command == "ml-always-on":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = (
            None
            if not isinstance(args.limit, int)
            or isinstance(args.limit, bool)
            or args.limit == 20
            else args.limit
        )
        use_events = bool(args.events)
        use_sector_rs = bool(getattr(args, "sector_rs", False))
        use_aspi = bool(getattr(args, "aspi", False))
        use_financials = bool(getattr(args, "financials", False))
        use_yoy = bool(getattr(args, "yoy", False))

        async def _ao() -> None:
            from pathlib import Path

            from chime.ml.always_on import run_always_on

            storage = Storage(settings.database_url)
            await storage.open()
            cse = None
            if use_aspi or use_financials:
                cse = CSEClient(
                    base_url=settings.cse_base_url,
                    timeout=settings.http_timeout_seconds,
                    fail_max=settings.circuit_fail_max,
                    reset_timeout=settings.circuit_reset_seconds,
                    min_interval_seconds=settings.cse_min_interval_seconds,
                )
            try:
                baseline_mean = None
                needs_delta = (
                    use_events
                    or use_sector_rs
                    or use_aspi
                    or use_financials
                    or use_yoy
                )
                if needs_delta:
                    base = await run_always_on(
                        storage=storage,
                        lever="baseline_cs_lmt_bag",
                        use_events=False,
                        use_sector_rs=False,
                        use_aspi=False,
                        use_financials=False,
                        use_yoy=False,
                        limit_symbols=limit if limit and limit > 0 else None,
                        out_dir=Path("docs/experiments"),
                    )
                    baseline_mean = base.mean_symbol_hit
                    print(
                        "ml-always-on baseline: "
                        f"mean_symbol_hit={base.mean_symbol_hit}"
                    )
                parts = []
                if use_aspi:
                    parts.append("aspi")
                if use_financials:
                    parts.append("fin")
                if use_yoy:
                    parts.append("yoy")
                if use_sector_rs:
                    parts.append("sector_rs")
                if use_events:
                    parts.append("events")
                lever = (
                    "_".join(parts) + "_cs_lmt_bag" if parts else "baseline_cs_lmt_bag"
                )
                result = await run_always_on(
                    storage=storage,
                    lever=lever,
                    use_events=use_events,
                    use_sector_rs=use_sector_rs,
                    use_aspi=use_aspi,
                    use_financials=use_financials,
                    use_yoy=use_yoy,
                    cse=cse,
                    baseline_mean=baseline_mean,
                    limit_symbols=limit if limit and limit > 0 else None,
                    out_dir=Path("docs/experiments"),
                )
                print(
                    "ml-always-on: "
                    f"lever={result.lever} "
                    f"mean_symbol_hit={result.mean_symbol_hit} "
                    f"pooled={result.pooled_hit} "
                    f"ge70={result.symbols_ge_070}/{result.n_symbols} "
                    f"delta={result.delta_vs_baseline} "
                    f"keep={result.keep} "
                    f"extras={result.extras}"
                )
            finally:
                if cse is not None:
                    await cse.aclose()
                await storage.close()

        asyncio.run(_ao())
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
