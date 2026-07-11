#!/usr/bin/env python3
"""Update docs/factory/SCOREBOARD.json from EPOCH*_BOARD.md DONE counts (E4-O02)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCORE = ROOT / "docs" / "factory" / "SCOREBOARD.json"
BOARD_DIR = ROOT / "docs" / "factory"

_EPOCH_RE = re.compile(r"EPOCH(\d+)_BOARD\.md$", re.IGNORECASE)


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


def board_epoch_num(path: Path) -> int | None:
    m = _EPOCH_RE.search(path.name)
    return int(m.group(1)) if m else None


def count_status(rows: list[tuple[str, str, str]]) -> dict[str, int]:
    out = {"OPEN": 0, "DONE": 0, "IN_PROGRESS": 0, "DEFER": 0}
    for _, _, status in rows:
        out[status] = out.get(status, 0) + 1
    return out


def load_boards() -> list[tuple[Path, int, list[tuple[str, str, str]]]]:
    boards: list[tuple[Path, int, list[tuple[str, str, str]]]] = []
    for path in sorted(BOARD_DIR.glob("EPOCH*_BOARD.md")):
        num = board_epoch_num(path)
        if num is None:
            continue
        boards.append((path, num, parse_board(path.read_text())))
    return boards


def choose_open_board(
    boards: list[tuple[Path, int, list[tuple[str, str, str]]]],
) -> Path | None:
    # Newest epoch with any OPEN item; else newest board file.
    for path, _, rows in sorted(boards, key=lambda t: t[1], reverse=True):
        if any(r[2] == "OPEN" for r in rows):
            return path
    if not boards:
        return None
    return max(boards, key=lambda t: t[1])[0]


def build_scoreboard(existing: dict) -> dict:
    boards = load_boards()
    done_by_epoch: dict[int, int] = {}
    for _, num, rows in boards:
        done_by_epoch[num] = count_status(rows)["DONE"]

    open_board = choose_open_board(boards)
    open_epoch = board_epoch_num(open_board) if open_board else None

    # Lifetime clusters = sum of DONE across epoch boards (factory_score units).
    lifetime = sum(done_by_epoch.values())

    out = dict(existing)
    out.setdefault("aspiration", "maximize_lifetime_factory_score")
    out.setdefault("literal_trillion_commits", False)
    out.setdefault("farming_banned", True)
    out.setdefault("concurrency_preferred", 8)
    out.setdefault("concurrency_hard_max", 16)
    out.setdefault("branch", "cursor/epoch2-agentic-loop-cb19")
    out.setdefault("loop_spec", "docs/factory/AGENTIC_LOOP.md")
    out.setdefault("clean_streak", 0)

    if open_epoch is not None:
        out["epoch"] = open_epoch
    if open_board is not None:
        out["open_board"] = str(open_board.relative_to(ROOT))

    out["lifetime_factory_score"] = lifetime
    out["lifetime_proper_commits"] = lifetime
    out["lifetime_clusters_closed"] = lifetime

    for num, done in sorted(done_by_epoch.items()):
        if num >= 2:
            out[f"epoch{num}_done"] = done

    out["note"] = (
        "Literal 5T git commits rejected; portfolio_score == chime node while "
        "Chime is the only enrolled factory"
    )
    # Drop stale session notes if present — machine counts are source of truth.
    out.pop("sessions", None)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if SCOREBOARD.json would change (CI drift guard)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write updated SCOREBOARD.json (default when neither flag set)",
    )
    args = parser.parse_args(argv)

    existing: dict = {}
    if SCORE.exists():
        existing = json.loads(SCORE.read_text())
    updated = build_scoreboard(existing)
    text = json.dumps(updated, indent=2) + "\n"

    if args.check:
        current = SCORE.read_text() if SCORE.exists() else ""
        if current != text:
            print(
                "SCOREBOARD.json out of date; run scripts/factory/update_scoreboard.py",
                file=sys.stderr,
            )
            return 1
        print("SCOREBOARD.json ok")
        return 0

    # Default: write
    SCORE.write_text(text)
    print(
        f"wrote {SCORE.relative_to(ROOT)} "
        f"epoch={updated.get('epoch')} "
        f"lifetime={updated.get('lifetime_factory_score')} "
        f"board={updated.get('open_board')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
