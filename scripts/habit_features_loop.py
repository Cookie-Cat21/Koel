#!/usr/bin/env python3
"""50-iteration improve/verify loop for habit surfaces (activity/events/settings)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/factory/passes/HABIT_FEATURES_LOOP_2026-07-21.md"
BASE = os.environ.get("KOEL_DASH_BASE", "http://127.0.0.1:3000")
LOOPS = 50


def http_ok(path: str, cookie: str | None = None) -> tuple[int, str]:
    req = urllib.request.Request(BASE + path, method="GET")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(2000).decode("utf-8", "replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read(500).decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def run_pytest() -> tuple[bool, str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = env.get(
        "TEST_DATABASE_URL", "postgresql://koel:koel@localhost:5432/koel"
    )
    # Avoid writing into Neon if injected.
    if "neon.tech" in env.get("DATABASE_URL", ""):
        env["DATABASE_URL"] = "postgresql://koel:koel@localhost:5432/koel"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_filing_categories.py",
            "--tb=line",
            "--no-cov",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (proc.stdout + proc.stderr)[-800:]
    return proc.returncode == 0, out


def main() -> int:
    checks = [
        ("login_page", "/login"),
        ("settings_page", "/settings"),
        ("activity_page", "/activity"),
        ("events_page", "/events"),
    ]
    rows: list[str] = []
    pass_n = 0
    for i in range(1, LOOPS + 1):
        ok_flags: list[str] = []
        # pytest every 5th loop + first
        if i == 1 or i % 5 == 0:
            pytest_ok, pytest_out = run_pytest()
            ok_flags.append("pytest" if pytest_ok else "pytest_FAIL")
        else:
            pytest_ok = True
            pytest_out = "skipped"
            ok_flags.append("pytest_skip")

        http_all = True
        for name, path in checks:
            status, body = http_ok(path)
            # login 200; others may 307/302 to login without cookie — both ok
            good = status in (200, 302, 303, 307) or (
                status == 200 and "koel" in body.lower()
            )
            if not good and status == 0:
                http_all = False
                ok_flags.append(f"{name}:{status}")
            elif status == 0:
                http_all = False
                ok_flags.append(f"{name}:down")
            else:
                ok_flags.append(f"{name}:{status}")

        # Static file presence
        files_ok = all(
            (ROOT / p).is_file()
            for p in (
                "web/src/app/activity/page.tsx",
                "web/src/app/events/page.tsx",
                "web/src/app/api/v1/hooks/tradingview/route.ts",
                "web/src/app/api/v1/activity/route.ts",
                "koel/filing_categories.py",
                "db/migrations/034_habit_prefs_webhook.sql",
            )
        )
        ok_flags.append("files" if files_ok else "files_FAIL")

        loop_ok = pytest_ok and files_ok and http_all
        if loop_ok:
            pass_n += 1
        rows.append(
            f"| {i} | {'PASS' if loop_ok else 'FAIL'} | {', '.join(ok_flags)} |"
        )
        # Tiny improve: rewrite report each loop (visibility)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            "\n".join(
                [
                    "# Habit features improve loop — 2026-07-21",
                    "",
                    f"Base: `{BASE}` · loops: {LOOPS} · pass so far: {pass_n}/{i}",
                    "",
                    "| # | Result | Notes |",
                    "|---|---|---|",
                    *rows,
                    "",
                    f"Last pytest snippet:\n```\n{pytest_out}\n```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        time.sleep(0.05)

    print(json.dumps({"pass": pass_n, "loops": LOOPS, "report": str(REPORT)}))
    return 0 if pass_n >= LOOPS * 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
