"""Public Telegram channel posts — market open pulse and close summary.

Builds factual message bodies from Postgres only (no LLM). Callers send via
``Poller.send`` when ``TELEGRAM_PUBLIC_CHANNEL_ID`` is set. Fail soft: return
``None`` when there is nothing useful to post.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, time
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from koel.domain import _clamp_telegram_message, disclaimer
from koel.logging_setup import get_logger

log = get_logger(__name__)

_COLOMBO = ZoneInfo("Asia/Colombo")

# Display labels for persisted index codes.
_INDEX_LABELS = {
    "ASPI": "ASPI",
    "SNP_SL20": "S&P SL20",
}

MAX_MOVER_LINES = 5
CHANNEL_CTA = "Get alerts for your stocks → set via the koel bot"


class ChannelStorage(Protocol):
    async def latest_index_snapshots(
        self, codes: list[str] | None = None
    ) -> list[dict[str, Any]]: ...

    async def list_market_movers(self, *, limit: int = 5) -> list[dict[str, Any]]: ...

    async def count_disclosures_published_since(self, since: datetime) -> int: ...


def colombo_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(_COLOMBO)
    if now.tzinfo is None:
        return now.replace(tzinfo=_COLOMBO)
    return now.astimezone(_COLOMBO)


def channel_cta_line() -> str:
    """CTA footer; optional ``TELEGRAM_BOT_USERNAME`` → t.me deep link."""
    raw = os.getenv("TELEGRAM_BOT_USERNAME", "")
    if isinstance(raw, str) and raw.strip():
        handle = raw.strip().lstrip("@")
        if handle and all(c.isalnum() or c == "_" for c in handle):
            return f"Get alerts for your stocks → https://t.me/{handle}"
    return CHANNEL_CTA


def _fmt_pct(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(pct):
        return None
    return f"{pct:+.2f}%"


def _fmt_price(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "?"
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "?"


def _format_index_line(row: dict[str, Any]) -> str | None:
    code = row.get("code")
    if not isinstance(code, str) or not code.strip():
        return None
    label = _INDEX_LABELS.get(code.strip().upper(), code.strip().upper())
    value = row.get("value")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    pct_s = _fmt_pct(row.get("change_pct"))
    if pct_s is None:
        return f"{label} {_fmt_price(value)}"
    return f"{label} {_fmt_price(value)} ({pct_s})"


async def _safe_indexes(storage: Any) -> list[dict[str, Any]]:
    fn = getattr(storage, "latest_index_snapshots", None)
    if not callable(fn):
        # Fallback: change_pct only via latest_index_change_pct.
        pct_fn = getattr(storage, "latest_index_change_pct", None)
        if not callable(pct_fn):
            return []
        out: list[dict[str, Any]] = []
        for code in ("ASPI", "SNP_SL20"):
            try:
                pct = await pct_fn(code)
            except Exception:
                log.exception("channel_index_pct_failed", code=code)
                continue
            if isinstance(pct, bool) or not isinstance(pct, int | float):
                continue
            out.append({"code": code, "value": None, "change_pct": float(pct)})
        return out
    try:
        rows = await fn(["ASPI", "SNP_SL20"])
    except Exception:
        log.exception("channel_latest_indexes_failed")
        return []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


async def _safe_movers(storage: Any, *, limit: int = MAX_MOVER_LINES) -> list[dict[str, Any]]:
    fn = getattr(storage, "list_market_movers", None)
    if not callable(fn):
        return []
    try:
        rows = await fn(limit=limit)
    except Exception:
        log.exception("channel_market_movers_failed")
        return []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


async def _safe_disclosure_count_today(storage: Any, *, now: datetime | None = None) -> int | None:
    fn = getattr(storage, "count_disclosures_published_since", None)
    if not callable(fn):
        return None
    local = colombo_now(now)
    since = datetime.combine(local.date(), time(0, 0), tzinfo=_COLOMBO)
    try:
        n = await fn(since)
    except Exception:
        log.exception("channel_disclosure_count_failed")
        return None
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        return None
    return n


async def build_open_pulse(storage: Any) -> str | None:
    """09:35-style open pulse: indexes + market-open one-liner. None if no data."""
    indexes = await _safe_indexes(storage)
    index_lines: list[str] = []
    for row in indexes:
        # Prefer rows with a real value; pct-only fallback still useful.
        line = _format_index_line(row)
        if line is None:
            code = row.get("code")
            pct_s = _fmt_pct(row.get("change_pct"))
            if isinstance(code, str) and pct_s is not None:
                label = _INDEX_LABELS.get(code.strip().upper(), code.strip().upper())
                line = f"{label} {pct_s}"
        if line:
            index_lines.append(line)
    if not index_lines:
        return None

    lines = [
        "koel open pulse — CSE is open",
        "",
        *index_lines,
        "",
        channel_cta_line(),
        disclaimer(),
    ]
    return _clamp_telegram_message("\n".join(lines))


async def build_close_summary(
    storage: Any, *, now: datetime | None = None
) -> str | None:
    """EOD close summary: indexes, top movers, disclosure count. None if empty."""
    local = colombo_now(now)
    indexes = await _safe_indexes(storage)
    movers = await _safe_movers(storage)
    disc_n = await _safe_disclosure_count_today(storage, now=local)

    index_lines: list[str] = []
    for row in indexes:
        line = _format_index_line(row)
        if line is None:
            code = row.get("code")
            pct_s = _fmt_pct(row.get("change_pct"))
            if isinstance(code, str) and pct_s is not None:
                label = _INDEX_LABELS.get(code.strip().upper(), code.strip().upper())
                line = f"{label} {pct_s}"
        if line:
            index_lines.append(line)

    mover_lines: list[str] = []
    for m in movers[:MAX_MOVER_LINES]:
        sym = m.get("symbol")
        if not isinstance(sym, str) or not sym.strip():
            continue
        pct_s = _fmt_pct(m.get("change_pct")) or "n/a"
        mover_lines.append(f"• {sym.strip().upper()} {_fmt_price(m.get('price'))} ({pct_s})")

    if not index_lines and not mover_lines and disc_n is None:
        return None

    lines = [f"koel close summary — {local.date().isoformat()} (SLT)"]
    if index_lines:
        lines.append("")
        lines.append("Indexes:")
        lines.extend(index_lines)
    if mover_lines:
        lines.append("")
        lines.append("Top movers (|%|):")
        lines.extend(mover_lines)
    if disc_n is not None:
        lines.append("")
        lines.append(f"Disclosures filed today: {disc_n}")
    lines.append("")
    lines.append(channel_cta_line())
    lines.append(disclaimer())
    return _clamp_telegram_message("\n".join(lines))
