"""Sync official CSE board lists into ``people`` / ``person_company_roles``.

Source: ``POST /companyProfile`` (``topPosts`` + ``infoCompanyDirector``).
Replaces prior active roles for each symbol so PDF noise does not linger.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from chime.adapters.cse import CSEClient
from chime.config import Settings
from chime.graph import GraphSettings, graph_enabled
from chime.logging_setup import get_logger

log = get_logger(__name__)

CSE_SOURCE = "cse_company_profile"


class DirectorsStorage(Protocol):
    async def upsert_stock(
        self, symbol: str, name: str | None = None, sector: str | None = None
    ) -> Any: ...

    async def list_top_symbols_by_market_cap(self, *, limit: int = 60) -> list[str]: ...

    async def list_voting_share_symbols(self, *, limit: int | None = None) -> list[str]: ...

    async def deactivate_person_roles_for_symbol(self, symbol: str) -> int: ...

    async def deactivate_non_cse_person_roles_for_symbol(
        self, symbol: str, *, source: str = "cse_company_profile"
    ) -> int: ...

    async def upsert_person(
        self, *, display_name: str, name_norm: str
    ) -> dict[str, Any]: ...

    async def upsert_person_company_role(self, row: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class DirectorsSyncResult:
    symbols_targeted: int
    symbols_updated: int
    symbols_skipped: int
    symbols_failed: int
    seats_written: int
    roles_written: int


def directors_sync_enabled(settings: GraphSettings | None = None) -> bool:
    """Ride COMPANY_PEOPLE_ENABLED / COMPANY_GRAPH_ENABLED (same research surface)."""
    import os

    raw = os.getenv("COMPANY_PEOPLE_ENABLED")
    if isinstance(raw, str) and raw.strip() != "":
        return raw.strip() == "1"
    return graph_enabled(settings)


async def sync_symbol_directors(
    *,
    storage: DirectorsStorage,
    cse: CSEClient,
    symbol: str,
) -> tuple[int, int]:
    """Fetch CSE board for one symbol; replace active roles. Returns (seats, roles)."""
    from chime.extractors.cse_directors import merge_cse_board

    sym = symbol.strip().upper()
    profile = await cse.fetch_company_profile(sym)
    if not profile:
        return 0, 0

    # Ensure FK target exists (and refresh sector/name when CSE provides them).
    await storage.upsert_stock(
        sym,
        name=profile.get("name") if isinstance(profile.get("name"), str) else None,
        sector=profile.get("sector")
        if isinstance(profile.get("sector"), str)
        else None,
    )

    parsed = merge_cse_board(
        top_posts=profile.get("top_posts")
        if isinstance(profile.get("top_posts"), list)
        else [],
        directors=profile.get("directors")
        if isinstance(profile.get("directors"), list)
        else [],
        key_executives=profile.get("key_executives")
        if isinstance(profile.get("key_executives"), list)
        else [],
    )
    if not parsed:
        # Still clear stale PDF seats when CSE returns an empty board.
        await storage.deactivate_person_roles_for_symbol(sym)
        return 0, 0

    roles_written = 0
    for seat in parsed:
        person = await storage.upsert_person(
            display_name=seat.display_name,
            name_norm=seat.name_norm,
        )
        for role in seat.roles:
            await storage.upsert_person_company_role(
                {
                    "person_id": person["id"],
                    "symbol": sym,
                    "role": role,
                    "confidence": "high",
                    "evidence_disclosure_id": None,
                    "evidence_page": None,
                    "evidence_snippet": seat.designation_raw[:240] or None,
                    "extract_notes": {
                        "source": CSE_SOURCE,
                        "director_id": seat.director_id,
                        "source_bucket": seat.source_bucket,
                        "designation": seat.designation_raw,
                    },
                }
            )
            roles_written += 1
    # After writing CSE seats, drop any remaining non-CSE roles for this issuer
    # (PDF extracts that did not collide on person/role).
    await storage.deactivate_non_cse_person_roles_for_symbol(sym, source=CSE_SOURCE)
    return len(parsed), roles_written


async def run_directors_sync(
    *,
    settings: Settings,
    storage: DirectorsStorage,
    cse: CSEClient,
    limit: int | None = None,
    sleep_seconds: float | None = None,
    symbols: list[str] | None = None,
    force: bool = False,
    top_by_mcap: bool = True,
) -> DirectorsSyncResult:
    """Backfill official directors for many issuers.

    When ``force`` is False and people/graph flags are off, no-op.
    """
    if not force and not directors_sync_enabled():
        log.info("directors_sync_disabled")
        return DirectorsSyncResult(0, 0, 0, 0, 0, 0)

    pause = sleep_seconds if sleep_seconds is not None else 0.35
    if not isinstance(pause, int | float) or isinstance(pause, bool) or pause < 0:
        pause = 0.35

    if symbols:
        targets = [
            s.strip().upper()
            for s in symbols
            if isinstance(s, str) and s.strip()
        ]
    elif top_by_mcap:
        lim = 80
        if (
            limit is not None
            and isinstance(limit, int)
            and not isinstance(limit, bool)
            and limit > 0
        ):
            lim = min(limit, 300)
        targets = await storage.list_top_symbols_by_market_cap(limit=lim)
        if not targets:
            targets = await storage.list_voting_share_symbols(limit=lim)
    else:
        targets = await storage.list_voting_share_symbols(
            limit=limit
            if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0
            else None
        )

    if (
        symbols is None
        and limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
        and len(targets) > limit
    ):
        targets = targets[:limit]

    updated = 0
    skipped = 0
    failed = 0
    seats_total = 0
    roles_total = 0
    for idx, symbol in enumerate(targets):
        try:
            seats, roles = await sync_symbol_directors(
                storage=storage, cse=cse, symbol=symbol
            )
            if seats == 0:
                skipped += 1
                log.info("directors_sync_empty", symbol=symbol)
            else:
                updated += 1
                seats_total += seats
                roles_total += roles
                log.info(
                    "directors_sync_ok",
                    symbol=symbol,
                    seats=seats,
                    roles=roles,
                )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log.warning("directors_sync_failed", symbol=symbol, error=str(exc)[:200])
        if pause > 0 and idx + 1 < len(targets):
            await asyncio.sleep(float(pause))

    result = DirectorsSyncResult(
        symbols_targeted=len(targets),
        symbols_updated=updated,
        symbols_skipped=skipped,
        symbols_failed=failed,
        seats_written=seats_total,
        roles_written=roles_total,
    )
    log.info("directors_sync_done", **asdict(result))
    return result
