"""Persist CSE STOMP topic payloads into existing koel Postgres tables."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from koel.adapters.cse_stomp import (
    TOPIC_ASPI,
    TOPIC_DAYTRADE,
    TOPIC_SNP,
    TOPIC_STATUS,
    TOPIC_SUMMARY,
    TOPIC_TODAY_SHARE,
    daytrade_rows_to_snapshots,
    index_payload_to_snapshot,
    status_payload_to_text,
    summary_payload_to_daily_row,
    today_share_rows_to_snapshots,
)
from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)


class StompIngestState:
    """Mutable live status from STOMP (for health / optional market gate)."""

    __slots__ = (
        "market_status",
        "last_index_at",
        "last_board_slice_at",
        "last_summary_at",
        "indexes_written",
        "snapshots_written",
        "summaries_written",
    )

    def __init__(self) -> None:
        self.market_status: str | None = None
        self.last_index_at: datetime | None = None
        self.last_board_slice_at: datetime | None = None
        self.last_summary_at: datetime | None = None
        self.indexes_written: int = 0
        self.snapshots_written: int = 0
        self.summaries_written: int = 0


async def handle_stomp_message(
    storage: Storage,
    state: StompIngestState,
    destination: str,
    payload: Any,
) -> None:
    """Route one STOMP MESSAGE body into storage. Fail-soft per topic."""
    now = datetime.now(UTC)
    try:
        if destination == TOPIC_ASPI:
            snap = index_payload_to_snapshot(
                payload,
                default_code="ASPI",
                default_name="All Share Price Index",
                now=now,
            )
            if snap is None:
                return
            stored = await storage.persist_index_snapshots([snap])
            state.indexes_written += len(stored)
            state.last_index_at = now
            return

        if destination == TOPIC_SNP:
            snap = index_payload_to_snapshot(
                payload,
                default_code="SNP_SL20",
                default_name="S&P Sri Lanka 20",
                now=now,
            )
            if snap is None:
                return
            # CSE SNP topic often omits code; keep koel’s SNP_SL20 convention.
            if snap.code in {"SNP", "S&P", "SPSL20", "S&P SL20"}:
                snap = snap.model_copy(update={"code": "SNP_SL20"})
            stored = await storage.persist_index_snapshots([snap])
            state.indexes_written += len(stored)
            state.last_index_at = now
            return

        if destination == TOPIC_STATUS:
            text = status_payload_to_text(payload)
            if text:
                state.market_status = text
            return

        if destination == TOPIC_SUMMARY:
            row = summary_payload_to_daily_row(payload)
            if row is None:
                return
            n = await storage.upsert_market_daily_summary([row])
            state.summaries_written += n
            state.last_summary_at = now
            return

        if destination == TOPIC_TODAY_SHARE:
            snaps = today_share_rows_to_snapshots(payload, now=now)
            if not snaps:
                return
            stored = await storage.persist_market_snapshots(snaps)
            state.snapshots_written += len(stored)
            state.last_board_slice_at = now
            return

        if destination == TOPIC_DAYTRADE:
            snaps = daytrade_rows_to_snapshots(payload, now=now)
            if not snaps:
                return
            stored = await storage.persist_market_snapshots(snaps)
            state.snapshots_written += len(stored)
            state.last_board_slice_at = now
            return

        # top-gainers / top-looses / most-active: dash movers already derive
        # from price_snapshots; no separate leaderboard table yet.
    except Exception as exc:
        log.warning(
            "stomp_ingest_failed",
            destination=destination,
            error=str(exc)[:240],
        )
