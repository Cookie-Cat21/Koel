"""Koel entrypoint: bot, poller, migrate, or both."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import inspect
import signal
import sys

from telegram import Bot

from koel.adapters.cse import CSEClient
from koel.bot import build_application
from koel.config import Settings
from koel.drain import (
    drain_briefs,
    drain_graph,
    drain_metrics,
    drain_pdfs,
    drain_people,
)
from koel.graph.directors_sync import run_directors_sync
from koel.health import HealthState, brief_queue_health_hint, start_health_server
from koel.issuer_profile_backfill import run_issuer_profile_backfill
from koel.logging_setup import configure_logging, get_logger
from koel.migrate import apply_migrations
from koel.notices_backfill import run_notices_backfill
from koel.notify import SendResult, send_message
from koel.path_backfill import run_path_backfill
from koel.poller import Poller, run_poller_forever
from koel.sector_backfill import run_sector_backfill
from koel.signals import run_signal_score_job
from koel.storage import Storage
from koel.ws_ingest import run_ws_ingest

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

    async def send(
        chat_id: int, text: str, *, reply_markup: object | None = None
    ) -> SendResult:
        # Lock is released before Telegram I/O (CORE-004) — honor RetryAfter.
        return await send_message(
            bot, chat_id, text, block_on_retry_after=True, reply_markup=reply_markup
        )

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
    ws_task: asyncio.Task[dict[str, object]] | None = None

    try:
        if settings.cse_ws_enabled:
            ws_task = asyncio.create_task(
                run_ws_ingest(settings, storage, force=False),
                name="cse-ws-ingest",
            )
            log.info("cse_ws_sidecar_started")
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
        if ws_task is not None:
            ws_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ws_task
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

    async def send(
        chat_id: int, text: str, *, reply_markup: object | None = None
    ) -> SendResult:
        # Lock is released before Telegram I/O (CORE-004) — honor RetryAfter.
        return await send_message(
            bot, chat_id, text, block_on_retry_after=True, reply_markup=reply_markup
        )

    health = HealthState()
    server = start_health_server(settings.health_host, settings.health_port, health)
    ws_task: asyncio.Task[dict[str, object]] | None = None
    try:
        if settings.cse_ws_enabled:
            ws_task = asyncio.create_task(
                run_ws_ingest(settings, storage, force=False),
                name="cse-ws-ingest",
            )
            log.info("cse_ws_sidecar_started")
        await run_poller_forever(settings, storage, cse, send, health=health)
    finally:
        if ws_task is not None:
            ws_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ws_task
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


def _cli_limit(raw: object, *, default: int | None = None) -> int | None:
    """Positive int limit from argparse, else ``default`` (often None = all)."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        return default
    if raw > 0:
        return raw
    return default


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="koel", description="CSE Telegram alerting")
    parser.add_argument(
        "command",
        choices=[
            "bot",
            "poller",
            "both",
            "migrate",
            "tick",
            "ws",
            "drain-pdfs",
            "drain-briefs",
            "drain-briefs-local",
            "drain-metrics",
            "drain-graph",
            "drain-people",
            "directors-backfill",
            "path-backfill",
            "intraday-backfill",
            "hybrid-backfill",
            "score-signals",
            "eval-signals",
            "sector-backfill",
            "issuer-profile-backfill",
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
            "ml-ltr-dual",
            "ml-ltr-ship",
            "disclosures-backfill",
            "financials-backfill",
            "aspi-backfill",
            "appetite-backfill",
            "corporate-actions-backfill",
            "ml-score-outcomes",
            "ml-backfill-outcomes",
            "ml-loop-nightly",
            "ml-loop-retrain",
            "ml-loop-research",
            "market-summary-backfill",
            "macro-tick",
            "digest",
        ],
        help=(
            "bot | poller | both | migrate | tick | ws | digest | "
            "drain-pdfs | drain-briefs | drain-briefs-local | drain-metrics | "
            "drain-graph | drain-people | directors-backfill | "
            "path-backfill | intraday-backfill | hybrid-backfill | "
            "score-signals | eval-signals | "
            "sector-backfill | issuer-profile-backfill | notices-backfill | "
            "disclosures-backfill | "
            "financials-backfill | aspi-backfill | appetite-backfill | "
            "corporate-actions-backfill | "
            "market-summary-backfill | macro-tick | "
            "ml-experiment | "
            "ml-forecast | ml-transfer | ml-harden | ml-diagnose | "
            "ml-iterate | ml-precision90 | ml-hpe | ml-forecast-unified | "
            "ml-always-on | ml-ltr-dual | ml-ltr-ship | ml-score-outcomes | "
            "ml-backfill-outcomes | "
            "ml-loop-nightly | ml-loop-retrain | ml-loop-research"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "tick/ws: ignore market hours; "
            "digest: ignore 14:30–16:00 SLT window; "
            "path-backfill/intraday-backfill/hybrid-backfill/"
            "sector-backfill/issuer-profile-backfill/notices-backfill/"
            "directors-backfill/corporate-actions-backfill/macro-tick: "
            "run even if flag off"
        ),
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="ws: run live STOMP ingest for N seconds then exit (smoke test)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help=(
            "For drain-* / path-backfill / intraday-backfill / hybrid-backfill: "
            "max rows/symbols (default 20)"
        ),
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help=(
            "For score-signals: YYYY-MM-DD tip date — truncate daily bars and "
            "write a historical leaderboard snapshot (rank Δ needs ≥2 as_of days)"
        ),
    )
    parser.add_argument(
        "--all-symbols",
        action="store_true",
        help=(
            "For drain-pdfs/drain-metrics/drain-graph/drain-people: "
            "include non-watchlist symbols. "
            "For directors-backfill: sync all *.N0000 stocks (not only top mcap)."
        ),
    )
    parser.add_argument(
        "--period",
        type=int,
        default=None,
        help="For path-backfill: CSE chart period 2–5 (default PATH_BACKFILL_PERIOD/5)",
    )
    parser.add_argument(
        "--model-prefix",
        type=str,
        default=None,
        help=(
            "For ml-score-outcomes: only score forecast_outcomes whose model_id "
            "starts with this prefix (e.g. shadow)"
        ),
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="For path-backfill / intraday-backfill: skip tradeSummary id seed",
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
            "hpe_with_ltr_fallback | always_on | gated | gated_p90 | gated_ltr"
        ),
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help=(
            "For appetite-backfill: read hybrid_daily_bars and store "
            "source=hybrid_research"
        ),
    )
    args = parser.parse_args(argv)
    limit: int | None = None  # CLI per-command; rebound below
    if args.force and args.command not in (
        "tick",
        "ws",
        "digest",
        "path-backfill",
        "intraday-backfill",
        "hybrid-backfill",
        "sector-backfill",
        "issuer-profile-backfill",
        "notices-backfill",
        "directors-backfill",
        "ml-forecast",
        "ml-hpe",
        "ml-forecast-unified",
        "disclosures-backfill",
        "financials-backfill",
        "aspi-backfill",
        "appetite-backfill",
        "corporate-actions-backfill",
        "macro-tick",
        "ml-loop-nightly",
        "ml-loop-retrain",
        "ml-loop-research",
        "ml-ltr-ship",
    ):
        parser.error(
            "--force is only valid for tick, ws, digest, path-backfill, "
            "intraday-backfill, hybrid-backfill, sector-backfill, "
            "issuer-profile-backfill, notices-backfill, "
            "directors-backfill, disclosures-backfill, financials-backfill, "
            "aspi-backfill, appetite-backfill, corporate-actions-backfill, "
            "macro-tick, ml-forecast, ml-hpe, "
            "ml-forecast-unified, ml-loop-nightly, ml-loop-retrain, "
            "ml-loop-research, or ml-ltr-ship"
        )
    if args.seconds is not None and args.command != "ws":
        parser.error("--seconds is only valid for ws")
    if args.period is not None and args.command != "path-backfill":
        parser.error("--period is only valid for path-backfill")
    if args.no_seed and args.command not in ("path-backfill", "intraday-backfill"):
        parser.error("--no-seed is only valid for path-backfill / intraday-backfill")
    if args.hybrid and args.command != "appetite-backfill":
        parser.error("--hybrid is only valid for appetite-backfill")

    if args.command == "migrate":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        applied = apply_migrations(settings.database_url)
        print("Applied:", ", ".join(applied) if applied else "(none)")
        return

    if args.command in (
        "drain-pdfs",
        "drain-briefs",
        "drain-metrics",
        "drain-graph",
        "drain-people",
    ):
        configure_logging()
        settings = Settings.from_env(require_token=False)
        drain_limit: int = _cli_limit(args.limit, default=20) or 20
        watched_only = not args.all_symbols

        async def _drain() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            try:
                if args.command == "drain-briefs":
                    result = await drain_briefs(storage=storage, limit=drain_limit)
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
                            limit=drain_limit,
                            watched_only=watched_only,
                        )
                    finally:
                        await cse.aclose()
                elif args.command == "drain-graph":
                    result = await drain_graph(
                        storage=storage,
                        limit=drain_limit,
                        watched_only=watched_only,
                    )
                elif args.command == "drain-people":
                    result = await drain_people(
                        storage=storage,
                        limit=drain_limit,
                        watched_only=watched_only,
                    )
                else:
                    result = await drain_metrics(
                        storage=storage,
                        limit=drain_limit,
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
        # --limit 0 ⇒ board-wide batch (local fill cap); default 200.
        local_limit: int
        if isinstance(args.limit, int) and not isinstance(args.limit, bool):
            local_limit = 2000 if args.limit <= 0 else args.limit
        else:
            local_limit = 200

        async def _local_briefs() -> None:
            from koel.briefs.local_fill import fill_pending_briefs_local

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                # First-run: fill skipped + title-only (no Groq). Metrics-only
                # mode remains available later via extract_ok_only=True.
                result = await fill_pending_briefs_local(
                    storage=storage,
                    limit=local_limit,
                    extract_ok_only=False,
                    include_skipped=True,
                    require_pdf=False,
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
        limit = _cli_limit(args.limit)

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

    if args.command == "intraday-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = _cli_limit(args.limit)

        async def _intraday_bf() -> None:
            from koel.intraday_backfill import run_intraday_backfill

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
                result = await run_intraday_backfill(
                    settings=settings,
                    storage=storage,
                    cse=cse,
                    limit=limit,
                    seed_ids=not args.no_seed,
                    force=args.force,
                )
                print(
                    "intraday-backfill: "
                    f"targeted={result.symbols_targeted} "
                    f"ok={result.symbols_ok} "
                    f"skipped={result.symbols_skipped} "
                    f"failed={result.symbols_failed} "
                    f"ticks={result.ticks_inserted}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_intraday_bf())
        return

    if args.command == "hybrid-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = _cli_limit(args.limit)

        async def _hybrid_bf() -> None:
            from koel.hybrid_backfill import run_hybrid_backfill

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
        limit = _cli_limit(args.limit)

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
            exit_code = 0
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
                for issue in result.issues:
                    print(f"sector-backfill issue: {issue}", file=sys.stderr)
                if result.symbols_failed > 0:
                    exit_code = 1
            finally:
                await cse.aclose()
                await storage.close()
            if exit_code:
                raise SystemExit(exit_code)

        asyncio.run(_sector_bf())
        return

    if args.command == "issuer-profile-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = _cli_limit(args.limit)

        async def _issuer_bf() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            cse = CSEClient(
                base_url=settings.cse_base_url,
                timeout=settings.http_timeout_seconds,
                fail_max=settings.circuit_fail_max,
                reset_timeout=settings.circuit_reset_seconds,
                min_interval_seconds=settings.cse_min_interval_seconds,
            )
            exit_code = 0
            try:
                result = await run_issuer_profile_backfill(
                    settings=settings,
                    storage=storage,
                    cse=cse,
                    limit=limit,
                    force=args.force,
                    only_missing=not args.all_symbols,
                )
                print(
                    "issuer-profile-backfill: "
                    f"targeted={result.symbols_targeted} "
                    f"updated={result.symbols_updated} "
                    f"skipped={result.symbols_skipped} "
                    f"failed={result.symbols_failed}"
                )
                for issue in result.issues:
                    print(
                        f"issuer-profile-backfill issue: {issue}",
                        file=sys.stderr,
                    )
                if result.symbols_failed > 0:
                    exit_code = 1
            finally:
                await cse.aclose()
                await storage.close()
            if exit_code:
                raise SystemExit(exit_code)

        asyncio.run(_issuer_bf())
        return

    if args.command == "directors-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = args.limit if isinstance(args.limit, int) and args.limit > 0 else 80
        if args.all_symbols:
            limit = (
                args.limit
                if isinstance(args.limit, int) and args.limit > 0
                else 500
            )

        async def _directors_bf() -> None:
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
                result = await run_directors_sync(
                    settings=settings,
                    storage=storage,
                    cse=cse,
                    limit=limit,
                    force=args.force,
                    top_by_mcap=not args.all_symbols,
                )
                print(
                    "directors-backfill: "
                    f"targeted={result.symbols_targeted} "
                    f"updated={result.symbols_updated} "
                    f"skipped={result.symbols_skipped} "
                    f"failed={result.symbols_failed} "
                    f"seats={result.seats_written} "
                    f"roles={result.roles_written}"
                )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_directors_bf())
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
        limit = _cli_limit(args.limit)
        as_of_raw = args.as_of if isinstance(args.as_of, str) else None
        as_of_day = None
        if as_of_raw and as_of_raw.strip():
            from datetime import date as _date

            try:
                as_of_day = _date.fromisoformat(as_of_raw.strip())
            except ValueError:
                print(f"score-signals: invalid --as-of {as_of_raw!r} (want YYYY-MM-DD)")
                return

        async def _score() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_signal_score_job(
                    storage=storage,
                    limit=limit,
                    ml_forecast=settings.ml_forecast_enabled,
                    as_of=as_of_day,
                )
                print(
                    "score-signals: "
                    f"targeted={result.symbols_targeted} "
                    f"scored={result.symbols_scored} "
                    f"skipped={result.symbols_skipped} "
                    f"forecast_pts={result.forecasts_written} "
                    f"model={result.model_version} "
                    f"ml_forecast={int(settings.ml_forecast_enabled)} "
                    f"as_of={result.as_of or 'latest'}"
                )
            finally:
                await storage.close()

        asyncio.run(_score())
        return

    if args.command == "eval-signals":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = _cli_limit(args.limit, default=40) or 40

        async def _eval() -> None:
            from koel.signals.eval import evaluate_walk_forward

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
        limit = _cli_limit(args.limit)
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

            from koel.ml.experiment import ExperimentConfig, run_ml_experiment

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
        limit = _cli_limit(args.limit) if _cli_limit(args.limit) not in (None, 20) else None

        async def _ml_fc() -> None:
            from koel.ml.serve import write_ml_forecasts

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
        limit = _cli_limit(args.limit) if _cli_limit(args.limit) not in (None, 20) else None
        raw_horizons = args.horizons if isinstance(args.horizons, str) else "1,5"
        horizons = []
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

            from koel.ml.transfer import (
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
        limit = _cli_limit(args.limit) if _cli_limit(args.limit) not in (None, 20) else None
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

            from koel.ml.harden import run_harden_experiment

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

    if args.command == "ml-ltr-dual":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = _cli_limit(args.limit) if _cli_limit(args.limit) not in (None, 20) else None

        async def _ltr_dual() -> None:
            from pathlib import Path

            from koel.ml.ltr_dual import run_ltr_dual_experiment

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_ltr_dual_experiment(
                    storage=storage,
                    limit_symbols=limit if limit and limit > 0 else None,
                    out_dir=Path("docs/experiments"),
                )
                print(
                    "ml-ltr-dual: "
                    f"decision={result.decision} "
                    f"metrics={len(result.metrics)} "
                    f"symbols={result.cse_symbols} bars={result.bars}"
                )
                for r in result.reasons:
                    print(" ", r)
            finally:
                await storage.close()

        asyncio.run(_ltr_dual())
        return

    if args.command == "ml-ltr-ship":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _ltr_ship() -> None:
            from koel.ml.ltr_serve import ship_ltr_serve

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
                result = await ship_ltr_serve(
                    storage,
                    cse=cse,
                    force_promote=bool(args.force),
                    write_forecasts=True,
                )
                print(
                    "ml-ltr-ship: "
                    f"promoted={int(result.promoted)} "
                    f"challenger={result.challenger_id} "
                    f"emits={result.emits} points={result.points_written}"
                )
                if result.metrics:
                    print(
                        "  "
                        f"rank_ic={result.metrics.mean_rank_ic} "
                        f"gated_hit={result.metrics.gated_hit} "
                        f"vol_ic={result.metrics.vol_rank_ic} "
                        f"ranker={result.metrics.ranker}"
                    )
                for r in result.reasons:
                    print(" ", r)
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_ltr_ship())
        return

    if args.command == "ml-diagnose":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        limit = _cli_limit(args.limit) if _cli_limit(args.limit) not in (None, 20) else None

        async def _diagnose() -> None:
            from pathlib import Path

            from koel.ml.diagnose import run_diagnose

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
        limit = _cli_limit(args.limit) if _cli_limit(args.limit) not in (None, 20) else None

        async def _iterate() -> None:
            from pathlib import Path

            from koel.ml.iterate import run_iterate

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
        limit = _cli_limit(args.limit) if _cli_limit(args.limit) not in (None, 20) else None

        async def _p90() -> None:
            from pathlib import Path

            from koel.ml.precision90 import run_precision90

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
            from koel.ml.hpe import run_hpe_forecast

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
        allowed_modes = {
            "hpe_only",
            "hpe_with_fallback",
            "hpe_with_ltr_fallback",
            "always_on",
            "gated",
            "gated_p90",
            "gated_ltr",
        }
        default_mode = (
            "hpe_with_ltr_fallback"
            if settings.ml_ltr_serve
            else "hpe_with_fallback"
        )
        mode = (
            args.mode
            if isinstance(args.mode, str) and args.mode in allowed_modes
            else default_mode
        )

        async def _uni() -> None:
            from koel.ml.forecast_serve import run_unified_forecast

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

            from koel.domain import DailyBar

            # chartId=1 → ASPI (sectorId 1); chartId=40 → S&P SL20 (sectorId 40).
            indexes = (
                ("ASPI", "All Share Price Index", 1),
                ("SNP_SL20", "S&P Sri Lanka 20", 40),
            )

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
                for symbol, name, chart_id in indexes:
                    await storage.upsert_stock(symbol, name)
                    series = await cse.fetch_index_chart(
                        chart_id=chart_id, period=5
                    )
                    bars = [
                        DailyBar(
                            symbol=symbol,
                            trade_date=d,
                            price=v,
                            high=None,
                            low=None,
                            open=None,
                            volume=None,
                            source_period=5,
                            bar_ts=datetime(
                                d.year, d.month, d.day, 18, 30, tzinfo=UTC
                            ),
                        )
                        for d, v, _pc in series
                    ]
                    n = await storage.persist_daily_bars(bars) if bars else 0
                    print(
                        f"aspi-backfill: {symbol} chartId={chart_id} "
                        f"points={len(series)} upserted={n}"
                    )
            finally:
                await cse.aclose()
                await storage.close()

        asyncio.run(_aspi())
        return

    if args.command == "ml-score-outcomes":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _score() -> None:
            from koel.ml.outcomes import score_due_outcomes

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                # Default CLI --limit is 20 (drain-* oriented). Treat that as
                # "unspecified" for scoring and use the scorer default (5000).
                score_limit = (
                    args.limit
                    if isinstance(args.limit, int)
                    and not isinstance(args.limit, bool)
                    and args.limit > 20
                    else 5000
                )
                result = await score_due_outcomes(
                    storage,
                    limit=score_limit,
                    model_id_prefix=args.model_prefix,
                )
                print(
                    "ml-score-outcomes: "
                    f"examined={result.examined} scored={result.scored} "
                    f"skipped={result.skipped}"
                    + (
                        f" prefix={args.model_prefix}"
                        if args.model_prefix
                        else ""
                    )
                )
            finally:
                await storage.close()

        asyncio.run(_score())
        return

    if args.command == "ml-backfill-outcomes":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _bf_out() -> None:
            from koel.ml.backfill_outcomes import backfill_walkforward_outcomes

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
            from koel.ml.loop_nightly import run_loop_nightly

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

    if args.command == "macro-tick":
        configure_logging()
        settings = Settings.from_env(require_token=False)

        async def _macro() -> None:
            from koel.macro_ingest import run_macro_tick

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_macro_tick(
                    storage, settings, force=args.force
                )
                print(f"macro-tick: {result}")
            finally:
                await storage.close()

        asyncio.run(_macro())
        return

    if args.command == "digest":
        configure_logging()
        settings = Settings.from_env(require_token=True)

        async def _digest() -> None:
            from koel.digest import run_eod_digest

            storage = Storage(settings.database_url)
            await storage.open()
            bot = Bot(settings.telegram_bot_token)

            async def send(
                chat_id: int, text: str, *, reply_markup: object | None = None
            ) -> SendResult:
                return await send_message(
                    bot,
                    chat_id,
                    text,
                    block_on_retry_after=True,
                    reply_markup=reply_markup,
                )

            try:
                result = await run_eod_digest(
                    storage, send, force=args.force
                )
                print(
                    "digest: "
                    f"candidates={result.candidates} sent={result.sent} "
                    f"skipped={result.skipped} errors={result.errors} "
                    f"outside_window={int(result.outside_window)}"
                )
            finally:
                await storage.close()

        asyncio.run(_digest())
        return

    if args.command == "appetite-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        appetite_source = "hybrid_research" if args.hybrid else "cse"

        async def _appetite_bf() -> None:
            from koel.appetite import backfill_appetite

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await backfill_appetite(
                    storage,
                    source=appetite_source,
                    force=args.force,
                )
                rows = await storage.list_market_appetite_daily(source=appetite_source)
                dates = [r["trade_date"] for r in rows if r.get("trade_date") is not None]
                print(
                    "appetite-backfill: "
                    f"source={result.source} "
                    f"targeted={result.dates_targeted} "
                    f"upserted={result.dates_upserted} "
                    f"skipped={result.dates_skipped} "
                    f"rows={len(rows)} "
                    f"min_date={min(dates) if dates else None} "
                    f"max_date={max(dates) if dates else None}"
                )
            finally:
                await storage.close()

        asyncio.run(_appetite_bf())
        return

    if args.command == "corporate-actions-backfill":
        configure_logging()
        settings = Settings.from_env(require_token=False)
        # Default argparse --limit 20 is a smoke size; pass a large limit for full scan.
        limit = _cli_limit(args.limit)

        async def _ca_bf() -> None:
            from koel.corporate_actions_backfill import run_corporate_actions_backfill

            storage = Storage(settings.database_url)
            await storage.open()
            try:
                result = await run_corporate_actions_backfill(
                    storage=storage,
                    limit=limit,
                    force=args.force,
                )
                print(
                    "corporate-actions-backfill: "
                    f"disclosures_scanned={result.disclosures_scanned} "
                    f"disclosures_upserted={result.disclosures_upserted} "
                    f"symbols_scanned={result.symbols_scanned} "
                    f"price_hits={result.price_hits} "
                    f"price_upserted={result.price_upserted} "
                    f"errors={result.errors}"
                )
            finally:
                await storage.close()

        asyncio.run(_ca_bf())
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
            from koel.ml.loop_research import run_loop_research

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
            from koel.ml.loop_retrain import run_loop_retrain
            from koel.ml.registry import get_champion

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
        limit = _cli_limit(args.limit)

        async def _disc_bf() -> None:
            from koel.disclosures_backfill import run_disclosures_backfill

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
        limit = _cli_limit(args.limit)

        async def _fin_bf() -> None:
            from koel.financials_backfill import run_financials_backfill

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
        limit = _cli_limit(args.limit) if _cli_limit(args.limit) not in (None, 20) else None
        use_events = bool(args.events)
        use_sector_rs = bool(getattr(args, "sector_rs", False))
        use_aspi = bool(getattr(args, "aspi", False))
        use_financials = bool(getattr(args, "financials", False))
        use_yoy = bool(getattr(args, "yoy", False))

        async def _ao() -> None:
            from pathlib import Path

            from koel.ml.always_on import run_always_on

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
    elif args.command == "ws":

        async def _ws() -> None:
            storage = Storage(settings.database_url)
            await storage.open()
            try:
                stats = await run_ws_ingest(
                    settings,
                    storage,
                    seconds=args.seconds,
                    force=args.force or args.seconds is not None,
                )
                print(
                    "WS ingest: "
                    f"price_rows={stats.get('price_rows')} "
                    f"index_rows={stats.get('index_rows')} "
                    f"batches={stats.get('batches')} "
                    f"messages={stats.get('messages')} "
                    f"error={stats.get('last_error')}"
                )
            finally:
                await storage.close()

        asyncio.run(_ws())
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

            async def send(
                chat_id: int, text: str, *, reply_markup: object | None = None
            ) -> SendResult:
                return await send_message(
                    bot,
                    chat_id,
                    text,
                    block_on_retry_after=True,
                    reply_markup=reply_markup,
                )

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
