"""Orchestrate Tier B macro adapters → Postgres ``macro_series``."""

from __future__ import annotations

import logging
from typing import Any

from koel.adapters.macro_cbsl import fetch_cbsl_fx_rows
from koel.adapters.macro_eia import fetch_eia_oil_rows
from koel.config import Settings
from koel.storage import Storage

log = logging.getLogger(__name__)


async def run_macro_tick(
    storage: Storage,
    settings: Settings,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Pull enabled macro feeds and upsert. Returns counts per source.

    When ``force`` is set, pull CBSL/EIA even if flags are off (ops smoke).
    Prod still requires intake checklist before leaving flags on.
    """
    result: dict[str, Any] = {
        "cbsl_fx": 0,
        "eia_oil": 0,
        "skipped": [],
    }

    pull_fx = settings.cbsl_fx_enabled or force
    pull_oil = settings.eia_oil_enabled or force

    if pull_fx:
        try:
            rows = await fetch_cbsl_fx_rows(max_rows=180)
            n = await storage.upsert_macro_series(rows)
            result["cbsl_fx"] = n
        except Exception:
            log.exception("macro_tick: cbsl_fx failed")
            result["skipped"].append("cbsl_fx_error")
    else:
        result["skipped"].append("cbsl_fx_disabled")

    if pull_oil:
        try:
            rows = await fetch_eia_oil_rows(length=180)
            n = await storage.upsert_macro_series(rows)
            result["eia_oil"] = n
        except Exception:
            log.exception("macro_tick: eia_oil failed")
            result["skipped"].append("eia_oil_error")
    else:
        result["skipped"].append("eia_oil_disabled")

    # Tourism / food adapters land when intake checklist is green;
    # keep slots honest so ops see intent.
    if not settings.sltda_tourism_enabled:
        result["skipped"].append("sltda_tourism_disabled")
    if not settings.dcs_food_enabled:
        result["skipped"].append("dcs_food_disabled")

    return result
