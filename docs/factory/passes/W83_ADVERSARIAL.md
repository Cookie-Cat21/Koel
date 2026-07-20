# Wave 83 — Adversarial CLEAN

**Verdict:** CLEAN (0 findings above minor)  
**Date:** 2026-07-13  
**HEAD reviewed:** `e8070d0d` (post w82/w84/w85 claim/lock/health/count soft-accept closes)  
**Branch:** `cursor/tijori-cse-phase1-e44e`

## Scope

Adversarial re-probe of soft-accept / fail-closed surfaces after the w76–w85 isinstance wave:

- `claim_alert` / `claim_and_disarm` RETURNING ids
- `mark_alert_attempt` attempt_count
- `try_advisory_lock` / `health_check` bool soft-accepts
- PG COUNT helpers + `pool_health_snapshot`
- Spot-check bot/poller/notify coerce sites and dash SafeInteger paths

## Result

**No new medium+ defects.** Candidate claim/lock/health/count soft-accepts were already closed and pinned by parallel w82/w84/w85 (including `tests/test_wave83_medium_bugs.py` under the w84 land). Residual coerce sites (`notify` RetryAfter float, bot digit parsers, HH:MM split) are either fail-closed already or below medium.

## Diminishing returns

Further waves that only rediscover `int(True)==1` / `True == 1` / `isinstance(True, int)` on the same storage RETURNING/COUNT/lock/health paths are **anti-fuel**. Soft-accept isinstance hunting on those surfaces is exhausted. Prefer:

1. Controlled `AI_BRIEFS_ENABLED=1` soak + rate-cap honesty
2. Real user-visible dash/bot gaps inside the thin-dashboard fence
3. Early STOP on CLEAN×2 rather than pin-farming to pad toward 100

## Gate

`DATABASE_URL= pytest -m 'not integration' --cov=koel --cov-fail-under=100` green at review HEAD.
