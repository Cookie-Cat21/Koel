# Epoch 1 — CR_SCORECARD

**Reviewer:** factory quality-bar CR (honest)  
**Date (UTC):** 2026-07-11  
**Branch:** `cursor/epoch1-execute-cb19`  
**Reviewed HEAD:** `2751414` (adversarial fixup) + tip at review time  
**Inputs:** [COMMIT_FACTORY.md](../../COMMIT_FACTORY.md) §2, [EPOCH1_PASS.md](../../passes/EPOCH1_PASS.md), [EPOCH1_ADVERSARIAL.md](../../passes/EPOCH1_ADVERSARIAL.md), implementation skim + verify re-run  

---

## Verdict

**NEEDS_FIXES**

Do **not** CONVERGE_EPOCH1. Same-pass fixup closed WS-009 and WS-068 for real; WS-083 remains a **false close** (30s sleep cap ≠ WAVE1 global backoff / bounded unsent). Pass report’s `clusters_closed: 16/16` overclaims. Fences held (no `web/` flood, no dash CSE client, no impersonation auth). Useful spine/CI work stands — reopen the storm cluster before scoring Epoch 1 Done.

---

## Quality bars (1–8)

| # | Bar | Score | One-line evidence |
|---|---|---|---|
| 1 | Alert correctness | **partial** | Price crossing/gap/re-arm/missing-prev covered (`tests/test_crossing.py`, `chime.rules` 100%); disclosure `dateOfAnnouncement` → UTC midnight skew still false+/false− vs rule `created_at` (ADV MEDIUM WS-001). |
| 2 | Zero dup / zero loss | **partial** | Claim-before-disarm + session advisory lock + `event_key` uniqueness stand; RetryAfter still sleeps **per message** (cap 30s) under held lock; `_retry_unsent` unbounded (WS-006/090 open). |
| 3 | Latency | **partial** | `alert_latency_ms` logs claim→send (`chime/poller.py`); CSE→TG honestly poll-interval-bounded; no dash TTFB (N/A until `web/`). |
| 4 | Resilience | **pass** | Price circuit-open / disclosure per-symbol `continue` never kill `run_once`; WS-017 re-raise proven; `tests/test_poller_resilience.py` + circuit tests. |
| 5 | Ops | **pass** | structlog, `/health` 200/503, env secrets, Makefile + compose Postgres + CI migrate/pytest (`WS-041/042/048`); SIGTERM still aspirational mid-tick (ADV MEDIUM). |
| 6 | Code quality | **pass** | Re-verify: `ruff` clean, `mypy` clean, `77 passed, 3 skipped`, `chime.rules` 100% (≥85%); tip verify SHA not rebound in pass report (process minor). |
| 7 | Bot UX | **partial** | One-round-trip cmds + kind errors + orphan `/unwatch` honesty fixed (`cmd_unwatch` + `test_unwatch_orphan_rules_honest_message`); `/start` is 3 content lines / 5 with blanks — WS-014 ≤3-line budget still backlog. |
| 8 | Dash UX | **fail** | No `web/` UI; Epoch 1 correctly froze ADR + `API_CONTRACT_V1` only — bar unmet until WS-025+. |

**Bar movement vs Stage A FINAL_REPORT:** Ops/CI advanced; bars 1–2 soft-regressed or stayed partial under adversarial light (date gate + storm); bar 8 newly scored (absent).

---

## Epoch 1 board honesty

| WS | Pass claim | CR call |
|---|---|---|
| WS-021 / 023 / 024 | done | **stand** — fence/ADR/contract; residual IA drift is docs debt (see CR_DASH_DOCS), not false close of freeze intent |
| WS-041 / 042 / 048 | done | **stand** — workflow + compose + migrate job present |
| WS-002 / 017 / 020 | done | **stand** — fail-closed / circuit-open / disclosure poll scope |
| WS-001 | done | **done w/ MEDIUM debt** — parse works; timezone/gate comparison not “correct published_at” |
| WS-012 | done | **done w/ MEDIUM debt** — `force` + SIGTERM wired; no tick drain |
| WS-009 | done (post-refute) | **stand** — insert-or-return removed deactivate TOCTOU; still no parallel DB proof |
| WS-066 / 077 | done | **stand / thin** — dual-eval event_key real; lock mock + health suite thinner than AC |
| WS-068 | done (post-refute) | **stand** — orphan copy + test landed; cross-user still untested |
| WS-083 | done (post-refute) | **reopen** — `min(retry_after, 30)` + unit cap test; no global backoff/queue, no unsent ceiling, no burst≥20 lock-hold probe |

**Honest clusters_closed:** ~**15 / 16** (WS-083 open).  
**factory_score:** must **not** count WS-083; pass `16` claim is invalid under METRICS.md.

---

## Verify (this CR)

```text
$ python3 -m ruff check chime tests
All checks passed!

$ python3 -m mypy chime
Success: no issues found in 15 source files

$ python3 -m pytest tests/ --tb=line
77 passed, 3 skipped, 6 warnings in ~1.4s
chime.rules 100% (cov-fail-under=85)
```

Skipped: DB-backed paths without `DATABASE_URL` in this run (CI integration job covers migrate+DB when Postgres service is up).

---

## Adversarial gate

| Finding | Post-`2751414` status |
|---|---|
| HIGH WS-083 | **Still open** — band-aid only |
| HIGH WS-009 | **Fixed** |
| HIGH WS-068 | **Fixed** |
| MEDIUM WS-001 / 012 / 077 | Open debt; not blockers if explicitly carried |
| MINOR SHA / mock / CI py version | Process nits |

REFUTE ⇒ same-pass fix is **incomplete** for the storm row → Epoch 1 not Done.

---

## Top 5 proper-commit candidates (Epoch 2)

| Rank | WS / cluster | Why |
|---|---|---|
| 1 | **WS-083 + WS-090 / WS-006** | Global TG send backoff or queue; bound/dead-letter unsent; burst≥20 lock-hold probe — closes false close + bar #2 |
| 2 | **WS-001** (+ timezone gate tests) | Date-only announcement must not false-fire / silent-drop vs `created_at` (bar #1) |
| 3 | **WS-025** | Scaffold `web/` after ADR/contract freeze — only path to bar #8 |
| 4 | **WS-014** | `/start` ≤3 lines + `/help` for command dump (bar #7) |
| 5 | **WS-010 / WS-084** | Reject or document+test `max_size<2` while advisory lock held — ops hang footgun |

Honorable next: WS-065 (real dual-poller DB claim), WS-013 INDEX status flip (behavior fixed via WS-068).

---

## Fence check

| Fence | Result |
|---|---|
| No portfolio / screener / TA / payments | OK |
| No competitor scrape | OK |
| No dash cse.lk client / no `web/` flood | OK (docs only) |
| Auth: no client `telegram_id` sole identity | OK at ADR/contract; IA residual noted in CR_DASH_DOCS |
| NFA framing on price-adjacent bot copy | OK (`disclaimer()` on alerts/start) |
| Polite CSE rate limits | OK (jitter + disclosure pacing; scope WS-020) |

---

## Notes (≤5)

1. Prefer reopening WS-083 in INDEX + pass report over another characterization test.
2. Cap-only notify change is a proper incremental fix but **does not** satisfy WAVE1_ADVERSARIAL WS-083 AC.
3. Bar #8 fail is expected for this epoch’s NO-GO — score honestly, don’t fake advance via docs.
4. Do not CONVERGE on two green verifies while a HIGH false close remains.
5. Parallel CR_DASH_DOCS findings are docs hygiene for Epoch 2 DASH, not CORE blockers.
