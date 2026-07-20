# CR_RUNTIME — Epoch 1 code review (poller / storage / bot / notify / `__main__`)

**Reviewer role:** Runtime CR (accurate only; no speculative endpoints)  
**Scope:** `koel/poller.py`, `koel/storage.py`, `koel/bot.py`, `koel/notify.py`, `koel/__main__.py`  
**Date:** 2026-07-11  
**Context:** Post Epoch1 fixup commits (`8e39270`, `2751414`). Checks claimed closes for disclosure scope, advisory lock, alert-create idempotency, orphan `/unwatch`, RetryAfter 30s cap, `tick --force`, `both` SIGTERM, races, connection leaks.

---

## Verdict

**PASS WITH RESIDUALS** — the Epoch1 adversarial HIGH closes (WS-009 / WS-068 / WS-083 cap / WS-020 / WS-012 signal+force) are **present in code** and match the pass scorecard’s “fixed after R1 refute” claim. Do not re-open those as false closes.

Remaining issues are real but secondary: claim/disarm intent mismatch on send failure, advisory-lock acquire/unlock exception paths that can leak a pooled connection, SIGTERM/`storage.close()` racing an in-flight tick, and RetryAfter still sleeping **per message** under the held lock (capped, not globally queued).

---

## Focus-area scorecard

| Focus | Status | Evidence |
|---|---|---|
| Disclosure poll scope | **OK** | `_poll_disclosures` builds `disclosure_symbols` from active disclosure rules only; empty → early `[], True` (no CSE announcements). Test: `test_disclosure_poll_fetches_only_disclosure_symbols`. |
| Advisory lock hold | **OK (design)** | `try_advisory_lock` keeps the pooled connection via `_lock_cm` / `_lock_conn` until `advisory_unlock`; `run_once` unlocks in `finally`; `Storage.close` unlocks first. Dual-Storage proof: `test_advisory_lock.py`. |
| `create_alert_rule` idempotency | **OK** | No deactivate-then-insert. Fetch active twin → return; else `INSERT`; `UniqueViolation` → `rollback` → re-fetch survivor. Partial unique index `idx_alert_rules_unique_active` backs it. |
| `/unwatch` orphan copy | **OK** | `removed=False` + `deactivated>0` → honest “orphan alert(s)” reply. Test: `test_unwatch_orphan_rules_honest_message`. |
| RetryAfter 30s cap | **OK (cap)** | `min(retry_after, 30.0)` then `sleep(delay + 0.5)`. Test: `test_retry_after_sleep_is_capped`. |
| `tick --force` | **OK** | `run_once(force=args.force)` — no `force or True`. Without `--force`, market-hours gate applies. |
| `both` SIGTERM | **OK (handlers)** | `_run_both` and `run_poller_forever` register SIGINT+SIGTERM → `stop.set()` → shutdown path. |
| Race conditions | **Mixed** | Claim uniqueness + create-rule race fixed; claim/disarm vs send-failure still wrong relative to comment. |
| Connection leaks | **Residual** | Happy path OK; error/shutdown interleaving can leak or close under borrow. |

---

## Ranked findings

### P1 — Fix soon (correctness / lock / pool)

| # | Finding | Evidence | Why it matters |
|---|---|---|---|
| 1 | **`_claim_and_send` returns `False` after a successful claim when Telegram send fails — so price disarm is skipped** | `poller._claim_and_send`: claim → send; on send fail `return False`. `_evaluate_price_snaps`: `if not claimed: continue` then disarm. Comment at 168–170 claims disarm “even if Telegram send failed.” | Comment/intent lie. Sticky-above crossing usually prevents an immediate duplicate, and `_retry_unsent` still delivers. But armed stays `True`, so a later genuine re-cross can fire without a rearm dip, and the “disarm-after-claim” invariant used elsewhere in reviews is not what the code does. Fix: return “claimed” separately from “sent”, or disarm when `log_id is not None`. |
| 2 | **`try_advisory_lock` can leak a pool connection if `pg_try_advisory_lock` raises after `__aenter__`** | `storage.py` 438–446: `cm = self._pool.connection(); conn = await cm.__aenter__();` then `execute` with no `try/except` that always `__aexit__`s on failure before `_lock_conn` is set. | Pool `max_size` is 4; one leaked checkout permanently shrinks capacity. Under repeated DB blips, poller + bot share the same pool in `both` and can stall. |
| 3 | **`advisory_unlock` can leak the same way if `pg_advisory_unlock` raises before `__aexit__`** | `storage.py` 457–462: unlock `execute` then `__aexit__`; exception skips return-to-pool and leaves `_lock_*` set. | Next `try_advisory_lock` on this `Storage` returns `False` forever (`_lock_conn is not None`), so every tick becomes `poll_lock_held` until process restart — health red, no polls. |
| 4 | **SIGTERM / `both` shutdown can `storage.close()` while a tick still holds the lock and borrows other connections** | `poller.shutdown` → `scheduler.shutdown(wait=False)`. `_run_both` `finally`: `await poller.shutdown()` then `await storage.close()` without draining the in-flight `run_once`. | In-flight disclosure loop (per-symbol HTTP + 0.15–0.35s sleep) or Telegram sleeps can race `close()`. Unlock from `close()` vs tick `finally` can interleave at `await` points on one event loop. Residual of WS-012 “stops cleanly” — handlers exist; drain does not. |
| 5 | **RetryAfter 30s cap does not bound aggregate lock hold under a burst** | `notify.send_message` sleeps per call (capped). `run_once` holds the advisory lock across prices + disclosures + `_retry_unsent`. | Cap correctly stops a single `RetryAfter(999)` from sleeping ~999s (WS-083 fix as shipped). N failed sends still ≈ `N × 30.5s` under lock → dual-poller `lock_held_skip` storms. Not a false close of the *cap*; still an open storm residual. |

### P2 — Medium residuals

| # | Finding | Evidence | Notes |
|---|---|---|---|
| 6 | **`tick` CLI has no `try/finally` around open → poll → close** | `__main__.py` `_tick`: `open` → `run_once` → `aclose`/`close` sequential. | If `run_once` / unlock raises, CSE client and pool are not closed. `run_once` swallows most poll errors, so this is uncommon but real on lock/DB failures. |
| 7 | **`create_alert_rule` UniqueViolation path can still raise if the winner is deactivated before re-fetch** | After `UniqueViolation` + `rollback`, `_fetch_active_rule` → `None` → `raise`. | Narrow window: concurrent `/cancel` (or unwatch deactivate) between loser UniqueViolation and re-fetch. User sees an error instead of “recreate”. No parallel DB test exists for the happy concurrent path either. |
| 8 | **Orphan disclosure rules are invisible to the poller** | `watched_symbols()` drives both price and disclosure legs; disclosure rules without a watchlist row are never fetched. | `/unwatch` now deactivates rules, so bot path is consistent. Manual SQL / future API that deletes watch without deactivate leaves silent undead rules. |
| 9 | **Retry bare resend drops `disable_web_page_preview=False`** | First `send_message` passes the kwarg; RetryAfter retry calls `bot.send_message(chat_id=..., text=...)` only. | Behavioral inconsistency on preview; low severity. |
| 10 | **CLI help still calls `tick` “one forced poll”** | `argparse` choices help: `tick (one forced poll)`; actual force is `--force`. | Ops footgun: `python -m koel tick` outside hours exits with `Fired 0` and looks like a no-op bug. |

### P3 — Minor / hygiene

| # | Finding | Notes |
|---|---|---|
| 11 | **No concurrent DB test for `create_alert_rule`** | Logic is sound against `idx_alert_rules_unique_active`; proof is code reading + UniqueViolation handler, not a two-task Postgres test. |
| 12 | **`test_dual_eval_optional_advisory_lock_mock` is still a mock no-op** | Real lock coverage remains `test_advisory_lock.py` (needs `DATABASE_URL`). Dual-eval claim tests are valuable separately. |
| 13 | **`_run_bot` relies on PTB for signals; health server always started** | Acceptable. `post_shutdown` closes storage/CSE; if `run_polling` dies before `post_init`, `close()` on an unopened pool depends on psycopg_pool behavior — edge only. |
| 14 | **Disclosure still uses a 365-day window per disclosure symbol** | Scope fix (WS-020) is correct; cost scales with disclosure-rule count, not full watchlist. Future bulk feed is backlog, not a regression. |

---

## Claims that stand (do not re-refute as false closes)

1. **WS-020** — Price-only watchlist symbols do not call `fetch_announcements_for_symbol`.  
2. **WS-009 (post-2751414)** — Idempotent create is insert-or-return; deactivate-then-insert TOCTOU from the adversarial write-up is **gone**.  
3. **WS-068 orphan copy (post-2751414)** — Orphan path reply + unit test landed.  
4. **WS-083 sleep cap (post-2751414)** — `min(..., 30.0)` + test asserting `slept <= 30.5`.  
5. **WS-012 force honesty** — `force=args.force`.  
6. **WS-012 SIGTERM registration** — both `both` and poller-forever handle SIGTERM.  
7. **Session advisory lock sticky connection** — design matches the Pass-2 footgun fix; unlock on `close()`.

---

## Suggested fix order (if a follow-up pass runs)

1. Split claim vs send success in `_claim_and_send` / disarm on claim (P1 #1).  
2. Wrap advisory lock acquire/release so `__aexit__` always runs; clear `_lock_*` in `finally` (P1 #2–3).  
3. On shutdown: wait for current tick (or cancel + unlock) before `storage.close()` (P1 #4).  
4. Optionally: global send gate / bound `_retry_unsent` per tick so RetryAfter cannot multiply lock hold (P1 #5).  
5. `tick` try/finally + honest argparse help (P2 #6/#10).

---

## Out of scope (not scored here)

Adapter HTML/JSON parsing, rules engine pure functions, migrations SQL beyond the unique index that backs create-rule, dash/`web/`, CI workflow. Those belong to other CR lanes.
