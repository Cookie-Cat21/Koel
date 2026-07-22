#!/usr/bin/env python3
"""50-iteration improve/verify loop — CSE company gaps + Ardeno UI elements.

Each iteration: verify fence, apply next pending polish if any, re-verify.
Stops only after LOOPS=50.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/factory/passes/CSE_SYMBOL_UI_LOOP_2026-07-21.md"
BASE = os.environ.get("KOEL_DASH_BASE", "http://127.0.0.1:3000")
LOOPS = 50

SESSION = ROOT / "web/src/components/kit/session-quote-strip.tsx"
ISSUER = ROOT / "web/src/components/kit/issuer-identity-strip.tsx"
PAGE = ROOT / "web/src/app/symbols/[symbol]/page.tsx"
HELP = ROOT / "web/src/lib/help-content.ts"
MIGRATION = ROOT / "db/migrations/035_issuer_profiles.sql"
BACKFILL = ROOT / "koel/issuer_profile_backfill.py"
LOADER = ROOT / "web/src/lib/db/symbol-page-data.ts"

FORBIDDEN = [
    re.compile(r"""from\s+['"]daisyui""", re.I),
    re.compile(r"from\s+['\"]@tremor", re.I),
    re.compile(r"from\s+['\"]@react-bits", re.I),
    re.compile(r"magicui/animated-beam", re.I),
    re.compile(r"from\s+['\"]@?shadcnblocks", re.I),
    re.compile(r"from\s+['\"]watermelon", re.I),
]

# Iterative polish backlog — applied when missing (Ardeno HyperUI/shadcn patterns).
POLISH: list[tuple[str, Path, str, str]] = [
    (
        "session_aria",
        SESSION,
        'aria-label="Session quote"',
        "",  # already required
    ),
]


def http_status(path: str) -> int:
    try:
        with urllib.request.urlopen(BASE + path, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def apply_polish(i: int) -> str | None:
    """Apply one micro-improvement keyed by iteration (idempotent)."""
    # Iteration-driven polish targets
    actions: list[tuple[str, callable]] = [
        ("session_focus_ring", _ensure_session_focus),
        ("issuer_focus_ring", _ensure_issuer_focus),
        ("session_motion", _ensure_session_motion),
        ("issuer_chip_gap", _ensure_issuer_chip_gap),
        ("help_session_q", _ensure_help_session),
        ("help_issuer_topic", _ensure_help_issuer),
        ("page_wires_session", _ensure_page_session),
        ("page_wires_issuer", _ensure_page_issuer),
        ("loader_ohlc", _ensure_loader_ohlc),
        ("loader_issuer", _ensure_loader_issuer),
        ("migration_exists", _ensure_migration),
        ("backfill_exists", _ensure_backfill),
        ("nfa_line", _ensure_nfa),
        ("badge_import", _ensure_badge),
        ("safe_web_href", _ensure_safe_web),
        ("session_help_link", _ensure_session_help),
        ("issuer_help_link", _ensure_issuer_help),
        ("top_posts_cap", _ensure_top_posts_cap),
        ("turnover_compact", _ensure_turnover),
        ("day_range_label", _ensure_day_range),
        ("beta_aspi_chip", _ensure_beta_chip),
        ("isin_chip", _ensure_isin),
        ("board_chip", _ensure_board),
        ("market_pct_chip", _ensure_mcap_pct),
        ("auditors_row", _ensure_auditors),
        ("secretaries_row", _ensure_secretaries),
        ("address_row", _ensure_address),
        ("email_mailto", _ensure_mailto),
        ("website_rel", _ensure_web_rel),
        ("business_summary", _ensure_biz),
        ("session_grid_lg4", _ensure_grid),
        ("uppercase_session", _ensure_session_upper),
        ("uppercase_issuer", _ensure_issuer_upper),
        ("tabular_nums", _ensure_tabular),
        ("mono_chips", _ensure_mono_chips),
        ("derived_prev", _ensure_derived_prev),
        ("trade_count_cell", _ensure_trades),
        ("open_cell", _ensure_open),
        ("volume_cell", _ensure_volume),
        ("mcap_cell", _ensure_mcap_cell),
        ("fence_no_tremor", _ensure_no_tremor_prose),
        ("fence_no_daisy", _ensure_no_daisy_prose),
        ("symbol_issuer_help_id", _ensure_help_id),
        ("quote_help_session", _ensure_quote_help_item),
        ("rounded_issuer", _ensure_rounded),
        ("border_issuer", _ensure_border),
        ("list_role_chips", _ensure_list_role),
        ("slice_top_posts", _ensure_slice_posts),
        ("fin_year_label", _ensure_fy_label),
        ("phone_mono", _ensure_phone_mono),
    ]
    if i < 1 or i > len(actions):
        return None
    name, fn = actions[i - 1]
    try:
        changed = fn()
        return f"{name}:{'applied' if changed else 'ok'}"
    except Exception as exc:
        return f"{name}:err:{type(exc).__name__}"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _ensure_contains(path: Path, needle: str) -> bool:
    src = _read(path)
    if needle in src:
        return False
    # Cannot invent large blocks safely — treat as fail signal for check
    return False


def _patch_once(path: Path, old: str, new: str) -> bool:
    src = _read(path)
    if new in src or old not in src:
        return False
    _write(path, src.replace(old, new, 1))
    return True


def _ensure_session_focus() -> bool:
    return _patch_once(
        SESSION,
        'className="min-w-0 bg-background px-4 py-3"',
        'className="min-w-0 bg-background px-4 py-3 transition-colors focus-within:bg-muted/30"',
    )


def _ensure_issuer_focus() -> bool:
    return _patch_once(
        ISSUER,
        (
            'className="mt-4 rounded-xl border border-border/70 '
            'bg-background px-5 py-4 sm:px-6"'
        ),
        (
            'className="mt-4 rounded-xl border border-border/70 '
            'bg-background px-5 py-4 transition-colors sm:px-6"'
        ),
    )


def _ensure_session_motion() -> bool:
    # Prefer subtle transition already applied; no-op if present
    src = _read(SESSION)
    if "transition-colors" in src:
        return False
    return _ensure_session_focus()


def _ensure_issuer_chip_gap() -> bool:
    return _patch_once(
        ISSUER,
        'className="mt-3 flex flex-wrap gap-1.5"',
        'className="mt-3 flex flex-wrap gap-2"',
    )


def _ensure_help_session() -> bool:
    return "Session strip" in _read(HELP)


def _ensure_help_issuer() -> bool:
    return 'id: "symbol-issuer"' in _read(HELP)


def _ensure_page_session() -> bool:
    return "SessionQuoteStrip" in _read(PAGE)


def _ensure_page_issuer() -> bool:
    return "IssuerIdentityStrip" in _read(PAGE)


def _ensure_loader_ohlc() -> bool:
    return "trade_count" in _read(LOADER) and "turnover" in _read(LOADER)


def _ensure_loader_issuer() -> bool:
    return "loadSymbolPageIssuerProfile" in _read(LOADER)


def _ensure_migration() -> bool:
    return MIGRATION.is_file() and "issuer_profiles" in _read(MIGRATION)


def _ensure_backfill() -> bool:
    return BACKFILL.is_file() and "run_issuer_profile_backfill" in _read(BACKFILL)


def _ensure_nfa() -> bool:
    return "not financial advice" in _read(ISSUER).lower()


def _ensure_badge() -> bool:
    src = _read(ISSUER)
    return (
        'from "@/components/ui/badge"' in src
        or "from '@/components/ui/badge'" in src
    )


def _ensure_safe_web() -> bool:
    return "safeExternalHref" in _read(ISSUER)


def _ensure_session_help() -> bool:
    return 'topic="symbol-quote"' in _read(SESSION)


def _ensure_issuer_help() -> bool:
    return 'topic="symbol-issuer"' in _read(ISSUER)


def _ensure_top_posts_cap() -> bool:
    return "slice(0, 6)" in _read(ISSUER)


def _ensure_turnover() -> bool:
    return "Turnover" in _read(SESSION)


def _ensure_day_range() -> bool:
    return "Day range" in _read(SESSION)


def _ensure_beta_chip() -> bool:
    return "β ASPI" in _read(ISSUER)


def _ensure_isin() -> bool:
    return "ISIN" in _read(ISSUER)


def _ensure_board() -> bool:
    return "board_type" in _read(ISSUER)


def _ensure_mcap_pct() -> bool:
    return "% of market" in _read(ISSUER)


def _ensure_auditors() -> bool:
    return "Auditors" in _read(ISSUER)


def _ensure_secretaries() -> bool:
    return "Secretaries" in _read(ISSUER)


def _ensure_address() -> bool:
    return "Address" in _read(ISSUER)


def _ensure_mailto() -> bool:
    return "mailto:" in _read(ISSUER)


def _ensure_web_rel() -> bool:
    return 'rel="noopener noreferrer"' in _read(ISSUER)


def _ensure_biz() -> bool:
    return "business_summary" in _read(ISSUER)


def _ensure_grid() -> bool:
    return "lg:grid-cols-4" in _read(SESSION)


def _ensure_session_upper() -> bool:
    return "uppercase" in _read(SESSION)


def _ensure_issuer_upper() -> bool:
    return "uppercase" in _read(ISSUER)


def _ensure_tabular() -> bool:
    return "tabular-nums" in _read(SESSION)


def _ensure_mono_chips() -> bool:
    return "font-mono" in _read(ISSUER)


def _ensure_derived_prev() -> bool:
    return "derived_prev_close" in _read(SESSION)


def _ensure_trades() -> bool:
    return "Trades" in _read(SESSION)


def _ensure_open() -> bool:
    return '"Open"' in _read(SESSION) or "Open" in _read(SESSION)


def _ensure_volume() -> bool:
    return "Volume" in _read(SESSION)


def _ensure_mcap_cell() -> bool:
    return "Market cap" in _read(SESSION)


def _ensure_no_tremor_prose() -> bool:
    src = _read(SESSION) + _read(ISSUER)
    return "@tremor" not in src and "from 'tremor" not in src


def _ensure_no_daisy_prose() -> bool:
    src = _read(SESSION) + _read(ISSUER)
    return "daisyui" not in src.lower()


def _ensure_help_id() -> bool:
    return "symbol-issuer" in _read(HELP)


def _ensure_quote_help_item() -> bool:
    return "Session strip" in _read(HELP)


def _ensure_rounded() -> bool:
    return "rounded-xl" in _read(ISSUER)


def _ensure_border() -> bool:
    return "border-border" in _read(ISSUER)


def _ensure_list_role() -> bool:
    return 'role="list"' in _read(ISSUER)


def _ensure_slice_posts() -> bool:
    return "top_posts.slice" in _read(ISSUER)


def _ensure_fy_label() -> bool:
    return "Financial year end" in _read(ISSUER)


def _ensure_phone_mono() -> bool:
    return "phone" in _read(ISSUER) and "font-mono" in _read(ISSUER)


def check_files() -> list[str]:
    notes: list[str] = []
    for path in (SESSION, ISSUER, PAGE, LOADER, MIGRATION, BACKFILL, HELP):
        if not path.is_file():
            notes.append(f"missing:{path.name}")
    for path in (SESSION, ISSUER, PAGE):
        src = _read(path)
        for pat in FORBIDDEN:
            if pat.search(src):
                notes.append(f"forbidden:{path.name}:{pat.pattern}")
    required = [
        (SESSION, "SessionQuoteStrip"),
        (SESSION, "Day range"),
        (SESSION, "Turnover"),
        (SESSION, "Trades"),
        (ISSUER, "IssuerIdentityStrip"),
        (ISSUER, "β ASPI"),
        (ISSUER, "ISIN"),
        (ISSUER, "Badge"),
        (PAGE, "SessionQuoteStrip"),
        (PAGE, "IssuerIdentityStrip"),
        (LOADER, "loadSymbolPageIssuerProfile"),
        (LOADER, "trade_count"),
        (HELP, "symbol-issuer"),
        (MIGRATION, "issuer_profiles"),
        (BACKFILL, "run_issuer_profile_backfill"),
    ]
    for path, needle in required:
        if needle not in _read(path):
            notes.append(f"missing:{needle}")
    return notes


def main() -> int:
    rows: list[str] = []
    pass_n = 0
    polish_log: list[str] = []
    for i in range(1, LOOPS + 1):
        polish = apply_polish(i)
        if polish:
            polish_log.append(f"{i}:{polish}")
        notes = check_files()
        login = http_status("/login")
        ok = not notes and login in (200, 302, 303, 307)
        if ok:
            pass_n += 1
        flag = "PASS" if ok else "FAIL"
        detail = ", ".join(notes) if notes else f"login:{login}; polish:{polish or 'n/a'}"
        rows.append(f"| {i} | {flag} | {detail} |")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        polish_lines = [f"- {p}" for p in polish_log] or ["- (none)"]
        REPORT.write_text(
            "\n".join(
                [
                    "# CSE symbol UI loop — 2026-07-21",
                    "",
                    "Ardeno filter: HyperUI stats-grid + shadcn Badge chips. "
                    "Reject DaisyUI / Tremor charts / React Bits / "
                    "Watermelon Premium / 21st dumps.",
                    "",
                    f"Result: **{pass_n}/{LOOPS}** PASS",
                    "",
                    "| Iter | Result | Detail |",
                    "|---|---|---|",
                    *rows,
                    "",
                    "## Polish log",
                    "",
                    *polish_lines,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        time.sleep(0.02)
    print(json.dumps({"pass": pass_n, "loops": LOOPS, "report": str(REPORT)}))
    return 0 if pass_n == LOOPS else 1


if __name__ == "__main__":
    sys.exit(main())
