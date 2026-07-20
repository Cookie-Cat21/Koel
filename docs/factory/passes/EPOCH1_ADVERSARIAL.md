# Epoch 1 adversarial review

**Branch:** `cursor/epoch1-execute-cb19`  
**Reviewed HEAD:** `3ad70f73b07d58a4f2e841c9538541eb8b43b38c`  
**Pass claim under review:** [EPOCH1_PASS.md](EPOCH1_PASS.md) — `clusters_closed: 16/16`, `factory_score: 16`  
**Method:** Read implementation + WAVE1 acceptance criteria; attempt to REFUTE each closed WS with a concrete failure scenario. No invented endpoints or behaviors.

## Verdict

**DO NOT CONVERGE_EPOCH1.** Findings above minor exist. Several board rows are false closes relative to their WAVE1 pass/fail criteria.

---

## Findings (ranked)

### HIGH — WS-083 closed without fixing the storm (false close)

**Claim:** WS-083 done via `dd21ba9` / `tests/test_notify_retry.py`.

**WAVE1 criterion (verbatim intent):** Pass only if burst sends back off **globally** (or queue) without unbounded advisory-lock hold, and unsent retry is **bounded**; fail if one storm stalls the poller or multiplies Telegram calls without a ceiling.

**What shipped:** `koel/notify.py` is unchanged Stage A behavior — per-message `RetryAfter` → `asyncio.sleep(retry_after + 0.5)` → one bare retry. No global backoff, no send queue, no unsent ceiling. `_retry_unsent` still walks every `message_sent=false` row each tick.

**Concrete failure:** Market-open gap claims 20 alerts; Telegram returns `RetryAfter(30)` on each. `run_once` holds `pg_try_advisory_lock` for the whole tick (`Poller.run_once` finally unlocks only after prices + disclosures + `_retry_unsent`). Wall time ≈ 20 × 30.5s while lock is held → dual-poller skip storms (`lock_held_skip`), delayed crosses, retry amplification next tick. Nested RetryAfter on the single retry path still returns `False` and leaves `message_sent=false` forever-retrying.

**Test gap:** `test_send_message_retry_after_then_succeeds` proves one message sleeps once then succeeds. It does not inject K≥20 fires, measure tick hold, or assert a ceiling. That is characterization theater, not the WAVE1 probe.

**Refute:** Marking WS-083 `done` / counting it in `factory_score` is incorrect. Probe still **fails** open.

---

### HIGH — WS-009 UniqueViolation handler does not make concurrent `/alert` safe

**Claim:** WS-009 done — catch `UniqueViolation`, return survivor.

**Concrete failure (deactivate-then-insert TOCTOU):** Partial unique index is `WHERE active`. `create_alert_rule` always `UPDATE … SET active=FALSE` for matching rows, then `INSERT`.

1. Request A: no active twin → INSERT rule id=10 → COMMIT → bot replies “alert #10”.
2. Request B (double-tap / parallel): `UPDATE` deactivates id=10 → INSERT id=11 → COMMIT → replies “alert #11”.
3. Exactly one active row (id=11), but A’s reply cites an **inactive** id. `/cancel 10` is a no-op; user thinks the alert exists.

The new `except UniqueViolation` path only helps when two INSERTs collide on the unique index. It does **not** stop B from deactivating A’s just-committed row. No concurrent DB test was added (`tests/` has zero `UniqueViolation` / parallel `create_alert_rule` proofs).

**Refute:** Acceptance “both bot replies succeed with a **valid** alert id” + “exactly one active row” is only half-met; first caller can hold a dead id. Cluster not honestly closed.

---

### HIGH — WS-068 acceptance incomplete; orphan `/unwatch` bug still live

**Claim:** WS-068 done — cancel/unwatch handler tests.

**WAVE1 acceptance:** `/cancel` happy + not-found; `/unwatch` with watch row; **orphan-rules path** replies with deactivated count **or documents + locks current behavior**; cross-user non-deactivation.

**What shipped:** Three tests — cancel missing, cancel success, unwatch when `remove_watch=True`. Missing: orphan path, cross-user.

**Concrete failure (still in `cmd_unwatch`):** Watchlist row already gone, active rules remain:

```text
removed = False
deactivated = N   # deactivate_rules_for_symbol still runs
reply = "{symbol} wasn't on your watchlist."
```

Rules are silently deactivated; user is told the symbol wasn’t watched and never sees the count. This is the PASS2 #7 / WS-013 honesty bug WS-068 was supposed to pin or document. Neither a locking regression test nor a copy fix landed.

**Refute:** WS-068 not closed per its own criterion.

---

### MEDIUM — WS-001 `dateOfAnnouncement` stamped as UTC midnight skews the backfill gate

**Claim:** Parseable `dateOfAnnouncement` yields “correct” `published_at`.

**What shipped:** `strptime(...).replace(tzinfo=UTC)` → date-only at **00:00:00 UTC**. Sample CSE rows use Colombo-facing strings like `"30 Jun 2026"` alongside ms `createdDate`.

**Concrete false positive:** Rule `created_at = 2026-06-29 20:00 UTC` (early Jun 30 SLT). Filing actually at `2026-06-30 00:30 SLT` (= `2026-06-29 19:00 UTC`) before the rule, but payload has `createdDate=null` + `dateOfAnnouncement="30 Jun 2026"` → `published_at=2026-06-30 00:00 UTC` → `published > created` → **fires historical/backfill**.

**Concrete false negative:** Rule created `2026-06-30 05:00 UTC`; same-day afternoon filing with only the date string → midnight UTC ≤ created → **never alerts** (same silent drop WS-001 aimed to fix for undated rows).

Undated→epoch fail-closed still holds. Parse formats for the common `"30 Jun 2026"` sample are real. “Correct published_at” for gate comparison is not.

---

### MEDIUM — WS-012 SIGTERM/`tick --force` only partially proven

**Code fix is real:** `run_once(force=args.force)` (no more `force or True`); `_run_both` registers SIGINT/SIGTERM.

**Residual failure:** `poller.shutdown()` uses `scheduler.shutdown(wait=False)` then `finally` closes storage/CSE. An in-flight disclosure leg (N symbols × ~0.15–0.35s sleep + HTTP) can still hold the advisory lock and borrow pool connections while `storage.close()` runs → unlock/pool errors or orphaned lock until process death. No test asserts `force=False` skips outside hours at the CLI boundary (only `is_market_open` unit coverage).

Acceptance “stops cleanly” is aspirational without draining the current tick.

---

### MEDIUM — WS-077 suite thinner than acceptance

Lock-skip and price circuit-open are pinned on `Poller` flags. Acceptance also asked for disclosure-leg → not OK and JSON/error-field shape (or HealthState). Disclosure degradation lives in `test_poller_resilience.py`, not the WS-077 file; no `/health` 503 body assertion. Risk is regression drift, not a proven current lie — but the “honesty regression suite” claim overstates coverage.

---

### MINOR — EPOCH1_PASS verify SHA ≠ branch HEAD

Pass report proves `4b5ef5b…`; current HEAD is `3ad70f7…` (the pass-report commit itself). Process docs want SHA-bound verify; the scorecard commit moved HEAD without re-running/updating the proof block.

---

### MINOR — WS-066 advisory-lock “optional” test is a mock no-op

`test_dual_eval_optional_advisory_lock_mock` only asserts `AsyncMock(side_effect=[True, False])`. Dual-eval event_key proof is real and valuable; the lock mock does not add confidence.

---

### MINOR — CI Python 3.12 vs project `requires-python >=3.11` / mypy `3.11`

`.github/workflows/ci.yml` uses 3.12. Acceptable, but typecheck target and runtime diverge slightly. Unit job `DATABASE_URL: ""` correctly skips DB tests (`.strip()` falsy).

---

## Claims that survive (not refuted above minor)

| WS | Why it stands |
|---|---|
| WS-002 | `created_at is None` → zero fires; naive/aware normalize covered by tests. |
| WS-017 | Circuit-open re-raises; poller sets `disclosure_poll_ok=False`; `[]` only on empty OK payload. |
| WS-020 | Price-only watchlist → `fetch_announcements_for_symbol` not called; disclosure symbols filtered. |
| WS-021 / 023 / 024 | Docs fence + ADR bans Bearer+`X-Telegram-Id`; API_CONTRACT_V1 aligned with session/CSRF; no `web/` flood. |
| WS-041 / 042 / 048 | Workflow, compose Postgres, migrate+pytest integration job present. |

---

## Cluster / score correction

| Pass claim | Adversarial correction |
|---|---|
| `clusters_closed: 16/16` | At most **13/16** honest closes if WS-083, WS-009, WS-068 are reopened (WS-001/012/077 may stay “done with MEDIUM debt”). |
| `factory_score: 16` | Must not count false closes (`METRICS.md`: counts without proof do not move the score). |

---

## Required before CONVERGE_EPOCH1

1. **WS-083:** Implement global send backoff / queue + bound unsent retries; probe with burst≥20 under held lock; or reopen and defer explicitly.
2. **WS-009:** Fix deactivate/insert race (e.g. insert-or-return without deactivating a twin you just lost to); add parallel DB test.
3. **WS-068:** Lock orphan `/unwatch` behavior with a test that fails today, then fix copy (or fix first) + cross-user case.
4. Re-issue pass report with honest cluster count and SHA = post-fix HEAD.

Until then: **not CONVERGE_EPOCH1**.
