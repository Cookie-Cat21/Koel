"""Best-effort one-liners for Telegram fire context (no LLM)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from koel.domain import _CTRL_RE, truncate_disclosure_title
from koel.logging_setup import get_logger

log = get_logger(__name__)

_CONTEXT_MAX = 120
_RECENT_HOURS = 48


def _as_utc_aware(value: datetime) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    try:
        return value.astimezone(UTC)
    except Exception:
        return None


async def build_price_fire_context(
    storage: Any,
    *,
    symbol: str,
    snapshot: Any,
) -> str | None:
    """One short line from Postgres facts: latest disclosure title if <48h.

    Never raises. Keep under ~120 chars. No LLM.
    """
    try:
        if not isinstance(symbol, str) or not symbol.strip():
            return None
        getter = getattr(storage, "get_latest_disclosure", None)
        if getter is None:
            getter = getattr(storage, "get_latest_disclosure_for_symbol", None)
        if getter is None:
            return None
        disc = await getter(symbol.strip().upper())
        if disc is None:
            return None
        published = getattr(disc, "published_at", None)
        published_utc = _as_utc_aware(published) if isinstance(published, datetime) else None
        if published_utc is None:
            return None
        snap_ts = getattr(snapshot, "ts", None)
        as_of = _as_utc_aware(snap_ts) if isinstance(snap_ts, datetime) else None
        if as_of is None:
            as_of = datetime.now(UTC)
        age = as_of - published_utc
        if age < timedelta(0) or age > timedelta(hours=_RECENT_HOURS):
            return None
        raw_title = getattr(disc, "title", None)
        if not isinstance(raw_title, str) or not raw_title.strip():
            return None
        title = truncate_disclosure_title(raw_title, max_len=80)
        if not title:
            return None
        line = f"Recent filing: {title}"
        line = _CTRL_RE.sub("", line).strip()
        if len(line) > _CONTEXT_MAX:
            line = line[: _CONTEXT_MAX - 1].rstrip() + "…"
        return line or None
    except Exception as exc:
        log.warning(
            "price_fire_context_failed",
            symbol=symbol if isinstance(symbol, str) else None,
            error=str(exc)[:240],
        )
        return None
