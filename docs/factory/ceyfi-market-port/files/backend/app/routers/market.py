"""CSE Market module — Chime-backed (or mock) watchlist + alerts for Ceyfi host UI.

Ceyfi never scrapes cse.lk. When CHIME_API_BASE is set, we proxy Chime's
/api/v1/* with a demo session; otherwise we return deterministic mocks so
the Market UI works in demos offline.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException

from app.services.auth import DEMO_PERSONAS, require_session

router = APIRouter(prefix="/api/market", tags=["market"])

CHIME_API_BASE = os.getenv("CHIME_API_BASE", "").rstrip("/")
CHIME_DEMO_TELEGRAM_ID = os.getenv("CHIME_DEMO_TELEGRAM_ID", "123456789")

NFA = (
    "Information only — not financial advice. Not an invitation to deal in "
    "securities. Ceyfi is not a stockbroker; place trades with your licensed broker."
)

# Per-persona demo watchlists (mock mode)
_MOCK_WATCH: dict[str, list[dict[str, Any]]] = {
    "SEY-USR-001": [
        {
            "symbol": "COMB.N0000",
            "name": "Commercial Bank of Ceylon PLC",
            "price": 128.5,
            "change_pct": 1.2,
            "volume": 245_000,
        },
        {
            "symbol": "JKH.N0000",
            "name": "John Keells Holdings PLC",
            "price": 22.4,
            "change_pct": -0.4,
            "volume": 1_120_000,
        },
        {
            "symbol": "CARS.N0000",
            "name": "Carson Cumberbatch PLC",
            "price": 380.0,
            "change_pct": 0.8,
            "volume": 42_000,
        },
    ],
    "SEY-USR-003": [
        {
            "symbol": "DIAL.N0000",
            "name": "Dialog Axiata PLC",
            "price": 11.2,
            "change_pct": 0.0,
            "volume": 890_000,
        },
    ],
    "SEY-BIZ-001": [
        {
            "symbol": "HNB.N0000",
            "name": "Hatton National Bank PLC",
            "price": 210.0,
            "change_pct": -0.7,
            "volume": 156_000,
        },
        {
            "symbol": "SAMP.N0000",
            "name": "Sampath Bank PLC",
            "price": 78.5,
            "change_pct": 0.3,
            "volume": 98_000,
        },
    ],
}

_MOCK_ALERTS: dict[str, list[dict[str, Any]]] = {
    "SEY-USR-001": [
        {
            "id": "a-comb-above",
            "symbol": "COMB.N0000",
            "type": "price_above",
            "threshold": 125.0,
            "active": True,
            "created_at": "2026-07-10T04:00:00Z",
        },
        {
            "id": "a-jkh-move",
            "symbol": "JKH.N0000",
            "type": "daily_move",
            "threshold": 3.0,
            "active": True,
            "created_at": "2026-07-12T04:00:00Z",
        },
        {
            "id": "a-cars-disc",
            "symbol": "CARS.N0000",
            "type": "disclosure",
            "threshold": None,
            "active": True,
            "created_at": "2026-07-14T04:00:00Z",
        },
    ],
    "SEY-USR-003": [
        {
            "id": "a-dial-below",
            "symbol": "DIAL.N0000",
            "type": "price_below",
            "threshold": 10.5,
            "active": True,
            "created_at": "2026-07-11T04:00:00Z",
        },
    ],
    "SEY-BIZ-001": [
        {
            "id": "a-hnb-above",
            "symbol": "HNB.N0000",
            "type": "price_above",
            "threshold": 220.0,
            "active": True,
            "created_at": "2026-07-09T04:00:00Z",
        },
    ],
}

_MOCK_FIRES: dict[str, list[dict[str, Any]]] = {
    "SEY-USR-001": [
        {
            "id": "f-1",
            "alert_id": "a-comb-above",
            "symbol": "COMB.N0000",
            "type": "price_above",
            "title": "COMB crossed above LKR 125",
            "message": "COMB.N0000 last 128.50 — above your 125 alert. Not financial advice.",
            "price": 128.5,
            "fired_at": "2026-07-17T05:12:00Z",
            "delivery_status": "sent",
        },
        {
            "id": "f-2",
            "alert_id": "a-cars-disc",
            "symbol": "CARS.N0000",
            "type": "disclosure",
            "title": "New disclosure on CARS",
            "message": "Annual report filing detected for CARS.N0000. Review on CSE — not advice.",
            "price": 380.0,
            "fired_at": "2026-07-16T09:40:00Z",
            "delivery_status": "sent",
        },
    ],
    "SEY-USR-003": [],
    "SEY-BIZ-001": [
        {
            "id": "f-3",
            "alert_id": "a-hnb-above",
            "symbol": "HNB.N0000",
            "type": "price_above",
            "title": "HNB near your alert level",
            "message": "HNB.N0000 last 210.00 — watching for 220. Demo fire. Not advice.",
            "price": 210.0,
            "fired_at": "2026-07-15T06:00:00Z",
            "delivery_status": "sent",
        },
    ],
}


def _user_from_auth(authorization: str | None) -> str:
    session = require_session(authorization)
    uid = session.get("user_id")
    if not uid or uid not in DEMO_PERSONAS:
        raise HTTPException(status_code=401, detail="Unknown persona")
    return str(uid)


async def _chime_get(path: str) -> Any | None:
    """Best-effort Chime proxy. Returns None to fall back to mocks."""
    if not CHIME_API_BASE:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            login = await client.post(
                f"{CHIME_API_BASE}/api/v1/auth/demo",
                json={"telegram_id": int(CHIME_DEMO_TELEGRAM_ID)},
            )
            if login.status_code >= 400:
                return None
            cookies = login.cookies
            res = await client.get(f"{CHIME_API_BASE}{path}", cookies=cookies)
            if res.status_code >= 400:
                return None
            return res.json()
    except Exception:
        return None


@router.get("/overview")
async def market_overview(authorization: str | None = Header(default=None)):
    uid = _user_from_auth(authorization)
    watch = _MOCK_WATCH.get(uid, [])
    fires = _MOCK_FIRES.get(uid, [])
    alerts = _MOCK_ALERTS.get(uid, [])

    live = await _chime_get("/api/v1/watchlist")
    if isinstance(live, dict) and "items" in live:
        watch = live["items"]
    elif isinstance(live, list):
        watch = live

    live_fires = await _chime_get("/api/v1/alerts/history?limit=10")
    if isinstance(live_fires, dict) and "items" in live_fires:
        fires = live_fires["items"]
    elif isinstance(live_fires, list):
        fires = live_fires

    return {
        "source": "chime" if CHIME_API_BASE else "mock",
        "nfa": NFA,
        "watchlist": watch,
        "alerts": alerts,
        "fires": fires[:5],
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/watchlist")
async def market_watchlist(authorization: str | None = Header(default=None)):
    uid = _user_from_auth(authorization)
    live = await _chime_get("/api/v1/watchlist")
    if isinstance(live, dict) and "items" in live:
        items = live["items"]
        source = "chime"
    elif isinstance(live, list):
        items = live
        source = "chime"
    else:
        items = _MOCK_WATCH.get(uid, [])
        source = "mock"
    return {"source": source, "nfa": NFA, "items": items}


@router.get("/alerts")
async def market_alerts(authorization: str | None = Header(default=None)):
    uid = _user_from_auth(authorization)
    live = await _chime_get("/api/v1/alerts")
    if isinstance(live, dict) and "items" in live:
        items = live["items"]
        source = "chime"
    elif isinstance(live, list):
        items = live
        source = "chime"
    else:
        items = _MOCK_ALERTS.get(uid, [])
        source = "mock"
    return {"source": source, "nfa": NFA, "items": items}


@router.get("/fires")
async def market_fires(authorization: str | None = Header(default=None)):
    uid = _user_from_auth(authorization)
    live = await _chime_get("/api/v1/alerts/history?limit=50")
    if live is None:
        live = await _chime_get("/api/v1/alerts/fires?limit=50")
    if isinstance(live, dict) and "items" in live:
        items = live["items"]
        source = "chime"
    elif isinstance(live, list):
        items = live
        source = "chime"
    else:
        items = _MOCK_FIRES.get(uid, [])
        source = "mock"
    return {"source": source, "nfa": NFA, "items": items}


@router.get("/fires/{fire_id}")
async def market_fire_detail(
    fire_id: str,
    authorization: str | None = Header(default=None),
):
    uid = _user_from_auth(authorization)
    bundle = await market_fires(authorization=authorization)
    items = list(bundle.get("items") or [])
    hit = next((x for x in items if str(x.get("id")) == fire_id), None)
    if not hit:
        for rows in _MOCK_FIRES.values():
            hit = next((x for x in rows if x["id"] == fire_id), None)
            if hit:
                break
    if not hit:
        raise HTTPException(status_code=404, detail="Alert fire not found")
    return {
        "source": bundle["source"],
        "nfa": NFA,
        "fire": hit,
        "user_id": uid,
        "broker_cta": {
            "label": "Open my broker",
            "hint": "Ceyfi does not place CSE orders. Use your licensed stockbroker / CDS participant.",
        },
    }
