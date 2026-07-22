"""Backfill ``issuer_profiles`` from companyInfoSummery + companyProfile.

Polite sleep between symbols. CLI: ``issuer-profile-backfill``.
Dash reads Postgres only — this is the CSE → DB bridge for ISIN/beta/contact.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any

from koel.adapters.cse import CSEClient
from koel.config import Settings
from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)

MARKET_INDEX_SYMBOLS: frozenset[str] = frozenset({"ASPI", "SNP_SL20"})
OPS_JOB_ID = "issuer-profile-backfill"
_MAX_ISSUES = 12
_DETAIL_MAX = 480


@dataclass(frozen=True, slots=True)
class IssuerProfileBackfillResult:
    symbols_targeted: int
    symbols_updated: int
    symbols_skipped: int
    symbols_failed: int
    issues: tuple[str, ...] = ()


def _trim_detail(issues: list[str]) -> str | None:
    if not issues:
        return None
    text = "; ".join(issues[:_MAX_ISSUES])
    if len(issues) > _MAX_ISSUES:
        text = f"{text}; …+{len(issues) - _MAX_ISSUES} more"
    if len(text) > _DETAIL_MAX:
        text = text[: _DETAIL_MAX - 1].rstrip() + "…"
    return text


def _top_posts_json(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for row in raw[:12]:
        if not isinstance(row, dict):
            continue
        first = row.get("firstName")
        last = row.get("lastName")
        role = row.get("designationOther")
        parts: list[str] = []
        if isinstance(first, str) and first.strip():
            parts.append(first.strip())
        if isinstance(last, str) and last.strip():
            parts.append(last.strip())
        name = " ".join(parts).strip()
        if not name:
            continue
        role_s = role.strip() if isinstance(role, str) and role.strip() else ""
        out.append({"name": name[:200], "role": role_s[:200]})
    return out


async def run_issuer_profile_backfill(
    *,
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    limit: int | None = None,
    sleep_seconds: float | None = None,
    only_missing: bool = True,
    force: bool = False,
    symbols: list[str] | None = None,
) -> IssuerProfileBackfillResult:
    """Upsert issuer_profiles for listed companies.

    When ``force`` is False and ``ISSUER_PROFILE_BACKFILL_ENABLED`` is off, no-op.
    """
    if not force and not settings.issuer_profile_backfill_enabled:
        log.info("issuer_profile_backfill_disabled")
        return IssuerProfileBackfillResult(0, 0, 0, 0, ())

    pause = (
        sleep_seconds
        if sleep_seconds is not None
        else settings.issuer_profile_backfill_sleep_seconds
    )
    if not isinstance(pause, int | float) or isinstance(pause, bool) or pause < 0:
        pause = 0.4

    if symbols:
        targets = [
            s.strip().upper()
            for s in symbols
            if isinstance(s, str) and s.strip()
        ]
    elif only_missing:
        targets = await storage.list_symbols_missing_issuer_profile()
    else:
        targets = [
            s
            for s in await storage.list_symbols_with_daily_bars()
            if isinstance(s, str) and s.strip().upper() not in MARKET_INDEX_SYMBOLS
        ]

    if (
        limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
    ):
        targets = targets[:limit]

    updated = 0
    skipped = 0
    failed = 0
    issues: list[str] = []

    for idx, symbol in enumerate(targets):
        sym = symbol.strip().upper() if isinstance(symbol, str) else ""
        if not sym or sym in MARKET_INDEX_SYMBOLS:
            skipped += 1
            if pause > 0 and idx + 1 < len(targets):
                await asyncio.sleep(float(pause))
            continue

        try:
            await storage.upsert_stock(sym)
            bundle = await cse.fetch_company_info_bundle(sym)
            profile = await cse.fetch_company_profile(sym)
            if not bundle and not profile:
                skipped += 1
                log.info("issuer_profile_backfill_skip_empty", symbol=sym)
            else:
                row: dict[str, Any] = {"symbol": sym}
                if isinstance(bundle, dict):
                    row.update(bundle)
                if isinstance(profile, dict):
                    for key in (
                        "board_type",
                        "founded",
                        "fin_year_end",
                        "website",
                        "email",
                        "phone",
                        "address",
                        "auditors",
                        "secretaries",
                        "business_summary",
                    ):
                        val = profile.get(key)
                        if val is not None:
                            row[key] = val
                    # Prefer profile sector onto stocks when present.
                    sector = profile.get("sector")
                    if isinstance(sector, str) and sector.strip():
                        await storage.upsert_stock(sym, sector=sector.strip())
                    row["top_posts"] = json.dumps(
                        _top_posts_json(profile.get("top_posts"))
                    )
                else:
                    row["top_posts"] = "[]"
                await storage.upsert_issuer_profile(row)
                updated += 1
                log.info("issuer_profile_backfill_ok", symbol=sym)
        except Exception as exc:
            failed += 1
            issue = f"{sym}: {str(exc)[:200]}"
            issues.append(issue)
            log.warning("issuer_profile_backfill_failed", symbol=sym, error=issue)

        if pause > 0 and idx + 1 < len(targets):
            await asyncio.sleep(float(pause))

    targeted = len(targets)
    if failed > 0:
        status = "failed"
        summary = (
            f"failed={failed} updated={updated} skipped={skipped} "
            f"targeted={targeted}"
        )
    else:
        status = "ok"
        summary = (
            f"updated={updated} skipped={skipped} failed={failed} "
            f"targeted={targeted}"
        )

    detail = _trim_detail(issues)
    try:
        await storage.upsert_ops_job_status(
            job_id=OPS_JOB_ID,
            status=status,
            summary=summary,
            detail=detail,
        )
    except Exception as exc:
        log.warning("issuer_profile_ops_status_failed", error=str(exc))

    result = IssuerProfileBackfillResult(
        symbols_targeted=targeted,
        symbols_updated=updated,
        symbols_skipped=skipped,
        symbols_failed=failed,
        issues=tuple(issues[:_MAX_ISSUES]),
    )
    log.info(
        "issuer_profile_backfill_done",
        **{k: v for k, v in asdict(result).items() if k != "issues"},
        status=status,
        issue_count=len(issues),
    )
    return result
