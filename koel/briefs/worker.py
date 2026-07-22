"""Filing brief worker — enqueue ledger rows and drain pending briefs.

``enqueue_brief`` persists pending/skipped rows. ``drain_pending_briefs``
claims work, fetches CDN PDF text when ``pdf_url`` is set, and calls the
configured provider (Gemini/Groq/OpenRouter) when briefs are enabled.
After mark-ready, optionally sends a Telegram follow-up via ``notify`` when the
poller provides one — only for users who already received a disclosure alert
without the brief (durable ``alert_log`` claim; no double Telegram).

Also sweeps ready briefs for late follow-ups (primary delivered after brief
ready) and promotes recent ``skipped`` rows when AI is newly enabled.
"""

from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx
import structlog

from koel.adapters.cse import allowed_cdn_pdf_url
from koel.briefs import BriefSettings, BriefStatus, briefs_enabled, build_brief_prompt
from koel.briefs.extract import CdnPdfPermanentError, extract_pdf_text, fetch_cdn_pdf
from koel.briefs.provider import BriefProvider, make_brief_provider
from koel.briefs.verify import brief_numbers_verified
from koel.domain import format_brief_followup, resolve_positive_int_cap
from koel.notify import SendResult

log = structlog.get_logger("koel.briefs")

BriefNotifyFunc = Callable[[int, str], Awaitable[Any]]


class BriefCdnTransientError(RuntimeError):
    """CDN PDF fetch failed transiently — requeue pending, do not burn daily cap."""


async def _maybe_await(value: Any) -> Any:
    """Await coroutine/awaitable results; pass through plain values (tests/mocks)."""
    if inspect.isawaitable(value):
        return await value
    return value


def _notify_succeeded(result: Any) -> bool:
    """True only when Telegram accepted the send (bool True or SendResult.OK)."""
    if isinstance(result, bool):
        return result
    return result is SendResult.OK


class _BriefEnqueuer(Protocol):
    async def enqueue_disclosure_brief(
        self,
        disclosure_id: int,
        *,
        status: str = "pending",
    ) -> bool: ...


class _BriefDrainStorage(Protocol):
    async def claim_pending_briefs(
        self,
        *,
        limit: int = 5,
        max_briefs_per_day: int | None = None,
        stale_processing_minutes: int = 15,
        pdf_grace_seconds: int = 120,
        cdn_backoff_seconds: int = 300,
    ) -> list[dict[str, Any]]: ...

    async def mark_brief_ready(
        self,
        disclosure_id: int,
        *,
        brief: str,
        model: str,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> bool: ...

    async def mark_brief_failed(
        self,
        disclosure_id: int,
        *,
        error: str,
        model: str | None = None,
    ) -> bool: ...

    async def requeue_brief_pending(
        self,
        disclosure_id: int,
        *,
        error: str,
    ) -> bool: ...

    async def count_briefs_today(self, *, stale_processing_minutes: int = 15) -> int: ...

    async def claim_brief_followups(
        self,
        *,
        external_id: str,
        symbol: str,
        brief: str,
        message_text: str,
        lease_seconds: int = 120,
    ) -> list[dict[str, Any]]: ...

    async def mark_delivery_attempted_ok(self, alert_log_id: int) -> None: ...

    async def mark_alert_sent(self, alert_log_id: int) -> None: ...

    async def promote_recent_skipped_briefs(
        self,
        *,
        max_age_hours: int = 24,
        limit: int = 100,
    ) -> int: ...

    async def list_ready_briefs_for_followup_sweep(
        self,
        *,
        limit: int = 20,
        max_age_days: int = 7,
    ) -> list[dict[str, Any]]: ...


async def enqueue_or_skip_brief(
    *,
    disclosure_id: int,
    settings: BriefSettings | None = None,
    storage: _BriefEnqueuer | None = None,
) -> BriefStatus:
    """Enqueue a briefs ledger row: pending when enabled, skipped when disabled.

    When ``storage`` is provided, persists via ``enqueue_disclosure_brief``
    (INSERT … ON CONFLICT DO NOTHING). Without storage this remains a pure
    status decision for unit tests. Does not call any LLM.
    """
    cfg = settings or BriefSettings.from_env()
    status = BriefStatus.PENDING if briefs_enabled(cfg) else BriefStatus.SKIPPED
    if storage is not None:
        inserted = await storage.enqueue_disclosure_brief(
            disclosure_id,
            status=status.value,
        )
        log.info(
            "brief_enqueued",
            disclosure_id=disclosure_id,
            status=status.value,
            inserted=inserted,
            provider=cfg.provider if status is BriefStatus.PENDING else None,
            model=cfg.model if status is BriefStatus.PENDING else None,
        )
        return status
    if status is BriefStatus.SKIPPED:
        log.debug("brief_skipped_disabled", disclosure_id=disclosure_id)
    else:
        log.info(
            "brief_enqueue_no_storage",
            disclosure_id=disclosure_id,
            provider=cfg.provider,
            model=cfg.model,
        )
    return status


def _title_only_input_text(row: dict[str, Any]) -> str:
    """Title-only fallback when no PDF text is available."""
    # Fail closed — non-string PG fields used to soft-accept via str().
    raw_sym = row.get("symbol")
    raw_title = row.get("title")
    symbol = raw_sym.strip() if isinstance(raw_sym, str) else ""
    title = raw_title.strip() if isinstance(raw_title, str) else ""
    if symbol and title:
        return f"{symbol}: {title}"
    return title or symbol


async def _input_text_for_row(
    row: dict[str, Any],
    *,
    cfg: BriefSettings,
    client: httpx.AsyncClient,
) -> tuple[str, str]:
    """Build provider input + raw source text for number verification.

    Returns ``(prompt, source_text)`` where ``source_text`` is the raw extracted
    PDF text or the title-only body — not the prompt wrapper. When ``pdf_url``
    is set, a failed CDN fetch raises ``BriefCdnTransientError`` so the drain
    requeues ``pending`` (no daily-cap burn) instead of a silent title-only
    summarize or a permanent ``failed``. Non-allowlisted hosts and permanent
    CDN faults (oversized / redirect) raise a plain ``RuntimeError``
    (permanent fail). Empty extract after a successful fetch still falls back
    to title (image-only PDFs).
    """
    # Fail closed — non-string PG fields used to soft-accept via str().
    raw_sym = row.get("symbol")
    raw_title = row.get("title")
    symbol = raw_sym.strip() if isinstance(raw_sym, str) else ""
    title = raw_title.strip() if isinstance(raw_title, str) else ""
    # Fail closed — bool soft-accepts via int(True)==1 shrink prompt budget.
    max_chars = resolve_positive_int_cap(cfg.max_input_chars, default=12_000)
    pdf_url = row.get("pdf_url")
    if isinstance(pdf_url, str) and pdf_url.strip():
        url = pdf_url.strip()
        if allowed_cdn_pdf_url(url) is None:
            raise RuntimeError(f"CDN PDF URL rejected (not allowlisted): {url!r}")
        try:
            raw = await fetch_cdn_pdf(
                url,
                max_bytes=cfg.pdf_max_bytes,
                client=client,
            )
        except CdnPdfPermanentError as exc:
            raise RuntimeError(str(exc)) from exc
        if raw is None:
            raise BriefCdnTransientError(f"CDN PDF fetch failed for {url!r}")
        extracted = extract_pdf_text(raw)
        if extracted:
            prompt = build_brief_prompt(
                symbol=symbol or "UNKNOWN",
                title=title or "Filing",
                extracted_text=extracted,
                max_chars=max_chars,
            )
            return prompt, extracted
        log.info(
            "brief_pdf_text_empty",
            disclosure_id=row.get("disclosure_id"),
            pdf_url=pdf_url,
        )
    source_text = _title_only_input_text(row)
    prompt = build_brief_prompt(
        symbol=symbol or "UNKNOWN",
        title=title or "Filing",
        extracted_text=source_text,
        max_chars=max_chars,
    )
    return prompt, source_text


async def _notify_brief_followups(
    storage: _BriefDrainStorage,
    *,
    notify: BriefNotifyFunc,
    row: dict[str, Any],
    brief: str,
) -> None:
    """Best-effort follow-up when a brief becomes ready. Never raises.

    Claims ``brief_followup:{rule}:{external_id}`` rows only for users who
    already have a primary disclosure alert that did not include this brief.
    That blocks ready-before-alert doubles and concurrent dual-notify.
    """
    disclosure_id = row.get("disclosure_id")
    try:
        # Fail closed — non-string PG fields used to soft-accept via str().
        raw_sym = row.get("symbol")
        raw_ext = row.get("external_id")
        symbol = raw_sym.strip() if isinstance(raw_sym, str) else ""
        external_id = raw_ext.strip() if isinstance(raw_ext, str) else ""
        # Fail closed — non-string brief used to throw on .strip mid follow-up.
        brief_text = brief.strip() if isinstance(brief, str) else ""
        if not symbol or not brief_text or not external_id:
            log.debug(
                "brief_followup_skipped_incomplete",
                disclosure_id=disclosure_id,
                has_symbol=bool(symbol),
                has_external_id=bool(external_id),
                has_brief=bool(brief_text),
            )
            return
        claim_fn = getattr(storage, "claim_brief_followups", None)
        if claim_fn is None:
            return
        raw_title = row.get("title")
        raw_url = row.get("url")
        message = format_brief_followup(
            symbol=symbol,
            brief=brief_text,
            title=raw_title if isinstance(raw_title, str) else None,
            url=raw_url if isinstance(raw_url, str) else None,
        )
        claimed = await claim_fn(
            external_id=external_id,
            symbol=symbol,
            brief=brief_text,
            message_text=message,
        )
        if not claimed:
            log.debug(
                "brief_followup_skipped_no_claim",
                disclosure_id=disclosure_id,
                symbol=symbol,
                external_id=external_id,
            )
            return
        for entry in claimed:
            # Fail closed — poisoned claim rows used to throw on int()/str()
            # soft-accept mid brief follow-up drain (bool→1, lists abort).
            raw_tg = entry.get("telegram_id")
            raw_log = entry.get("id")
            if (
                isinstance(raw_tg, bool)
                or not isinstance(raw_tg, int)
                or isinstance(raw_log, bool)
                or not isinstance(raw_log, int)
            ):
                log.warning(
                    "brief_followup_claim_row_poisoned",
                    disclosure_id=disclosure_id,
                    symbol=symbol,
                    telegram_id=raw_tg,
                    alert_log_id=raw_log,
                )
                continue
            telegram_id = raw_tg
            log_id = raw_log
            raw_text = entry.get("message_text")
            text = raw_text if isinstance(raw_text, str) and raw_text else message
            try:
                result = await notify(telegram_id, text)
            except Exception as exc:
                log.warning(
                    "brief_followup_send_failed",
                    disclosure_id=disclosure_id,
                    symbol=symbol,
                    telegram_id=telegram_id,
                    alert_log_id=log_id,
                    error=str(exc),
                )
                continue
            # Only mark delivered on OK — FAILED/DEFERRED leave message_sent=False
            # so claim_unsent_batch can retry after the delivery lease expires.
            if not _notify_succeeded(result):
                log.warning(
                    "brief_followup_send_not_ok",
                    disclosure_id=disclosure_id,
                    symbol=symbol,
                    telegram_id=telegram_id,
                    alert_log_id=log_id,
                    send_result=getattr(result, "value", result),
                )
                continue
            try:
                mark_ok = getattr(storage, "mark_delivery_attempted_ok", None)
                mark_sent = getattr(storage, "mark_alert_sent", None)
                if mark_ok is not None:
                    await mark_ok(log_id)
                if mark_sent is not None:
                    await mark_sent(log_id)
                log.info(
                    "brief_followup_sent",
                    disclosure_id=disclosure_id,
                    symbol=symbol,
                    telegram_id=telegram_id,
                    alert_log_id=log_id,
                )
            except Exception as exc:
                log.warning(
                    "brief_followup_mark_failed",
                    disclosure_id=disclosure_id,
                    symbol=symbol,
                    telegram_id=telegram_id,
                    alert_log_id=log_id,
                    error=str(exc),
                )
    except Exception as exc:
        log.warning(
            "brief_followup_failed",
            disclosure_id=disclosure_id,
            error=str(exc),
        )


async def _promote_skipped_if_needed(
    storage: _BriefDrainStorage,
    *,
    cfg: BriefSettings,
) -> None:
    """Best-effort: recent skipped → pending when AI briefs are on."""
    # Fail closed — bool soft-accepts via int(True)==1 promote with a 1h window.
    raw_hours = cfg.skipped_promote_hours
    if isinstance(raw_hours, bool) or not isinstance(raw_hours, int):
        return
    hours = raw_hours
    if hours <= 0:
        return
    promote = getattr(storage, "promote_recent_skipped_briefs", None)
    if promote is None or not callable(promote):
        return
    try:
        raw = await _maybe_await(promote(max_age_hours=hours))
        # Fail closed — bool soft-accepts via isinstance(True, int) / int(True)==1
        # and inflated promote counts mid brief drain.
        n = (
            raw
            if isinstance(raw, int) and not isinstance(raw, bool)
            else 0
        )
        if n:
            log.info("brief_skipped_promoted", count=n, max_age_hours=hours)
    except Exception as exc:
        log.warning("brief_skipped_promote_failed", error=str(exc))


async def _sweep_brief_followups(
    storage: _BriefDrainStorage,
    *,
    notify: BriefNotifyFunc,
    limit: int = 20,
) -> None:
    """Retry follow-ups for ready briefs after late primary delivery. Fail-soft."""
    list_fn = getattr(storage, "list_ready_briefs_for_followup_sweep", None)
    if list_fn is None or not callable(list_fn):
        return
    try:
        raw = await _maybe_await(list_fn(limit=max(1, limit)))
        rows = raw if isinstance(raw, list) else []
    except Exception as exc:
        log.warning("brief_followup_sweep_list_failed", error=str(exc))
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        brief = row.get("brief")
        if not isinstance(brief, str) or not brief.strip():
            continue
        await _notify_brief_followups(
            storage,
            notify=notify,
            row=row,
            brief=brief,
        )


async def claim_pending_briefs(
    storage: _BriefDrainStorage,
    *,
    settings: BriefSettings | None = None,
    provider: BriefProvider | None = None,
    limit: int = 5,
    http_client: httpx.AsyncClient | None = None,
    notify: BriefNotifyFunc | None = None,
) -> int:
    """Load pending rows, call provider, mark ready/failed.

    When ``pdf_url`` is set on a claimed row, fetches the CDN PDF (host check +
    ``PDF_MAX_BYTES`` cap) and extracts text for the prompt. Claim SQL applies a
    PDF grace window so title-only summarize waits for legacy enrich when possible.
    No-op (returns 0) when briefs are disabled. Honours ``max_briefs_per_day``.
    Paces consecutive LLM calls with ``AI_BRIEF_SLEEP_SECONDS`` (default 0.5;
    ``0`` disables). Sleep runs between briefs, not before the first.

    When ``notify`` is provided: (1) after each successful ``mark_brief_ready``,
    and (2) via a ready-brief sweep covering late primary delivery, claims and
    sends fail-soft Telegram follow-ups only for users whose disclosure alert
    already fired without this brief (``claim_brief_followups``). Notify
    failures never fail the drain (unsent ``alert_log`` rows can retry).
    """
    cfg = settings or BriefSettings.from_env()
    if not briefs_enabled(cfg):
        log.debug("brief_drain_skipped_disabled")
        return 0

    await _promote_skipped_if_needed(storage, cfg=cfg)

    processed = 0
    used_raw = await storage.count_briefs_today()
    # Fail closed — bool soft-accepts via arithmetic True==1 understate daily
    # use and over-claim past AI_MAX_BRIEFS_PER_DAY (parity ``_pg_count``).
    if isinstance(used_raw, bool) or not isinstance(used_raw, int) or used_raw < 0:
        log.warning("brief_drain_used_poisoned", used=used_raw)
        return 0
    used = used_raw
    cap = cfg.max_briefs_per_day
    # Fail closed — bool soft-accepts via int(True)==1 understate the daily cap.
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
        log.warning("brief_drain_cap_poisoned", max_briefs_per_day=cap)
        return 0
    remaining = max(0, cap - used)
    if remaining <= 0:
        log.info(
            "brief_drain_daily_cap",
            used=used,
            max_briefs_per_day=cap,
        )
    else:
        batch = min(max(1, limit), remaining)
        rows = await storage.claim_pending_briefs(
            limit=batch,
            max_briefs_per_day=cap,
            pdf_grace_seconds=cfg.pdf_grace_seconds,
            cdn_backoff_seconds=cfg.cdn_backoff_seconds,
        )
        if rows:
            owns_provider = provider is None
            owns_http = http_client is None
            prov: BriefProvider = provider or make_brief_provider(cfg)
            # Fail closed — bool/non-finite soft-accepts must not poison httpx.
            raw_timeout = cfg.http_timeout_seconds
            timeout_s = (
                float(raw_timeout)
                if isinstance(raw_timeout, (int, float))
                and not isinstance(raw_timeout, bool)
                and math.isfinite(raw_timeout)
                and raw_timeout > 0
                else 30.0
            )
            http = http_client or httpx.AsyncClient(timeout=timeout_s)
            # Fail closed — bool/non-finite soft-accepts must not hang sleep(inf).
            raw_sleep = cfg.sleep_seconds
            sleep_s = (
                max(0.0, float(raw_sleep))
                if isinstance(raw_sleep, (int, float))
                and not isinstance(raw_sleep, bool)
                and math.isfinite(raw_sleep)
                else 0.0
            )
            try:
                for i, row in enumerate(rows):
                    if i > 0 and sleep_s > 0:
                        await asyncio.sleep(sleep_s)
                    if not isinstance(row, dict):
                        log.warning(
                            "brief_drain_row_poisoned",
                            row_type=type(row).__name__,
                        )
                        continue
                    # Fail closed — poisoned disclosure_id used to throw on
                    # int() (lists) or soft-accept bool→1 mid brief drain.
                    raw_did = row.get("disclosure_id")
                    if isinstance(raw_did, bool) or not isinstance(raw_did, int):
                        log.warning(
                            "brief_drain_row_poisoned",
                            disclosure_id=raw_did,
                        )
                        continue
                    disclosure_id = raw_did
                    try:
                        text, source_text = await _input_text_for_row(
                            row, cfg=cfg, client=http
                        )
                        brief = await prov.summarize(text)
                        if not brief_numbers_verified(brief, source_text):
                            await storage.mark_brief_failed(
                                disclosure_id,
                                error="number_verification_failed",
                                model=cfg.model,
                            )
                            log.warning(
                                "brief_number_verify_failed",
                                disclosure_id=disclosure_id,
                                model=cfg.model,
                            )
                            processed += 1
                            continue
                        marked = await storage.mark_brief_ready(
                            disclosure_id,
                            brief=brief,
                            model=cfg.model,
                        )
                        log.info(
                            "brief_ready",
                            disclosure_id=disclosure_id,
                            model=cfg.model,
                            marked=marked,
                        )
                        if marked and notify is not None:
                            await _notify_brief_followups(
                                storage,
                                notify=notify,
                                row=row,
                                brief=brief,
                            )
                    except BriefCdnTransientError as exc:
                        # Transient CDN miss: requeue pending so the next drain
                        # retries without burning max_briefs_per_day on failed.
                        requeue = getattr(storage, "requeue_brief_pending", None)
                        if requeue is not None:
                            await requeue(disclosure_id, error=str(exc))
                        else:
                            await storage.mark_brief_failed(
                                disclosure_id,
                                error=str(exc),
                                model=cfg.model,
                            )
                        log.warning(
                            "brief_cdn_requeued",
                            disclosure_id=disclosure_id,
                            error=str(exc),
                        )
                    except Exception as exc:
                        await storage.mark_brief_failed(
                            disclosure_id,
                            error=str(exc),
                            model=cfg.model,
                        )
                        log.warning(
                            "brief_failed",
                            disclosure_id=disclosure_id,
                            error=str(exc),
                        )
                    processed += 1
            finally:
                if owns_http:
                    await http.aclose()
                if owns_provider:
                    aclose = getattr(prov, "aclose", None)
                    if callable(aclose):
                        await _maybe_await(aclose())

    # Late follow-up sweep even when the daily cap blocked new summarizes or
    # the pending queue was empty (primary may have delivered after ready).
    if notify is not None:
        await _sweep_brief_followups(
            storage,
            notify=notify,
            limit=max(5, limit),
        )
    return processed
