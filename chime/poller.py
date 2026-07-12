"""Market-hours polling loop (09:30–14:30 Asia/Colombo, weekdays).

Fetches price + disclosure data via adapters, stores every snapshot, evaluates
rules, claims alerts idempotently, and dispatches Telegram sends.

CORE-004: advisory lock covers fetch/store/evaluate/claim/disarm only.
Telegram sends and disclosure inter-symbol sleeps run after unlock.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import random
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from chime.adapters.cse import CSEClient, legacy_pdf_urls_by_id
from chime.circuit import CircuitOpenError
from chime.config import Settings
from chime.domain import (
    AlertEvent,
    Disclosure,
    PriceSnapshot,
    format_alert_message,
    format_dead_letter_notify,
)
from chime.logging_setup import get_logger
from chime.notify import SendResult
from chime.rules import evaluate_disclosure_rules, evaluate_price_rules, filter_fireable
from chime.storage import Storage

log = get_logger(__name__)

# bool kept for test AsyncMocks; production send returns SendResult.
SendFunc = Callable[[int, str], Awaitable[SendResult | bool]]
POLL_LOCK_ID = 4_201_337
# After this many failed Telegram sends, stop retrying (message_sent stays false).
MAX_SEND_ATTEMPTS = 5
# After this many deferred (RetryAfter) sends, stop retrying — same attempt_count
# column, higher ceiling so transient flood-waits are not dead-lettered early.
MAX_DEFERRED_ATTEMPTS = 30
# Persist delivery_attempted_ok this many times before abandoning to memory + DL.
MARK_DELIVERY_OK_ATTEMPTS = 3
# Cap one-at-a-time unsent claims per drain (lease starts just before each send).
RETRY_UNSENT_MAX = 50
# Fsync'd local Telegram-OK ledger. Covers restart after total post-send DB write failure.
DELIVERY_OK_LEDGER_ENV = "CHIME_DELIVERY_OK_LEDGER"
# Max time shutdown waits for an in-flight scheduled tick (CORE-005 / E2-C02).
SHUTDOWN_TICK_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class PendingSend:
    """Claimed alert awaiting Telegram delivery (outside the advisory lock)."""

    log_id: int
    telegram_id: int
    message: str
    already_claimed_new: bool
    rule_id: int | None = None
    event: AlertEvent | None = None
    symbol: str | None = None


@dataclass(frozen=True)
class PendingPdfEnrich:
    """Disclosure awaiting optional legacy PDF URL enrichment (after unlock)."""

    disclosure_id: int
    symbol: str
    external_id: str


def _normalize_send_result(result: SendResult | bool) -> SendResult:
    """Map legacy bool send callbacks onto SendResult (False → failed)."""
    if isinstance(result, bool):
        return SendResult.OK if result else SendResult.FAILED
    return result


def _symbol_from_alert_message(message: str) -> str | None:
    """Best-effort parse of ``format_alert_message`` first line (``🔔 SYMBOL``)."""
    first = (message or "").split("\n", 1)[0].strip()
    if first.startswith("🔔"):
        symbol = first.removeprefix("🔔").strip()
        return symbol or None
    return None


def _delivery_ok_token(
    *,
    log_id: int,
    rule_id: int | None,
    telegram_id: int,
    message: str,
) -> str:
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()
    rule_part = "" if rule_id is None else str(rule_id)
    return f"{log_id}:{rule_part}:{telegram_id}:{digest}"


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def is_market_open(now: datetime, settings: Settings) -> bool:
    tz = ZoneInfo(settings.market_tz)
    local = now.astimezone(tz)
    if local.weekday() >= 5:
        return False
    open_t = parse_hhmm(settings.market_open)
    close_t = parse_hhmm(settings.market_close)
    return open_t <= local.time() <= close_t


class Poller:
    def __init__(
        self,
        settings: Settings,
        storage: Storage,
        cse: CSEClient,
        send: SendFunc,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.cse = cse
        self.send = send
        self._scheduler: AsyncIOScheduler | None = None
        self._stopping = asyncio.Event()
        self.last_tick_at: datetime | None = None
        self.last_tick_ok: bool = False
        self.last_error: str | None = None
        self.price_poll_ok: bool = True
        self.disclosure_poll_ok: bool = True
        self.lock_held_skip: bool = False
        # Watched symbols absent from the latest tradeSummary (E2-C06).
        self.watched_missing: list[str] = []
        # Last tradeSummary shape: empty HTTP-OK with a non-empty watchlist is
        # operationally different from a partial symbol miss.
        self.trade_summary_count: int | None = None
        self.trade_summary_empty_ok: bool = False
        # When True, _claim_and_send queues PendingSend instead of sending inline
        # (set for the locked section of run_once).
        self._queue_sends: bool = False
        self._pending_sends: list[PendingSend] = []
        # In-flight scheduled tick (APScheduler job task). Awaited on shutdown.
        self._tick_task: asyncio.Task[Any] | None = None
        # Process-lifetime: Telegram-OK alert_log ids. Survives ticks so a
        # mark_alert_sent outage cannot re-push every poll (L08-001).
        self._delivered_ok_ids: set[int] = set()
        # Restart-lifetime: Telegram-OK signatures fsync'd before DB marks.
        self._delivery_ok_ledger_path = self._delivery_ok_ledger_path_from_env()
        self._delivered_ok_tokens: set[str] = set()
        self._delivery_ok_records: dict[str, dict[str, Any]] = {}
        self._load_delivery_ok_ledger()
        # Dead-letter user notification is best-effort and one-shot per process.
        self._dead_letter_notify_attempted_ids: set[int] = set()
        # Legacy PDF enrichment queued under lock; HTTP runs after unlock.
        self._pending_pdf_enrich: list[PendingPdfEnrich] = []

    async def run_once(self, *, force: bool = False) -> list[AlertEvent]:
        """Single poll cycle. Returns events claimed (delivered after unlock)."""
        now = datetime.now(UTC)
        if not force and not is_market_open(now, self.settings):
            log.info("poll_skipped_outside_hours", now=now.isoformat())
            # Delivery is independent of market hours — retry unsent backlog
            # so Telegram failures overnight/weekend still drain.
            await self._retry_unsent_with_lock()
            self.last_tick_at = datetime.now(UTC)
            return []

        locked = await self.storage.try_advisory_lock(POLL_LOCK_ID)
        if not locked:
            log.info("poll_skipped_lock_held")
            self.lock_held_skip = True
            self.last_tick_ok = False
            self.last_error = "poll_lock_held"
            self.last_tick_at = datetime.now(UTC)
            return []

        self.lock_held_skip = False
        fired: list[AlertEvent] = []
        pending: list[PendingSend] = []
        pdf_enrich: list[PendingPdfEnrich] = []
        self._queue_sends = True
        self._pending_sends = pending
        self._pending_pdf_enrich = pdf_enrich
        try:
            price_events, price_ok = await self._poll_prices()
            disc_events, disc_ok = await self._poll_disclosures()
            fired.extend(price_events)
            fired.extend(disc_events)
            self.price_poll_ok = price_ok
            self.disclosure_poll_ok = disc_ok
            symbols = await self.storage.watched_symbols()
            rules = await self.storage.active_rules_for_symbols(symbols) if symbols else []
            needs_disclosure = any(r.type.value == "disclosure" for r in rules)
            ok = True
            # Market-wide persist is the browse foundation: degrade on price_ok
            # False even with an empty watchlist (fetch/persist/empty board).
            if not price_ok:
                ok = False
            if needs_disclosure and not disc_ok:
                ok = False
            self.last_tick_ok = ok
            if not ok:
                self.last_error = "poll_degraded"
            else:
                self.last_error = None
        except Exception as exc:
            self.last_tick_ok = False
            self.last_error = str(exc)
            log.exception("poll_cycle_failed", error=str(exc))
        finally:
            self._queue_sends = False
            self.last_tick_at = datetime.now(UTC)
            await self.storage.advisory_unlock(POLL_LOCK_ID)

        # CORE-004: Telegram I/O for this tick's new claims after unlock.
        # E2-C05: unsent drain uses row leases (SKIP LOCKED) — no advisory
        # re-hold, so RetryAfter may sleep without pinning the poll lock.
        # PDF enrichment is fail-soft and rate-limited — never blocks alerts.
        try:
            await self._deliver_pending(pending)
            await self._retry_unsent_with_lock()
        except Exception as exc:
            log.exception("poll_deliver_failed", error=str(exc))
        try:
            await self._enrich_disclosure_pdfs(pdf_enrich)
        except Exception as exc:
            log.warning("pdf_enrich_batch_failed", error=str(exc))
        return fired

    async def _retry_unsent_with_lock(self) -> None:
        """Drain unsent without holding the poll advisory lock (E2-C05).

        ``claim_unsent_batch`` leases rows via FOR UPDATE SKIP LOCKED so
        concurrent pollers cannot double-send; Telegram RetryAfter sleeps
        safely outside any advisory hold. Method name kept for call sites.
        """
        try:
            await self._retry_unsent()
        except Exception as exc:
            log.exception("offhours_retry_failed", error=str(exc))

    def _remember_delivered(self, log_id: int) -> None:
        self._delivered_ok_ids.add(log_id)
        # Bound memory if mark_alert_sent stays broken for a long outage.
        if len(self._delivered_ok_ids) > 10_000:
            # Drop an arbitrary half (set pop is fine — ids are opaque).
            for _ in range(5_000):
                self._delivered_ok_ids.pop()

    def _delivery_ok_ledger_path_from_env(self) -> Path | None:
        raw = os.getenv(DELIVERY_OK_LEDGER_ENV)
        if raw is not None:
            raw = raw.strip()
            return Path(raw) if raw else None
        digest = hashlib.sha256(self.settings.database_url.encode("utf-8")).hexdigest()[:16]
        return Path("/tmp/chime") / f"delivery-ok-{digest}.jsonl"

    def _load_delivery_ok_ledger(self) -> None:
        path = self._delivery_ok_ledger_path
        if path is None:
            return
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except Exception:
            log.exception("delivery_ok_ledger_load_failed", path=str(path))
            return
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                log.warning("delivery_ok_ledger_bad_line", path=str(path))
                continue
            token = record.get("token")
            if not isinstance(token, str) or not token:
                continue
            if record.get("forget") is True:
                self._delivered_ok_tokens.discard(token)
                self._delivery_ok_records.pop(token, None)
                continue
            self._delivered_ok_tokens.add(token)
            self._delivery_ok_records[token] = record

    def _delivery_ok_token_for_pending(self, pending: PendingSend) -> str:
        return _delivery_ok_token(
            log_id=pending.log_id,
            rule_id=pending.rule_id,
            telegram_id=pending.telegram_id,
            message=pending.message,
        )

    def _durably_remember_delivery_ok(
        self,
        pending: PendingSend,
        *,
        event_key: str | None,
    ) -> str:
        """Fsync Telegram-OK before DB marks so restart cannot re-send."""
        token = self._delivery_ok_token_for_pending(pending)
        self._delivered_ok_tokens.add(token)
        if token in self._delivery_ok_records:
            return token
        record: dict[str, Any] = {
            "token": token,
            "id": pending.log_id,
            "rule_id": pending.rule_id,
            "telegram_id": pending.telegram_id,
            "message_sha256": hashlib.sha256(pending.message.encode("utf-8")).hexdigest(),
            "event_key": event_key,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        path = self._delivery_ok_ledger_path
        if path is None:
            self._delivery_ok_records[token] = record
            return token
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._delivery_ok_records[token] = record
        except Exception:
            log.exception(
                "delivery_ok_ledger_write_failed",
                alert_log_id=pending.log_id,
                rule_id=pending.rule_id,
                event_key=event_key,
                path=str(path),
            )
        return token

    def _forget_durable_delivery_ok(self, token: str) -> None:
        self._delivered_ok_tokens.discard(token)
        self._delivery_ok_records.pop(token, None)
        path = self._delivery_ok_ledger_path
        if path is None:
            return
        record: dict[str, Any] = {
            "token": token,
            "forget": True,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
        except Exception:
            log.exception("delivery_ok_ledger_forget_failed", path=str(path))

    def _delivery_ok_already_recorded(self, pending: PendingSend) -> bool:
        return (
            pending.log_id in self._delivered_ok_ids
            or self._delivery_ok_token_for_pending(pending) in self._delivered_ok_tokens
        )

    async def _reconcile_delivery_ok(self, pending: PendingSend) -> None:
        token = self._delivery_ok_token_for_pending(pending)
        self._remember_delivered(pending.log_id)
        delivery_marked = await self._mark_delivery_ok_best_effort(
            pending.log_id,
            rule_id=pending.rule_id,
            event_key=None,
        )
        marked = await self._mark_sent_best_effort(
            pending.log_id,
            rule_id=pending.rule_id,
            event_key=None,
        )
        if delivery_marked or marked:
            self._forget_durable_delivery_ok(token)

    async def _poll_prices(self) -> tuple[list[AlertEvent], bool]:
        """Fetch full tradeSummary, persist market-wide, evaluate watchlist only.

        Empty watchlist still persists the board so the thin /market browse has
        data. Rule evaluation and watched_missing checks remain watchlist-scoped.
        """
        symbols = await self.storage.watched_symbols()
        wanted = set(symbols)

        try:
            all_snaps = await self.cse.fetch_trade_summary()
        except CircuitOpenError:
            self.trade_summary_count = None
            self.trade_summary_empty_ok = False
            if not wanted:
                self.watched_missing = []
            log.error("price_poll_circuit_open")
            return [], False
        except Exception as exc:
            self.trade_summary_count = None
            self.trade_summary_empty_ok = False
            if not wanted:
                self.watched_missing = []
            log.exception("price_poll_failed", error=str(exc))
            return [], False

        self.trade_summary_count = len(all_snaps)
        self.trade_summary_empty_ok = len(all_snaps) == 0
        if self.trade_summary_empty_ok:
            log.warning(
                "trade_summary_empty_ok",
                watched_count=len(symbols),
                symbols=sorted(symbols),
            )

        # Market-wide persist (Tijori/browse foundation). Fail closed on DB errors.
        try:
            stored_all = await self.storage.persist_market_snapshots(all_snaps)
        except Exception as exc:
            log.exception("market_persist_failed", error=str(exc), count=len(all_snaps))
            if not wanted:
                self.watched_missing = []
            return [], False

        if not wanted:
            self.watched_missing = []
            # Empty HTTP-OK board is not a successful browse persist.
            price_ok = not self.trade_summary_empty_ok
            log.info(
                "poll_market_persist_no_watchlist",
                persisted=len(stored_all),
                trade_summary_count=self.trade_summary_count,
                price_ok=price_ok,
            )
            return [], price_ok

        present = {s.symbol for s in stored_all}
        missing = sorted(wanted - present)
        self.watched_missing = missing
        price_ok = not missing
        if missing:
            log.warning(
                "watched_symbols_missing",
                count=len(missing),
                symbols=missing,
            )

        snaps = [s for s in stored_all if s.symbol in wanted]
        rules = await self.storage.active_rules_for_symbols(list(wanted))
        rules_by_symbol: dict[str, list[Any]] = {}
        for rule in rules:
            rules_by_symbol.setdefault(rule.symbol, []).append(rule)

        return await self._evaluate_price_snaps(snaps, rules_by_symbol), price_ok

    async def _evaluate_price_snaps(
        self,
        snaps: list[PriceSnapshot],
        rules_by_symbol: dict[str, list[Any]],
    ) -> list[AlertEvent]:
        """Evaluate already-persisted watchlist snapshots (ids required)."""
        fired: list[AlertEvent] = []
        for stored in snaps:
            assert stored.id is not None
            previous = await self.storage.get_previous_state(stored.symbol, before_id=stored.id)
            symbol_rules = rules_by_symbol.get(stored.symbol, [])
            events = evaluate_price_rules(
                snapshot=stored,
                previous=previous,
                rules=symbol_rules,
            )
            for event in events:
                if event.trigger == "rearm" and event.set_armed is True:
                    await self.storage.set_rule_armed(event.rule_id, True)
            # Price crosses: claim+disarm in one DB transaction (E2-C03).
            # Conflict claim skips disarm. Telegram send stays outside the txn.
            for event in filter_fireable(events):
                t0 = datetime.now(UTC)
                claimed = await self._claim_and_send(
                    event,
                    disarm=event.set_armed is False,
                )
                if not claimed:
                    continue
                latency_ms = (datetime.now(UTC) - t0).total_seconds() * 1000
                log.info(
                    "alert_latency_ms",
                    rule_id=event.rule_id,
                    latency_ms=round(latency_ms, 1),
                    event_key=event.event_key,
                )
                fired.append(event)
        return fired

    async def _poll_disclosures(self) -> tuple[list[AlertEvent], bool]:
        symbols = await self.storage.watched_symbols()
        if not symbols:
            return [], True
        rules = await self.storage.active_rules_for_symbols(symbols)
        disclosure_rules = [r for r in rules if r.type.value == "disclosure"]
        # Only hit CSE announcements for symbols with active disclosure rules
        # (price-only watchlist symbols skip this leg — rate-limit priority).
        disclosure_symbols = sorted({r.symbol for r in disclosure_rules})
        if not disclosure_symbols:
            return [], True

        tz = ZoneInfo(self.settings.market_tz)
        today = datetime.now(tz).date()
        from_date = (today - timedelta(days=365)).isoformat()
        to_date = today.isoformat()
        any_failure = False

        # Fetch all first (no inter-symbol sleep under lock — CORE-004).
        # Sequential HTTP provides natural spacing; rate-limit sleeps belong
        # outside the advisory lock if reintroduced.
        fetched: dict[str, list[Disclosure]] = {}
        for symbol in disclosure_symbols:
            try:
                fetched[symbol] = await self.cse.fetch_announcements_for_symbol(
                    symbol, from_date=from_date, to_date=to_date
                )
            except Exception as exc:
                any_failure = True
                log.warning("disclosure_poll_failed", symbol=symbol, error=str(exc))

        fired: list[AlertEvent] = []
        for symbol, disclosures in fetched.items():
            symbol_rules = [r for r in disclosure_rules if r.symbol == symbol]
            for disc in disclosures:
                # Always upsert + evaluate. Crash between insert and claim used to
                # permanently skip (insert_if_new → None). Claim uniqueness
                # prevents duplicate Telegram sends; created_at gates history.
                stored = await self.storage.upsert_disclosure(disc)
                events = evaluate_disclosure_rules(disclosure=stored, rules=symbol_rules)
                for event in filter_fireable(events):
                    claimed = await self._claim_and_send(event)
                    if claimed:
                        fired.append(event)
                # Queue PDF enrichment after alerts are claimed — never blocks
                # rule eval / Telegram. Skip rows that already have pdf_url.
                if (
                    stored.id is not None
                    and not stored.pdf_url
                    and self._pending_pdf_enrich is not None
                ):
                    self._pending_pdf_enrich.append(
                        PendingPdfEnrich(
                            disclosure_id=stored.id,
                            symbol=stored.symbol,
                            external_id=stored.external_id,
                        )
                    )
        return fired, not any_failure

    async def _enrich_disclosure_pdfs(self, items: list[PendingPdfEnrich]) -> None:
        """Resolve legacy filePath → CDN PDF URL. Fail-soft; polite per-symbol sleep.

        Runs outside the advisory lock so CSE latency / sleeps never pin the
        poller or delay Telegram delivery.
        """
        if not items:
            return
        by_symbol: dict[str, list[PendingPdfEnrich]] = {}
        for item in items:
            by_symbol.setdefault(item.symbol, []).append(item)

        sleep_s = max(0.0, float(self.settings.pdf_enrich_sleep_seconds))
        first = True
        for symbol, rows in sorted(by_symbol.items()):
            if not first and sleep_s > 0:
                await asyncio.sleep(sleep_s)
            first = False
            try:
                legacy = await self.cse.fetch_legacy_announcements(symbol)
            except Exception as exc:
                log.warning(
                    "legacy_announcement_enrich_failed",
                    symbol=symbol,
                    error=str(exc),
                )
                continue
            pdf_map = legacy_pdf_urls_by_id(legacy)
            if not pdf_map:
                continue
            for item in rows:
                pdf_url = pdf_map.get(item.external_id)
                if not pdf_url:
                    continue
                try:
                    updated = await self.storage.set_disclosure_pdf_url(
                        item.disclosure_id, pdf_url
                    )
                    if updated:
                        log.info(
                            "disclosure_pdf_url_set",
                            disclosure_id=item.disclosure_id,
                            symbol=item.symbol,
                            external_id=item.external_id,
                        )
                except Exception as exc:
                    log.warning(
                        "pdf_url_set_failed",
                        disclosure_id=item.disclosure_id,
                        symbol=item.symbol,
                        error=str(exc),
                    )

    async def _notify_dead_letter(
        self,
        *,
        telegram_id: int | None,
        symbol: str | None,
        attempts: int,
        alert_log_id: int,
        rule_id: int | None = None,
    ) -> None:
        """One Telegram notify after dead-letter. Failures are log-only (no retry loop)."""
        if telegram_id is None or not symbol:
            log.warning(
                "dead_letter_notify_skipped",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
                has_telegram_id=telegram_id is not None,
                has_symbol=bool(symbol),
            )
            return
        if alert_log_id in self._dead_letter_notify_attempted_ids:
            log.info(
                "dead_letter_notify_already_attempted",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                symbol=symbol,
                attempts=attempts,
            )
            return
        self._dead_letter_notify_attempted_ids.add(alert_log_id)
        text = format_dead_letter_notify(symbol, attempts)
        try:
            result = _normalize_send_result(await self.send(telegram_id, text))
        except Exception:
            log.exception(
                "dead_letter_notify_failed",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                symbol=symbol,
                attempts=attempts,
            )
            return
        if result is SendResult.OK:
            log.info(
                "dead_letter_notify_sent",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                symbol=symbol,
                attempts=attempts,
            )
        else:
            # Do not bump attempt_count / dead-letter again — notify is best-effort.
            log.warning(
                "dead_letter_notify_failed",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                symbol=symbol,
                attempts=attempts,
                send_result=result.value,
            )

    async def _record_send_failure(
        self,
        alert_log_id: int,
        *,
        rule_id: int | None = None,
        telegram_id: int | None = None,
        symbol: str | None = None,
    ) -> None:
        attempts = await self.storage.mark_alert_attempt(alert_log_id)
        if attempts >= MAX_SEND_ATTEMPTS:
            await self.storage.dead_letter(alert_log_id)
            log.warning(
                "alert_dead_lettered",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
                reason="failed",
            )
            await self._notify_dead_letter(
                telegram_id=telegram_id,
                symbol=symbol,
                attempts=attempts,
                alert_log_id=alert_log_id,
                rule_id=rule_id,
            )
        else:
            log.warning(
                "alert_send_failed",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
            )

    async def _record_send_deferred(
        self,
        alert_log_id: int,
        *,
        rule_id: int | None = None,
        telegram_id: int | None = None,
        symbol: str | None = None,
    ) -> None:
        """Bump attempt_count on RetryAfter defer; dead-letter at MAX_DEFERRED_ATTEMPTS."""
        attempts = await self.storage.mark_alert_attempt(alert_log_id)
        if attempts >= MAX_DEFERRED_ATTEMPTS:
            await self.storage.dead_letter(alert_log_id)
            log.warning(
                "alert_dead_lettered",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
                reason="deferred",
            )
            await self._notify_dead_letter(
                telegram_id=telegram_id,
                symbol=symbol,
                attempts=attempts,
                alert_log_id=alert_log_id,
                rule_id=rule_id,
            )
        else:
            log.info(
                "alert_send_deferred",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
            )

    async def _claim_only(
        self,
        event: AlertEvent,
        *,
        disarm: bool = False,
    ) -> PendingSend | None:
        """Claim the alert row; return a PendingSend or None on conflict.

        When ``disarm`` is True (price crosses), uses ``claim_and_disarm`` so
        claim + armed=False commit together. Conflict → no disarm.
        """
        message = format_alert_message(event)
        if disarm:
            log_id = await self.storage.claim_and_disarm(event, message)
        else:
            log_id = await self.storage.claim_alert(event, message)
        if log_id is None:
            log.info("alert_already_claimed", event_key=event.event_key, rule_id=event.rule_id)
            return None
        return PendingSend(
            log_id=log_id,
            telegram_id=event.telegram_id,
            message=message,
            already_claimed_new=True,
            rule_id=event.rule_id,
            event=event,
            symbol=event.symbol,
        )

    async def _deliver_one(self, pending: PendingSend) -> None:
        """Send one claimed alert and update alert_log (OK / FAILED / DEFERRED)."""
        result = _normalize_send_result(await self.send(pending.telegram_id, pending.message))
        symbol = pending.symbol
        if symbol is None and pending.event is not None:
            symbol = pending.event.symbol
        if symbol is None:
            symbol = _symbol_from_alert_message(pending.message)
        if result is SendResult.OK:
            # Telegram already delivered. Remember across ticks (L08-001) so a
            # mark_alert_sent outage cannot re-push every poll interval.
            self._remember_delivered(pending.log_id)
            event_key = pending.event.event_key if pending.event is not None else None
            # E12-C01: write a local durable OK marker before any DB marks. If
            # all post-send DB writes fail and the process restarts, retry drain
            # will reconcile this row without re-sending Telegram.
            token = self._durably_remember_delivery_ok(pending, event_key=event_key)
            # Durable guard before message_sent (E2-C04): survives restart when
            # mark_alert_sent fails but this lighter UPDATE succeeds.
            delivery_marked = await self._mark_delivery_ok_best_effort(
                pending.log_id,
                rule_id=pending.rule_id,
                event_key=event_key,
            )
            marked = await self._mark_sent_best_effort(
                pending.log_id,
                rule_id=pending.rule_id,
                event_key=event_key,
            )
            if marked:
                log.info(
                    "alert_sent",
                    rule_id=pending.rule_id,
                    event_key=event_key,
                )
            if delivery_marked or marked:
                self._forget_durable_delivery_ok(token)
        elif result is SendResult.FAILED:
            await self._record_send_failure(
                pending.log_id,
                rule_id=pending.rule_id,
                telegram_id=pending.telegram_id,
                symbol=symbol,
            )
        elif result is SendResult.DEFERRED:
            await self._record_send_deferred(
                pending.log_id,
                rule_id=pending.rule_id,
                telegram_id=pending.telegram_id,
                symbol=symbol,
            )

    async def _deliver_pending(self, pending: list[PendingSend]) -> None:
        for item in pending:
            await self._deliver_one(item)

    async def _claim_and_send(self, event: AlertEvent, *, disarm: bool = False) -> bool:
        """Claim the alert, then attempt Telegram send (or queue when locked).

        Returns True when the claim succeeded (row inserted), even if Telegram
        send failed. With ``disarm=True``, claim and armed=False are one
        transaction (E2-C03); delivery continues via ``message_sent=False``
        retry / dead-letter. Returns False only on claim conflict.

        Under ``run_once`` (``_queue_sends=True``) the send is deferred until
        after advisory unlock (CORE-004). Direct callers (unit tests) still
        send inline.
        """
        pending = await self._claim_only(event, disarm=disarm)
        if pending is None:
            return False
        if self._queue_sends:
            self._pending_sends.append(pending)
            return True
        await self._deliver_one(pending)
        return True

    async def _mark_delivery_ok_best_effort(
        self,
        log_id: int,
        *,
        rule_id: int | None = None,
        event_key: str | None = None,
    ) -> bool:
        """Persist delivery_attempted_ok so restart cannot re-push (E2-C04).

        Retries before treating delivery as durably recorded. Never raises.
        Returns True if the durable flag was written. On total failure the
        caller still keeps ``log_id`` in ``_delivered_ok_ids``; we log
        critical and best-effort dead-letter as a last resort.
        """
        for attempt in range(1, MARK_DELIVERY_OK_ATTEMPTS + 1):
            try:
                await self.storage.mark_delivery_attempted_ok(log_id)
                return True
            except Exception:
                log.exception(
                    "mark_delivery_attempted_ok_failed",
                    alert_log_id=log_id,
                    rule_id=rule_id,
                    event_key=event_key,
                    attempt=attempt,
                )
        log.critical(
            "mark_delivery_attempted_ok_abandoned",
            alert_log_id=log_id,
            rule_id=rule_id,
            event_key=event_key,
            attempts=MARK_DELIVERY_OK_ATTEMPTS,
        )
        with contextlib.suppress(Exception):
            await self.storage.dead_letter(log_id)
        return False

    async def _mark_sent_best_effort(
        self,
        log_id: int,
        *,
        rule_id: int | None = None,
        event_key: str | None = None,
    ) -> bool:
        """Mark message_sent; retry once on failure. Never raises.

        Returns True if marked. If both attempts fail, dead-letters so
        ``_retry_unsent`` cannot re-deliver to Telegram.
        """
        for attempt in (1, 2):
            try:
                await self.storage.mark_alert_sent(log_id)
                return True
            except Exception:
                log.exception(
                    "mark_alert_sent_failed",
                    alert_log_id=log_id,
                    rule_id=rule_id,
                    event_key=event_key,
                    attempt=attempt,
                )
        with contextlib.suppress(Exception):
            await self.storage.dead_letter(log_id)
        log.warning(
            "mark_alert_sent_abandoned",
            alert_log_id=log_id,
            rule_id=rule_id,
            event_key=event_key,
        )
        return False

    async def _retry_unsent(self) -> None:
        """Claim+send one unsent row at a time so each lease starts at send time.

        Batch-claiming N rows then sending sequentially can let later leases
        expire mid-drain (RetryAfter). ``limit=1`` renews the lease just before
        each Telegram attempt; stop when the queue is empty or after
        ``RETRY_UNSENT_MAX`` claims.
        """
        for _ in range(RETRY_UNSENT_MAX):
            pending = await self.storage.claim_unsent_batch(limit=1)
            if not pending:
                break
            row = pending[0]
            log_id = int(row["id"])
            text = row["message_text"] or ""
            item = PendingSend(
                log_id=log_id,
                telegram_id=int(row["telegram_id"]),
                message=text,
                already_claimed_new=False,
                rule_id=int(row["rule_id"]),
                event=None,
                symbol=_symbol_from_alert_message(text),
            )
            if self._delivery_ok_already_recorded(item):
                log.warning(
                    "alert_send_skipped_already_delivered_ok",
                    alert_log_id=log_id,
                    rule_id=item.rule_id,
                )
                await self._reconcile_delivery_ok(item)
                continue
            await self._deliver_one(item)

    async def _scheduled_tick(self) -> None:
        task = asyncio.current_task()
        self._tick_task = task
        try:
            jitter = random.uniform(0, self.settings.poll_jitter_seconds)
            await asyncio.sleep(jitter)
            await self.run_once()
        finally:
            if self._tick_task is task:
                self._tick_task = None

    def start_scheduler(self) -> AsyncIOScheduler:
        tz = ZoneInfo(self.settings.market_tz)
        scheduler = AsyncIOScheduler(timezone=tz)
        scheduler.add_job(
            self._scheduled_tick,
            IntervalTrigger(seconds=self.settings.poll_interval_seconds, timezone=tz),
            id="cse_poll",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30,
        )
        scheduler.start()
        self._scheduler = scheduler
        log.info(
            "poller_started",
            interval=self.settings.poll_interval_seconds,
            tz=self.settings.market_tz,
        )
        return scheduler

    async def shutdown(self) -> None:
        """Stop the scheduler, then await any in-flight tick (bounded).

        ``scheduler.shutdown(wait=False)`` returns immediately; CORE-005 /
        E2-C02 require waiting for the current ``_scheduled_tick`` /
        ``run_once`` so ``storage.close()`` does not race the advisory lock.
        """
        self._stopping.set()
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        tick = self._tick_task
        if tick is not None and not tick.done():
            try:
                # shield: timeout must not cancel mid-tick (lock / pool borrow).
                await asyncio.wait_for(
                    asyncio.shield(tick),
                    timeout=SHUTDOWN_TICK_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                log.warning(
                    "poller_shutdown_tick_timeout",
                    timeout_seconds=SHUTDOWN_TICK_TIMEOUT_SECONDS,
                )
            except Exception:
                log.exception("poller_shutdown_tick_error")
        log.info("poller_stopped")


async def run_poller_forever(
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    send: SendFunc,
    *,
    health: Any | None = None,
) -> None:
    poller = Poller(settings, storage, cse, send)
    poller.start_scheduler()

    stop = asyncio.Event()

    def _handle_sig(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handle_sig)

    async def _health_loop() -> None:
        if health is None:
            return
        while not stop.is_set():
            db_ok = False
            try:
                db_ok = await storage.health_check()
            except Exception as exc:
                log.warning("health_db_failed", error=str(exc))
            tick_ok = poller.last_tick_ok
            missing = list(poller.watched_missing)
            circuits: dict[str, object] = {}
            metrics = getattr(poller.cse, "circuit_metrics", None)
            if callable(metrics):
                raw = metrics()
                if isinstance(raw, dict):
                    circuits = raw
            health.update(
                ok=db_ok and tick_ok and not missing and not poller.trade_summary_empty_ok,
                db_ok=db_ok,
                last_tick_at=poller.last_tick_at.isoformat() if poller.last_tick_at else None,
                last_tick_ok=tick_ok,
                price_poll_ok=poller.price_poll_ok,
                disclosure_poll_ok=poller.disclosure_poll_ok,
                lock_held_skip=poller.lock_held_skip,
                watched_missing=missing,
                trade_summary_empty_ok=poller.trade_summary_empty_ok,
                trade_summary_count=poller.trade_summary_count,
                tradeSummary={
                    "empty_ok": poller.trade_summary_empty_ok,
                    "count": poller.trade_summary_count,
                },
                circuits=circuits,
                last_error=poller.last_error,
            )
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=10)

    health_task = asyncio.create_task(_health_loop())
    try:
        await stop.wait()
    finally:
        health_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await health_task
        await poller.shutdown()
