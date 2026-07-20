#!/usr/bin/env python3
"""Sum Plan A portfolio scores across enrolled factory nodes (E9-O01).

Reads ``docs/factory/PORTFOLIO_NODES.json``. For each node, loads that
repo's scoreboard and applies:

    repo_score(r) = min(proper_commits(r), clusters_closed(r))
    portfolio_score = Σ repo_score(r)

v1: only the local ``koel`` node is enrolled (same checkout). Remote
nodes can be added later; missing score files print 0 for that node.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NODES = ROOT / "docs" / "factory" / "PORTFOLIO_NODES.json"


def repo_score(scoreboard: dict) -> int:
    proper = int(scoreboard.get("lifetime_proper_commits", 0) or 0)
    clusters = int(scoreboard.get("lifetime_clusters_closed", 0) or 0)
    # Prefer explicit factory_score when present and consistent.
    explicit = scoreboard.get("lifetime_factory_score")
    if explicit is not None:
        return min(proper, clusters, int(explicit))
    return min(proper, clusters)


def load_nodes(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        raise SystemExit(f"invalid nodes list in {path}")
    return nodes


def resolve_score_file(node: dict) -> Path:
    """Koel node: score_file is relative to this repo root."""
    rel = node.get("score_file") or "docs/factory/SCOREBOARD.json"
    # Local-only stub: always resolve under the Koel checkout that owns
    # PORTFOLIO_NODES.json (multi-repo paths deferred).
    return (ROOT / rel).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--nodes",
        type=Path,
        default=DEFAULT_NODES,
        help="path to PORTFOLIO_NODES.json",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON instead of text",
    )
    args = parser.parse_args(argv)

    if not args.nodes.is_file():
        print(f"missing nodes file: {args.nodes}", file=sys.stderr)
        return 2

    nodes = load_nodes(args.nodes)
    rows: list[dict] = []
    total = 0
    for node in nodes:
        nid = str(node.get("id") or node.get("repo") or "?")
        score_path = resolve_score_file(node)
        if not score_path.is_file():
            rows.append(
                {
                    "id": nid,
                    "score_file": str(score_path),
                    "repo_score": 0,
                    "missing": True,
                }
            )
            continue
        board = json.loads(score_path.read_text(encoding="utf-8"))
        rs = repo_score(board)
        total += rs
        rows.append(
            {
                "id": nid,
                "score_file": str(score_path.relative_to(ROOT)),
                "repo_score": rs,
                "missing": False,
            }
        )

    if args.json:
        print(
            json.dumps(
                {"portfolio_score": total, "nodes": rows},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for row in rows:
            flag = " MISSING" if row["missing"] else ""
            print(f"{row['id']}\t{row['repo_score']}{flag}")
        print(f"portfolio_score\t{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
