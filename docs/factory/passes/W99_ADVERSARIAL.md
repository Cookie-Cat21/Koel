# Wave 99 — Adversarial re-probe after waves 91-98

**Verdict:** CLEAN (0 new medium+ findings)  
**Date:** 2026-07-13  
**HEAD reviewed:** `eded1f98b429` plus local sibling W96-W98 hardening diffs present during probe  
**Branch:** `cursor/tijori-cse-phase1-e44e`

## Scope

Re-probed `koel/` for new medium+ soft-accepts and alert correctness bugs after
the Wave 91-98 hardening lane:

- `koel.rules`: price above/below crossing, rearm, daily-move fallback,
  disclosure created-at gating, category matching, and event-key idempotency.
- `koel.poller`: price/disclosure evaluation, claim+disarm, retry backlog,
  delivery leases, dead-letter behavior, bulk disclosure attribution, and
  persisted-disclosure failure handling in the local W98 diff.
- `koel.storage`: active-rule reads, previous-state reads, alert claims,
  unsent claims, row mappers, disclosure upsert watermarks, and brief follow-up
  claims.
- `koel.bot`, `koel.notify`, `koel.adapters.cse`, and `koel.briefs`: command
  parsing, threshold/category acceptance, Telegram send boundaries, CSE payload
  normalization, URL egress guards, and brief worker row handling.

## Result

**No concrete medium+ defect found.** Remaining candidates were either already
covered by recent wave pins, fail closed before a false/missed alert path, or
require non-production mock-only return shapes without a credible alert
correctness impact.

No fix file was owned. No `tests/test_wave99_medium_bugs.py` was added.

## Gate

- `python3 -m pytest --no-cov tests/test_wave91_bot_medium_bugs.py tests/test_wave91_briefs_medium_bugs.py tests/test_wave91_config_medium_bugs.py tests/test_wave91_cse_medium_bugs.py tests/test_wave91_rules_medium_bugs.py tests/test_wave91_storage_medium_bugs.py tests/test_wave92_notify_medium_bugs.py tests/test_wave92_poller_medium_bugs.py tests/test_wave93_briefs_medium_bugs.py tests/test_wave94_bot_medium_bugs.py tests/test_wave94_cse_medium_bugs.py tests/test_wave95_rules_medium_bugs.py tests/test_wave95_storage_medium_bugs.py`
  -> **34 passed**.
- Same targeted suite with repo default coverage enabled also had **34 tests
  passing**, but failed the global `--cov-fail-under=85` threshold because this
  narrow adversarial subset covers 34% total.
