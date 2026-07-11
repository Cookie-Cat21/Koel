#!/usr/bin/env python3
"""Activate the next staged epoch board when current has no OPEN items."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACTORY = ROOT / "docs" / "factory"


def board_num(path: Path) -> int:
    m = re.search(r"EPOCH(\d+)_BOARD", path.name)
    return int(m.group(1)) if m else -1


def parse_item_statuses(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        if not line.startswith("| E"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 3 and parts[2] in {"OPEN", "DONE", "IN_PROGRESS", "DEFER"}:
            out.append(parts[2])
    return out


def is_staged(text: str) -> bool:
    return "**Status:** STAGED" in text


def main() -> int:
    boards = sorted(FACTORY.glob("EPOCH*_BOARD.md"), key=board_num)
    if not boards:
        print("NO_FUEL: no epoch boards")
        return 1

    # Already have an active (non-staged) board with OPEN items?
    for b in boards:
        text = b.read_text()
        if is_staged(text):
            continue
        statuses = parse_item_statuses(text)
        open_n = sum(1 for s in statuses if s == "OPEN")
        if open_n:
            print(f"ACTIVE_OPEN board={b.name} open={open_n}")
            return 0

    # Activate lowest STAGED board
    for b in boards:
        text = b.read_text()
        if not is_staged(text):
            continue
        new = text
        new = re.sub(
            r"\*\*Status:\*\* STAGED[^\n]*",
            "**Status:** OPEN",
            new,
            count=1,
        )
        if new == text:
            continue
        b.write_text(new)
        print(f"REFILLED activated={b.name}")
        return 0

    print("NO_FUEL: no staged boards left — add next EPOCHN_BOARD.md")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
