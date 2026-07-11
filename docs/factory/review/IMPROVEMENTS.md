# Plan review rollup (Wave R1)

**Execution note:** “Another 100 subagents” was run as **8 concurrent adversarial reviewers** covering all 100 workstreams + process/compliance/crosscut — same concurrency constitution as planning. Simultaneous 100-way review is rejected.

**Overall verdict:** Plan is usable after rework. Do **not** start a feature flood. Freeze contracts, cut duplicates, patch farmable metrics, then Epoch 1 (≤16 WS).

## Source reviews

| Review | Verdict | Path |
|---|---|---|
| CORE | Needs rework | [R1_CORE.md](R1_CORE.md) |
| DASH | Conditional reject until contract freeze | [R1_DASH.md](R1_DASH.md) |
| OPS | Conditional pass; cut ~40% | [R1_OPS.md](R1_OPS.md) |
| QUALITY | Strong gaps; cut Hypothesis theater | [R1_QUALITY.md](R1_QUALITY.md) |
| ADVERSARIAL catalog | ~30% real probes; rest fear/dup | [R1_ADVERSARIAL.md](R1_ADVERSARIAL.md) |
| PROCESS | Farmable; patch language | [R1_PROCESS.md](R1_PROCESS.md) |
| CROSSCUT | Cycles + twins + IA drift | [R1_CROSSCUT.md](R1_CROSSCUT.md) |
| COMPLIANCE | Conditional GO | [R1_COMPLIANCE.md](R1_COMPLIANCE.md) |

## Critical improvements (must land before implementation flood)

1. **Kill obsolete WS-007** — poller already disarms after successful claim even when Telegram send fails (Stage B Pass 2). Convert to regression test only or drop.
2. **Freeze DASH contracts** — DASH_IA vs WAVE1_DASH disagree on auth, routes, cancel, health. Single ADR before any `web/` feature code.
3. **Auth is not “shared secret + client telegram_id”** — that is impersonation. Demo login must be server-side session bound to a verified id; CSRF on mutations (WS-100) gates writes.
4. **No second unbounded CSE client from the dashboard** — dash reads Postgres; bot/poller own cse.lk. Compliance NO-GO otherwise.
5. **Deduplicate CORE ↔ ADVERSARIAL twins** — ADV rows become verify-only for: 006/090, 008/089, 009/091, 012/092, 011/065/066.
6. **Patch commit farming** — convergence must stop on minors-only epochs; `factory_score = min(proper_commits, clusters_closed)`; verify SHA-bound; REFUTE ⇒ revert/fix same pass.
7. **OPS Pass 1 slim** — CI + compose Postgres + migrate + DB pytest. Defer justfile twin, day-1 Dependabot, `/metrics`, pre-commit.

## Epoch 1 board (max 16 — first implementation series)

Ordered for ≤8 concurrent agents, docs/CI/spine first:

| # | WS | Lane | Why |
|---|---|---|---|
| 1 | WS-021 | DASH | Constitution/dashboard fence consistency (docs) |
| 2 | WS-023 | DASH | Auth ADR (server session; no impersonation) |
| 3 | WS-024 | DASH | Freeze API contract vs DASH_IA |
| 4 | WS-041 | OPS | GitHub Actions ruff/mypy/pytest |
| 5 | WS-042 | OPS | docker-compose Postgres |
| 6 | WS-048 | OPS | Migrate on ephemeral DB in CI |
| 7 | WS-002 | CORE | Fail-closed disclosure if `created_at` missing |
| 8 | WS-017 | CORE | Circuit-open ≠ empty success |
| 9 | WS-001 | CORE | Parse `dateOfAnnouncement` fallback |
| 10 | WS-020 | CORE | Poll disclosures only where rules exist |
| 11 | WS-012 | CORE | `both` SIGTERM + honest `tick --force` |
| 12 | WS-009 | CORE | Concurrent `/alert` IntegrityError |
| 13 | WS-066 | QUALITY | Dual-eval / fake-lock proof (no optional DB required) |
| 14 | WS-068 | QUALITY | Bot `/cancel` + `/unwatch` handler tests |
| 15 | WS-077 | QUALITY | Health honesty regression pins |
| 16 | WS-083 | ADV | Telegram RetryAfter storm probe → fix if open |

**Explicitly deferred past Epoch 1:** bulk `approvedAnnouncement` (003/004), full `web/` CRUD UI, sparkline polish, Dependabot, Hypothesis suites, dashboard mutating APIs until auth ADR merges.

## Kill / convert list

| WS | Action |
|---|---|
| WS-007 | Drop or regression-only (already implemented) |
| WS-062–064 | Defer Hypothesis theater; keep targeted unit edges |
| WS-085, WS-100 as “build dash insecurely” | Block; auth ADR first |
| WS-089, WS-098 as new features | Stage B closed → regression only |
| WS-003 + WS-004 | Merge into one cluster when scheduled |
| justfile + Makefile day-1 | Pick one DX entrypoint (Make) |

## Go / no-go

- **GO:** Epoch 1 board above (docs + CI + CORE spine + targeted tests).  
- **NO-GO:** Shipping WS-021–040 as one dash feature flood; dash CSE polling; client-supplied identity.

## Next actions (this planning branch)

1. Apply process patches to COMMIT_FACTORY / METRICS / ORCHESTRATOR_PROMPTS.  
2. Mark INDEX.md with Epoch 1 / deferred / kill statuses.  
3. Open implementation on a new branch only after this review PR merges (or same PR if product owner prefers).
