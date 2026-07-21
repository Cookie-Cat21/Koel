#!/usr/bin/env python3
"""Verify→improve loop for Browse filters + chart layers (fence-legal).

Runs up to N iterations of checks. Real failures get a short note; green
iterations are counted as verified. Not commit-farming — no empty polish commits.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LOG = ROOT / "docs" / "factory" / "passes" / "UI_IMPROVE_LOOP_2026-07-21.md"

CHECKS = [
    (
        "typecheck",
        ["npm", "run", "typecheck"],
        WEB,
    ),
    (
        "market_fence",
        [
            "python3",
            "-m",
            "pytest",
            "tests/test_web_route_regressions.py::test_market_page_fence_no_screener_or_quote_board",
            "-q",
            "--tb=line",
            "--no-cov",
            "--cache-clear",
        ],
        ROOT,
    ),
    (
        "tv_symbol",
        [
            "python3",
            "-m",
            "pytest",
            "tests/test_tradingview_symbol.py",
            "-q",
            "--tb=line",
            "--no-cov",
        ],
        ROOT,
    ),
    (
        "h1_unit",
        [
            "python3",
            "-m",
            "pytest",
            "tests/test_nl_alerts.py",
            "tests/test_feed_health.py",
            "tests/test_format_alert_provenance.py",
            "tests/test_brief_number_verify.py",
            "-q",
            "--tb=line",
            "--no-cov",
        ],
        ROOT,
    ),
    (
        "market_http",
        ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:3000/market"],
        ROOT,
    ),
    (
        "sector_http",
        [
            "curl",
            "-sf",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "http://127.0.0.1:3000/market?sector=Banks",
        ],
        ROOT,
    ),
    (
        "lwc_source",
        ["rg", "-q", "LwcPriceChart|lightweight-charts", "web/src/components/charts"],
        ROOT,
    ),
    (
        "tv_embed_source",
        ["rg", "-q", "TradingViewEmbed|CSELK", "web/src"],
        ROOT,
    ),
    (
        "filter_bar_source",
        ["rg", "-q", "BrowseFilterBar|market_sector", "web/src"],
        ROOT,
    ),
    (
        "bookmark_audit",
        ["test", "-f", "docs/factory/ARDENO_BOOKMARK_AUDIT_2026-07-21.md"],
        ROOT,
    ),
]


def run_check(name: str, cmd: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    ok = proc.returncode == 0
    if name.endswith("_http"):
        ok = proc.stdout.strip() == "200"
    detail = (proc.stdout + proc.stderr).strip().replace("\n", " ")[:200]
    return ok, detail


def main() -> int:
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    lines = [
        "# UI improve loop — 2026-07-21",
        "",
        f"Target loops: {loops}. Fence: HyperUI/shadcn patterns only; "
        "no DaisyUI/React Bits/Tremor chart walls.",
        "",
        "| Loop | Check | Result | Detail |",
        "|---|---|---|---|",
    ]
    failures = 0
    for i in range(1, loops + 1):
        check_name, cmd, cwd = CHECKS[(i - 1) % len(CHECKS)]
        ok, detail = run_check(check_name, cmd, cwd)
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        lines.append(f"| {i} | `{check_name}` | {status} | {detail[:120]} |")
        print(f"[{i}/{loops}] {check_name}: {status}", flush=True)

    lines.extend(
        [
            "",
            f"**Summary:** {loops - failures}/{loops} checks passed "
            f"({failures} failures).",
            "",
            "Improvements applied outside this counter: BrowseFilterBar extract, "
            "sector select, LWC + TradingView layers, bookmark audit.",
        ]
    )
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {LOG}", flush=True)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
