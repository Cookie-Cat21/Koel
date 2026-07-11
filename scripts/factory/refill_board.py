#!/usr/bin/env python3
"""Open the next staged epoch board when current has no OPEN items."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACTORY = ROOT / "docs" / "factory"


def parse_status_rows(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| E"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 3:
            continue
        if parts[2] not in {"OPEN", "DONE", "IN_PROGRESS", "DEFER", "STAGED"}:
            continue
        rows.append((parts[0], parts[2]))
    return rows


def board_num(path: Path) -> int:
    m = re.search(r"EPOCH(\d+)_BOARD", path.name)
    return int(m.group(1)) if m else -1


def main() -> int:
    boards = sorted(FACTORY.glob("EPOCH*_BOARD.md"), key=board_num)
    if not boards:
        print("NO_FUEL: no epoch boards")
        return 1

    # Find highest board that still has OPEN
    for b in reversed(boards):
        rows = parse_status_rows(b.read_text())
        if any(s == "OPEN" for _, s in rows):
            print(f"ACTIVE_OPEN board={b.name} open={sum(1 for _, s in rows if s == 'OPEN')}")
            return 0

    # Activate next STAGED board (flip Status header + STAGED rows → OPEN)
    for b in boards:
        text = b.read_text()
        rows = parse_status_rows(text)
        if not rows:
            continue
        if any(s == "STAGED" for _, s in rows) or "**Status:** STAGED" in text:
            new = text.replace("**Status:** STAGED (open after Epoch 6)", "**Status:** OPEN")
            new = new.replace("**Status:** STAGED (open after Epoch 7)", "**Status:** OPEN")
            new = new.replace("**Status:** STAGED", "**Status:** OPEN")
            # Don't auto-flip item STAGED cells — items use OPEN already in our boards
            b.write_text(new)
            print(f"REFILLED activated={b.name}")
            return 0

    # If latest is all DONE, print NO_FUEL (human must add Epoch N+1)
    latest = boards[-1]
    rows = parse_status_rows(latest.read_text())
    if rows and all(s == "DONE" for _, s in rows):
        print(f"NO_FUEL: {latest.name} complete — add EPOCH{board_num(latest)+1}_BOARD.md")
        return 2

    print(f"ACTIVE board={latest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
