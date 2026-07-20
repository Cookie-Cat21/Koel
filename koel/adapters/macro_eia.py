"""EIA Open Data — Brent / WTI spot → macro_series.

Prefer ``EIA_API_KEY`` (v2 API). When the key is missing, fall back to the
public PET bulk zip (no key required — EIA bulk facility). Attribute EIA.
Flag: ``EIA_OIL_ENABLED`` (default off).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import zipfile
from datetime import UTC, date, datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

ATTRIBUTION = "U.S. Energy Information Administration (EIA)"

# koel series_id → EIA series id
_SERIES = {
    "BRENT_SPOT": "PET.RBRTE.D",
    "WTI_SPOT": "PET.RWTC.D",
}

_EIA_BULK_PET_URL = "https://www.eia.gov/opendata/bulk/PET.zip"


def _parse_period(raw: object) -> date | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if len(s) >= 10 and s[4] == "-":
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None
    # Bulk files use YYYYMMDD
    if len(s) == 8 and s.isdigit():
        try:
            return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    return None


def _rows_from_pairs(
    pairs: list[tuple[date, float]],
    *,
    series_id: str,
    raw_hash: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d, v in pairs:
        if not (v > 0):
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


def _parse_eia_payload(payload: dict[str, Any], *, series_id: str) -> list[dict[str, Any]]:
    data = payload.get("response", {}).get("data") or payload.get("data") or []
    if not isinstance(data, list):
        return []
    raw_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    pairs: list[tuple[date, float]] = []
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
        d = _parse_period(period)
        if d is None:
            continue
        pairs.append((d, v))
    return _rows_from_pairs(pairs, series_id=series_id, raw_hash=raw_hash)


def _parse_bulk_series_line(
    line: bytes,
    *,
    wanted: dict[str, str],
    length: int,
) -> list[dict[str, Any]]:
    """Parse one EIA bulk JSON line if it matches a wanted series."""
    try:
        obj = json.loads(line)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(obj, dict):
        return []
    eia_id = obj.get("series_id")
    if not isinstance(eia_id, str) or eia_id not in wanted:
        return []
    koel_id = wanted[eia_id]
    data = obj.get("data")
    if not isinstance(data, list):
        return []
    pairs: list[tuple[date, float]] = []
    for item in data:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        d = _parse_period(item[0])
        try:
            v = float(item[1])
        except (TypeError, ValueError):
            continue
        if d is None:
            continue
        pairs.append((d, v))
    pairs.sort(key=lambda x: x[0], reverse=True)
    if length > 0:
        pairs = pairs[: int(length)]
    raw_hash = hashlib.sha256(line[:4096]).hexdigest()[:16]
    return _rows_from_pairs(pairs, series_id=koel_id, raw_hash=raw_hash)


async def _fetch_eia_oil_api(
    *,
    key: str,
    http: httpx.AsyncClient,
    length: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for series_id, eia_id in _SERIES.items():
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
        log.info("eia_oil: api %s → %s points", series_id, len(rows))
    return out


async def _fetch_eia_oil_bulk(
    *,
    http: httpx.AsyncClient,
    length: int,
    url: str = _EIA_BULK_PET_URL,
) -> list[dict[str, Any]]:
    """Key-free fallback: scan PET.zip for Brent/WTI daily series only."""
    resp = await http.get(url)
    resp.raise_for_status()
    wanted = {eia: koel for koel, eia in _SERIES.items()}
    out: list[dict[str, Any]] = []
    found: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        target = next((n for n in names if n.endswith(".txt")), None)
        if target is None:
            log.warning("eia_oil: bulk zip has no .txt member")
            return []
        with zf.open(target) as fh:
            for raw in fh:
                rows = _parse_bulk_series_line(raw, wanted=wanted, length=length)
                if not rows:
                    continue
                sid = str(rows[0]["series_id"])
                if sid in found:
                    continue
                found.add(sid)
                out.extend(rows)
                log.info("eia_oil: bulk %s → %s points", sid, len(rows))
                if found >= set(_SERIES):
                    break
    return out


async def fetch_eia_oil_rows(
    *,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
    length: int = 120,
) -> list[dict[str, Any]]:
    key = (api_key if isinstance(api_key, str) else "") or os.getenv("EIA_API_KEY", "")
    key = key.strip() if isinstance(key, str) else ""

    own = client is None
    http = client or httpx.AsyncClient(timeout=120.0, follow_redirects=True)
    try:
        if key:
            rows = await _fetch_eia_oil_api(key=key, http=http, length=length)
            if rows:
                return rows
            log.warning("eia_oil: API returned empty — trying PET bulk zip")
        else:
            log.info("eia_oil: EIA_API_KEY missing — using PET bulk zip")
        return await _fetch_eia_oil_bulk(http=http, length=length)
    except Exception:
        log.exception("eia_oil: fetch failed")
        return []
    finally:
        if own:
            await http.aclose()
