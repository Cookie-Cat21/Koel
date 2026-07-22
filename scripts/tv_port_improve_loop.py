#!/usr/bin/env python3
"""50-iteration verify loop for TradingView → koel workbench port."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LOG = ROOT / "docs" / "factory" / "passes" / "TV_PORT_LOOP_2026-07-21.md"

CHECKS = [
    ("typecheck", ["npm", "run", "typecheck"], WEB),
    (
        "indicators_src",
        [
            "rg",
            "-q",
            "computeSma|computeRsi|computeBollinger",
            "web/src/lib/charts/koel-indicators.ts",
        ],
        ROOT,
    ),
    (
        "workbench_src",
        ["rg", "-q", "seriesStyle|drawMode|SMA 20|H-line", "web/src/components/charts"],
        ROOT,
    ),
    (
        "audit_doc",
        ["test", "-f", "docs/factory/TRADINGVIEW_AUDIT_AND_KOEL_PORT.md"],
        ROOT,
    ),
    (
        "unit_events",
        [
            "python3",
            "-m",
            "pytest",
            "tests/test_koel_chart_events.py",
            "tests/test_koel_indicators.py",
            "-q",
            "--tb=line",
            "--no-cov",
        ],
        ROOT,
    ),
    (
        "lwc_styles",
        [
            "rg",
            "-q",
            "AreaSeries|CandlestickSeries|LineSeries",
            "web/src/components/charts/lwc-price-chart.tsx",
        ],
        ROOT,
    ),
    (
        "market_http",
        ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:3000/market"],
        ROOT,
    ),
    (
        "no_tv_spine",
        [
            "rg",
            "-q",
            "TV is \\*\\*never\\*\\*|never.*alert.*spine|koel alerts still use",
            "docs/factory",
        ],
        ROOT,
    ),
    (
        "expand_overlays",
        ["rg", "-q", "initialDisclosures|buildFireMarkers", "web/src"],
        ROOT,
    ),
    (
        "chart_layers",
        [
            "rg",
            "-q",
            "TV-inspired koel workbench|TRADINGVIEW_AUDIT",
            "docs/factory/CHART_LAYERS.md",
        ],
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
        "# TradingView → koel port improve loop — 2026-07-21",
        "",
        f"Target loops: {loops}. Port: styles / MAs / BB / RSI / drawings on Postgres LWC.",
        "",
        "| Loop | Check | Result | Detail |",
        "|---|---|---|---|",
    ]
    failures = 0
    for i in range(1, loops + 1):
        name, cmd, cwd = CHECKS[(i - 1) % len(CHECKS)]
        ok, detail = run_check(name, cmd, cwd)
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        lines.append(f"| {i} | `{name}` | {status} | {detail[:120]} |")
        print(f"[{i}/{loops}] {name}: {status}", flush=True)

    lines.extend(
        [
            "",
            f"**Summary:** {loops - failures}/{loops} checks passed ({failures} failures).",
            "",
            "See `docs/factory/TRADINGVIEW_AUDIT_AND_KOEL_PORT.md`.",
        ]
    )
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {LOG}", flush=True)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
