#!/usr/bin/env python3
"""Bulk trade summary — prefer this for polling many symbols."""

from __future__ import annotations

import httpx

BASE = "https://www.cse.lk/api"
HEADERS = {
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/",
    "User-Agent": "CSE-API-Docs-Example/1.0",
    "Content-Type": "application/json",
}


def main() -> None:
    r = httpx.post(f"{BASE}/tradeSummary", json={}, headers=HEADERS, timeout=45.0)
    r.raise_for_status()
    rows = r.json().get("reqTradeSummery") or []
    print(f"symbols: {len(rows)}")
    for row in rows[:5]:
        print(f"{row.get('symbol')}\t{row.get('price')}\t{row.get('percentageChange')}")


if __name__ == "__main__":
    main()
