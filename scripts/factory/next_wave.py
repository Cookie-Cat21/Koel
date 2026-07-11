#!/usr/bin/env python3
"""Print up to 8 OPEN item ids for the active board (wave packing aid)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACTORY = ROOT / "docs" / "factory"


def main() -> int:
    boards = sorted(FACTORY.glob("EPOCH*_BOARD.md"), reverse=True)
    for b in boards:
        open_ids: list[str] = []
        for line in b.read_text().splitlines():
            if not line.startswith("| E"):
                continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3 and parts[2] == "OPEN":
                open_ids.append(parts[0])
        if open_ids:
            print(b.name)
            for i, oid in enumerate(open_ids[:8], 1):
                print(f"{i} {oid}")
            return 0
    print("NO_OPEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
