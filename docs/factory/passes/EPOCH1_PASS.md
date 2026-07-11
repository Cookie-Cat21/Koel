# Epoch 1 — progress report (stub)

**Status:** in progress  
**Branch:** `cursor/epoch1-execute-cb19`  
**Board source:** [review/IMPROVEMENTS.md](../review/IMPROVEMENTS.md) (fixed 16 WS)  
**Date started (UTC):** 2026-07-11

Telegram remains primary. Thin dash is greenlit (secondary); no portfolio /
screener / TA. Docs/CI/spine first — no feature flood.

## Board

| # | WS | Lane | Title | Status |
|---|---|---|---|---|
| 1 | WS-021 | DASH | Constitution / dashboard fence consistency (docs) | in-progress |
| 2 | WS-023 | DASH | Auth ADR (server session; no impersonation) | pending |
| 3 | WS-024 | DASH | Freeze API contract vs DASH_IA | pending |
| 4 | WS-041 | OPS | GitHub Actions ruff/mypy/pytest | pending |
| 5 | WS-042 | OPS | docker-compose Postgres | pending |
| 6 | WS-048 | OPS | Migrate on ephemeral DB in CI | pending |
| 7 | WS-002 | CORE | Fail-closed disclosure if `created_at` missing | pending |
| 8 | WS-017 | CORE | Circuit-open ≠ empty success | pending |
| 9 | WS-001 | CORE | Parse `dateOfAnnouncement` fallback | pending |
| 10 | WS-020 | CORE | Poll disclosures only where rules exist | pending |
| 11 | WS-012 | CORE | `both` SIGTERM + honest `tick --force` | pending |
| 12 | WS-009 | CORE | Concurrent `/alert` IntegrityError | pending |
| 13 | WS-066 | QUALITY | Dual-eval / fake-lock proof (no optional DB) | pending |
| 14 | WS-068 | QUALITY | Bot `/cancel` + `/unwatch` handler tests | pending |
| 15 | WS-077 | QUALITY | Health honesty regression pins | pending |
| 16 | WS-083 | ADV | Telegram RetryAfter storm probe → fix if open | pending |

## Scorecard (fill when pass closes)

| Field | Value |
|---|---|
| Pass ID | `EPOCH1` (multi-lane) |
| Date (UTC) | |
| Agents used | |
| Findings opened | |
| Findings closed | |
| Proper commits accepted | |
| Proper commits rejected / excluded | |
| Quality bars touched | |
| Verify | `ruff` ☐ `mypy` ☐ `pytest` ☐ dash smoke ☐ N/A ☐ |
| Adversarial review | pass ☐ / refute→fixed ☐ / refute→open ☐ |
| Fence violations | none ☐ / list |
| Stop signal? | |

## Notes

- WS-021 closes when RESOURCES/README/CLAUDE fence text agree on thin dash.
- Defer past Epoch 1: bulk announcements (003/004), full `web/` CRUD UI,
  sparkline polish, Dependabot, Hypothesis suites, mutating dash APIs until
  auth ADR merges.
