#!/usr/bin/env python3
"""Fetch a single-symbol quote from cse.lk (unofficial)."""

from __future__ import annotations

import json
import sys

import httpx

BASE = "https://www.cse.lk/api"
HEADERS = {
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/",
    "User-Agent": "CSE-API-Docs-Example/1.0",
}


def main(symbol: str = "JKH.N0000") -> None:
    r = httpx.post(
        f"{BASE}/companyInfoSummery",
        data={"symbol": symbol},
        headers=HEADERS,
        timeout=30.0,
    )
    r.raise_for_status()
    info = r.json()["reqSymbolInfo"]
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "JKH.N0000")
