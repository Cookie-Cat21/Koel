"""Phase 1 stub worker — no LLM calls until AI_BRIEFS_ENABLED=1 (Phase 2)."""

from __future__ import annotations

from typing import Protocol

import structlog

from chime.briefs import BriefSettings, BriefStatus, briefs_enabled

log = structlog.get_logger("chime.briefs")


class _BriefEnqueuer(Protocol):
    async def enqueue_disclosure_brief(
        self,
        disclosure_id: int,
        *,
        status: str = "pending",
    ) -> bool: ...


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
            "brief_enqueue_stub",
            disclosure_id=disclosure_id,
            provider=cfg.provider,
            model=cfg.model,
        )
    return status
