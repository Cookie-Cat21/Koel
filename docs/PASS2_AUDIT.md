# Pass 2 adversarial audit — Chime Stage A (post–Pass 1)

**Verdict: Pass 1 did not close the dual-poller / leader-election bar.** Session advisory locks are acquired and released on *different pooled connections*, so the lock is ineffective and can stall polling. Most other Pass 1 fixes hold under code review. The suggested “sticky above + failed send → new `event_key` duplicate” path is **refuted** for normal evaluate semantics.

Ranking key: **score ≈ severity × user impact ÷ effort**. Severity: critical≈4, high≈3, medium≈2, minor≈1. Effort: S≈÷1, M≈÷2, L≈÷3.

---

## Ranked findings

### 1. Session advisory lock is useless (and harmful) with `AsyncConnectionPool`
- **Severity:** critical  
- **Score:** 20  
- **Failure scenario:** `Storage.try_advisory_lock` runs `pg_try_advisory_lock` inside `async with self._pool.connection()`, then **returns the connection to the pool** while the session still holds the lock. Default pool reset only rollbacks open transactions — it does **not** `DISCARD ALL` / clear session advisory locks (`psycopg_pool` `_reset_connection`). `advisory_unlock` opens a **new** pooled connection and calls `pg_advisory_unlock`, which returns false on a session that does not hold the lock. Result:
  1. Lock stays held on whatever backend first acquired it.
  2. Later `try_advisory_lock` on a *different* pool member → `false` → `poll_skipped_lock_held` → **missed polls** (default `max_size=4`).
  3. Dual-poller “single leader” claim in Pass 1 is **false**; coordination is broken. Crossing-stable `event_key` still dedupes same-minute/same-price races *if* two cycles both run, but intermittent lock-skip starves alerts and `_retry_unsent`.
- **Where:** `chime/storage.py:388–399`, `chime/poller.py:77–100`; pool default `max_size=4` in `Storage.__init__`.  
- **Fix:** Hold **one** connection for lock → entire `run_once` work → unlock (or a dedicated long-lived lock connection). Alternatively `pg_try_advisory_lock` + unlock on that same checkout only. Do not acquire session locks across pool checkout boundaries.  
- **Acceptance:** With `max_size≥2`, run 20 consecutive `run_once(force=True)` → zero `poll_skipped_lock_held` when sole poller; two concurrent pollers → exactly one cycle executes per tick window; `pg_locks` shows no orphaned advisory lock after unlock.  
- **Effort:** S  
- **Pass 1 claim:** “Dual poller — `pg_try_advisory_lock`” — **refuted as fixed.**

### 2. Health stays green while the poller is lock-starved
- **Severity:** high  
- **Score:** 12  
- **Failure scenario:** After finding #1, most cycles early-return at `poll_skipped_lock_held` **before** the `try`/`finally` that updates `last_tick_at` / `last_tick_ok`. Health keeps the last successful tick (`ok=True`). Ops sees `/health` 200 while price/disclosure polling has stopped.  
- **Where:** `chime/poller.py:77–80` (early return), `88–100` (status only updated when lock held); `chime/health.py`; `__main__` / `run_poller_forever` health loops.  
- **Fix:** On lock skip, set `last_tick_ok=False` (or `degraded` + `last_error=lock_held`) and refresh `last_tick_at`; or fix #1 so skips only happen for a true second replica.  
- **Acceptance:** Force stuck session lock → `/health` 503 with explicit lock/skip error within one health refresh interval.  
- **Effort:** S (status) / S (root-cause #1)  
- **Pass 1 claim:** “Health honesty” — **partially refuted** (CSE circuit path fixed; lock-skip / silent stall not covered).

### 3. `last_tick_ok` ignores disclosure-leg failure
- **Severity:** medium  
- **Score:** 6  
- **Failure scenario:** Prices fetch OK; every `fetch_announcements_for_symbol` fails (or circuit returns `[]` after open). `disclosure_poll_ok=False` is stored in health details, but `last_tick_ok = price_ok if symbols else True` and `health.ok = db_ok and last_tick_ok` → still **200**. Disclosure alerts freeze while ops trusts green.  
- **Where:** `chime/poller.py:91–93`, `164–200`; health consumers in `__main__.py` / `run_poller_forever`.  
- **Fix:** Treat non-empty watchlist + `not disc_ok` as degraded (503) or require both legs OK when disclosure rules exist.  
- **Acceptance:** Watchlist + forced disclosure failures + OK prices → `/health` 503 (or documented `degraded` that fails the probe).  
- **Effort:** S  
- **Pass 1 claim:** health tracks `disclosure_poll_ok` — field exists but **does not drive** `ok`.

### 4. Missing `createdDate` → `published_at=now()` bypasses backfill filter
- **Severity:** medium  
- **Score:** 6  
- **Failure scenario:** Pass 1 filter `published_at <= rule.created_at` works when CSE supplies epoch `createdDate` (samples do). `_ms_to_dt(None)` returns `datetime.now(UTC)`. Any historical row with null `createdDate` is stamped “just now”, compares **after** `rule.created_at`, and fires on first insert — backfill flood for those rows. `dateOfAnnouncement` is ignored.  
- **Where:** `chime/adapters/cse.py:123–126`, `187`; `chime/rules.py:200–201`.  
- **Fix:** Prefer `dateOfAnnouncement` when `createdDate` missing; if still unknown, seed/insert without notifying (or skip fire). Never use wall-clock now as `published_at` for alert gating.  
- **Acceptance:** Fixture row with `createdDate=null` + old `dateOfAnnouncement` (or neither) + disclosure rule → zero Telegram; dated new row → one send.  
- **Effort:** S  
- **Pass 1 claim:** disclosure backfill fixed — **holds for dated rows**; **residual flood** for undated.

### 5. `created_at is None` fail-open (and naive/aware compare risk)
- **Severity:** medium  
- **Score:** 4  
- **Failure scenario:** `if rule.created_at is not None and disclosure.published_at <= rule.created_at` — when `created_at` is missing, **all** new inserts fire. Schema/`create_alert_rule` normally supply `TIMESTAMPTZ`, so production load path is OK; any code path or test-like construction without `created_at` floods. Separately, naive vs aware `published_at`/`created_at` raises `TypeError` (verified) and aborts the disclosure loop for that cycle (outer `run_once` except → tick fail). Unlikely with psycopg timestamptz + adapter UTC, but the compare is unguarded.  
- **Where:** `chime/rules.py:200–201`; `chime/domain.py` `created_at: datetime | None = None`; `_row_to_rule`.  
- **Fix:** Fail-closed: `created_at is None` → do not fire; normalize both sides to UTC aware before compare.  
- **Acceptance:** Rule with `created_at=None` + any disclosure → zero events; mixed naive/aware inputs → no exception, correct skip/fire.  
- **Effort:** S  

### 6. Successful `_retry_unsent` never disarms the rule
- **Severity:** medium  
- **Score:** 4  
- **Failure scenario:** Claim succeeds, send fails → `_claim_and_send` returns False → **armed stays True** (intentional). Later `_retry_unsent` marks `message_sent=True` but **never** `set_rule_armed(False)`. Crossing-vs-previous still prevents sticky re-fire (see Refuted #A), so this is not a user-visible duplicate under normal snapshots. It does weaken the armed safety net against missing/reordered snapshot history (armed was meant to suppress a second fire without a clean rearm).  
- **Where:** `chime/poller.py:146–153`, `202–214`, `216–222`.  
- **Fix:** On successful retry, disarm if the claimed event was a price above/below rule (join `alert_rules` / store type on log), or disarm in `_claim_and_send` after claim regardless of send (Pass 1 audit’s alternate), keeping retry for delivery only.  
- **Acceptance:** Flaky send then retry success → rule `armed=False` until price rearm; no sticky duplicate; one Telegram.  
- **Effort:** S  

### 7. `/unwatch` when not on watchlist still deactivates rules but lies
- **Severity:** medium  
- **Score:** 4  
- **Failure scenario:** `deactivate_rules_for_symbol` always runs; if `remove_watch` returns false, reply is only “wasn't on your watchlist” — user not told alerts were cancelled. Edge case after manual DB edits / partial state; normal `/alert` always `add_watch`s first.  
- **Where:** `chime/bot.py:126–134`.  
- **Fix:** Always report deactivated count; if neither watch nor rules, then “wasn't watching.”  
- **Acceptance:** Orphan active rules + `/unwatch SYMBOL` → rules inactive + honest reply.  
- **Effort:** S  
- **Pass 1 `/unwatch` owner-rules fix:** **holds** for the cross-user leak when watchlist remove succeeds.

### 8. Unsent retry still unbounded (Pass 1 #17 deferred)
- **Severity:** medium  
- **Score:** 3  
- **Failure scenario:** User blocks bot / permanent TelegramError → every successful lock cycle retries up to 50 unsent forever; noise and API burn. Worsens if #1 causes irregular cycles.  
- **Where:** `chime/poller.py:216–222`, `chime/storage.py:428–444`.  
- **Fix:** attempts / `next_retry_at` / dead-letter after N.  
- **Acceptance:** Permanent failure stops after N; new alerts still send.  
- **Effort:** M  

### 9. Concurrent identical `/alert` still IntegrityError (Pass 1 #14)
- **Severity:** medium  
- **Score:** 4  
- **Failure scenario:** Double-tap hits partial unique index `idx_alert_rules_unique_active`; no catch in `create_alert_rule` / bot.  
- **Where:** `db/migrations/001_initial.sql:79–81`, `chime/storage.py:271–289`, `chime/bot.py` `cmd_alert`.  
- **Fix:** Catch unique violation → return existing active rule.  
- **Acceptance:** Parallel identical creates → one active row, both replies success.  
- **Effort:** S  

### 10. `both` mode still has no SIGTERM; `tick` still always forces (Pass 1 #15/#16)
- **Severity:** medium / minor  
- **Score:** 4 / 2  
- **Failure scenario:** `_run_both` `while True` without signal handlers (unlike `run_poller_forever`). `tick` uses `force=args.force or True` — `--force` dead; hours never respected.  
- **Where:** `chime/__main__.py:57–72`, `172`.  
- **Acceptance:** SIGTERM stops `both` cleanly; `tick` without `--force` outside hours skips work.  
- **Effort:** S  

### 11. Minute+price `event_key` blocks same-minute re-fire after rearm
- **Severity:** minor  
- **Score:** 2  
- **Failure scenario:** Price crosses above, disarms, dips below and re-crosses **within the same UTC minute at the same print price** → identical `event_key` → claim conflict → silent miss until minute or price changes. Rare at 60s poll; intentional dual-poller tradeoff.  
- **Where:** `chime/rules.py:33–44`.  
- **Fix:** Include armed-generation / rearm sequence, or omit price and use crossing id.  
- **Acceptance:** Synthetic same-minute re-cross after rearm delivers exactly one new alert.  
- **Effort:** S  

### 12. No automated tests for `/cancel` / `/unwatch` deactivation
- **Severity:** minor  
- **Score:** 1  
- **Failure scenario:** Regressions in bot/storage wiring go unnoticed (handlers exist and look correct).  
- **Where:** `chime/bot.py`; `tests/` (no matches for cancel/unwatch).  
- **Acceptance:** Unit/integration: cancel → inactive; unwatch → owner rules inactive while other user’s remain.  
- **Effort:** S  

---

## Focus scenario verdicts

### 1) Disclosure backfill — can historical still flood?
| Claim | Verdict |
|---|---|
| Pass 1 `published_at <= rule.created_at` stops dated history | **Holds** (engine + unit tests; DB `created_at NOT NULL`). |
| Naive vs aware `created_at` breaks filter | **Unlikely in prod** (timestamptz + UTC adapter); unguarded compare → TypeError risk if naive appears. |
| Missing `created_at` on old rows | Schema always has it; **fail-open if None** is residual (#5). |
| Undated CSE rows | **Yes, can still flood** via `published_at=now()` (#4). |

### 2) Claim-before-disarm — send fail → armed → next cycle duplicate?
**Verified code path** (`_evaluate_price_snaps` + `_claim_and_send`):

1. `claim_alert` inserts `message_sent=False`.
2. `send` fails → return `False`.
3. Caller `continue` → **`set_rule_armed(False)` does not run** → **armed stays True**.
4. Same cycle / later: `_retry_unsent` may deliver the **same** `alert_log` row.

**Next poll while price stays above threshold:** `get_previous_state` returns the prior snapshot already ≥ threshold → `crossed_above(prev, curr, thr)` is **false** → **no new evaluate event**, hence **no new `event_key`**. Duplicate-via-sticky-reevaluate is **refuted**.

Pass 1 “claim then disarm after successful claim+send” **holds** for the original lose-forever bug (disarm-before-claim). Residual: retry success does not disarm (#6); lock-starvation can delay retry (#1/#2).

### 3) Dual poller advisory lock vs pool
**Confirmed broken** — see finding #1. Unlock does not run on the locking session; session lock survives pool return.

### 4) `/cancel` and `/unwatch`
| Item | Verdict |
|---|---|
| `/cancel ALERT_ID` | **Fixed** — `deactivate_alert(user_id, rule_id)` + handler registered. |
| `/unwatch` stops owner alerts | **Fixed** when watch row removed — `deactivate_rules_for_symbol`. |
| UX edge | **#7** when not on watchlist. |

### 5) Health
| Item | Verdict |
|---|---|
| Watchlist + price circuit → `last_tick_ok=False` | **Fixed** (test asserts). |
| Poller-only health loop | **Fixed** (`run_poller_forever(..., health=)`). |
| Lock skip / disclosure-only fail | **Still lies or under-reports** (#2, #3). |

### 6) `event_key` minute+price
| Item | Verdict |
|---|---|
| Two pollers, same minute, same price | Same key → one claim (**OK** if both evaluate). |
| Same-minute rearm re-cross | **Impossible** (#11) — tradeoff. |
| Sticky + failed send → re-fire next minute | **Refuted** (no cross without `prev < thr`). |

---

## Refuted / overstated concerns

| Concern | Verdict |
|---|---|
| **A. Sticky above + send fail → new minute `event_key` → duplicate Telegram** | **Refuted.** Armed stays True, but next snapshot’s previous price is already on the far side of the threshold, so evaluate does not emit a second fire. Delivery is via `_retry_unsent` on the original claim. |
| **B. Pass 1 disclosure filter is a no-op** | **Refuted** for normal dated CSE rows + DB `created_at`. |
| **C. Disarm-before-claim loss still present** | **Refuted.** Disarm only after `_claim_and_send` returns True (send success). Crash after successful send before disarm: sticky evaluate still quiet; later true re-cross can fire (armed left True is acceptable under crossing semantics). |
| **D. `/cancel` / `/unwatch` missing** | **Refuted** as missing features; residual UX/edge only. |
| **E. Dual-poller fixed by advisory lock** | **Refuted** — lock implementation is incorrect (#1). `event_key` is a partial mitigator only. |

---

## Pass 1 scorecard (adversarial re-score)

| # | Pass 1 claim | Pass 2 |
|---|---|---|
| 1 | Disclosure backfill | **Mostly pass** — residual undated/`created_at` None (#4/#5) |
| 2 | Claim-before-disarm | **Pass** for loss bug; sticky-duplicate scare **refuted**; retry disarm gap **medium** (#6) |
| 3 | `/cancel` + `/unwatch` | **Pass** (+ UX edge #7) |
| 4 | Dual poller lock + event_key | **Fail** on lock (#1); event_key **partial** |
| 5 | Health honesty | **Partial** (#2/#3) |
| 6–12 | Latency doc, junk rows, move cross, START copy, upstream errors, URL, Colombo dates | **Hold** under this review (not re-litigated) |

---

## Bottom line

**Not “only intentional minor tradeoffs.”** Finding **#1 (advisory lock + connection pool)** is a **critical** production defect that **refutes** Pass 1’s dual-poller fix and can **skip polls** even for a single replica. Fix that first; then tighten health on lock-skip and disclosure-leg failure.

The claim that failed send + sticky price produces a **second logical crossing alert** via a new `event_key` is **incorrect** given current `crossed_*` + snapshot chaining; do not prioritize that as a duplicate bug.

After #1–#3, remaining items are medium (undated disclosure flood, fail-open `created_at`, retry disarm, IntegrityError, unbounded unsent, `both`/tick leftovers) or minor intentional `event_key` tradeoffs.
