#!/usr/bin/env python3
"""Print agentic factory loop status and next-wave hints."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCORE = ROOT / "docs" / "factory" / "SCOREBOARD.json"
BOARD_DIR = ROOT / "docs" / "factory"


def board_num(path: Path) -> int:
    m = re.search(r"EPOCH(\d+)_BOARD", path.name)
    return int(m.group(1)) if m else 10**9


def parse_board(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| E"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 3 or not parts[0].startswith("E"):
            continue
        if parts[2] not in {"OPEN", "DONE", "IN_PROGRESS", "DEFER"}:
            continue
        rows.append((parts[0], parts[1], parts[2]))
    return rows


def is_staged(text: str) -> bool:
    return "**Status:** STAGED" in text


def main() -> int:
    score = json.loads(SCORE.read_text()) if SCORE.exists() else {}
    boards = sorted(BOARD_DIR.glob("EPOCH*_BOARD.md"), key=board_num)
    chosen = None
    rows: list[tuple[str, str, str]] = []
    # Prefer lowest epoch that is not STAGED and has OPEN items (sequential drain)
    for b in boards:
        text = b.read_text()
        if is_staged(text):
            continue
        r = parse_board(text)
        if any(x[2] == "OPEN" for x in r):
            chosen = b
            rows = r
            break
    if chosen is None:
        for b in reversed(boards):
            if not is_staged(b.read_text()):
                chosen = b
                rows = parse_board(b.read_text())
                break
    if chosen is None:
        print("NO_BOARD", file=sys.stderr)
        return 1
    open_items = [r for r in rows if r[2] == "OPEN"]
    done = [r for r in rows if r[2] == "DONE"]
    prog = [r for r in rows if r[2] == "IN_PROGRESS"]
    print("=== Koel Agentic Factory Status ===")
    print(f"epoch={score.get('epoch')} branch={score.get('branch')}")
    print(f"board={chosen.relative_to(ROOT)}")
    print(f"lifetime_factory_score={score.get('lifetime_factory_score', 0)}")
    print(f"portfolio_kpi=A clean_streak={score.get('clean_streak', 0)}")
    print(f"OPEN={len(open_items)} IN_PROGRESS={len(prog)} DONE={len(done)}")
    print("--- OPEN (next wave fuel) ---")
    for i, (eid, title, _) in enumerate(open_items[:8], 1):
        print(f"  {i}. {eid}: {title[:72]}")
    if not open_items and score.get("clean_streak", 0) >= 2:
        print("GLOBAL_STOP_CANDIDATE: board empty + CLEAN×2")
    elif not open_items:
        print("BOARD_EMPTY: make factory-refill or open next epoch")
    else:
        print("CONTINUE: spawn ≤8 agents on OPEN items (disjoint OWNED_FILES)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
