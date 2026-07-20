"""EIA Open Data — Brent / WTI spot → macro_series.

Requires ``EIA_API_KEY``. Public domain US gov data; attribute EIA.
Flag: ``EIA_OIL_ENABLED`` (default off).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import UTC, date, datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

ATTRIBUTION = "U.S. Energy Information Administration (EIA)"

# EIA v2 petroleum spot price series ids
_SERIES = {
    "BRENT_SPOT": "PET.RBRTE.D",
    "WTI_SPOT": "PET.RWTC.D",
}


def _parse_eia_payload(payload: dict[str, Any], *, series_id: str) -> list[dict[str, Any]]:
    data = payload.get("response", {}).get("data") or payload.get("data") or []
    if not isinstance(data, list):
        return []
    raw_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    out: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        period = row.get("period") or row.get("date")
        value = row.get("value")
        if period is None or value is None:
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        if not (v > 0):
            continue
        try:
            d = date.fromisoformat(str(period)[:10])
        except ValueError:
            continue
        ts = datetime(d.year, d.month, d.day, 12, 0, tzinfo=UTC)
        out.append(
            {
                "source": "eia_oil",
                "series_id": series_id,
                "ts": ts,
                "value": v,
                "unit": "USD/bbl",
                "as_of_date": d,
                "attribution": ATTRIBUTION,
                "raw_hash": raw_hash,
            }
        )
    out.sort(key=lambda r: r["ts"])
    return out


async def fetch_eia_oil_rows(
    *,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
    length: int = 120,
) -> list[dict[str, Any]]:
    key = (api_key if isinstance(api_key, str) else "") or os.getenv("EIA_API_KEY", "")
    key = key.strip() if isinstance(key, str) else ""
    if not key:
        log.warning("eia_oil: EIA_API_KEY missing — skip")
        return []

    own = client is None
    http = client or httpx.AsyncClient(timeout=45.0, follow_redirects=True)
    out: list[dict[str, Any]] = []
    try:
        for series_id, eia_id in _SERIES.items():
            # facet route for daily spot prices
            url = (
                "https://api.eia.gov/v2/petroleum/pri/spt/data/"
                f"?api_key={key}&frequency=daily"
                f"&data[0]=value&facets[series][]={eia_id}"
                f"&sort[0][column]=period&sort[0][direction]=desc"
                f"&length={int(length)}"
            )
            resp = await http.get(url)
            if resp.status_code >= 400:
                log.warning(
                    "eia_oil: %s HTTP %s %s",
                    eia_id,
                    resp.status_code,
                    resp.text[:200],
                )
                continue
            payload = resp.json()
            rows = _parse_eia_payload(payload, series_id=series_id)
            out.extend(rows)
            log.info("eia_oil: %s → %s points", series_id, len(rows))
    finally:
        if own:
            await http.aclose()
    return out
