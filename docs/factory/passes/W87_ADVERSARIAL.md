# Wave 87 — Adversarial CLEAN (WS-087 clock skew)

**Verdict:** CLEAN (0 findings above minor)  
**Date:** 2026-07-13  
**HEAD reviewed:** `a2d54b0f` (post w86 loop status / w88 ops polish)  
**Branch:** `cursor/tijori-cse-phase1-e44e`  
**Catalog:** WS-087 — Clock skew between app host and Postgres / CSE

## Scope (shrunk per R1_ADVERSARIAL)

Single code invariant — disclosure / price **claim eligibility** must not use host
wall-clock windows. Dropped NTP sermon and Neon `SELECT now()` live probe as
pass/fail criteria (ops honesty only).

## Probe

1. **Static:** `chime/rules.py` contains no `datetime.now` — eval is pure over
   `(previous, snapshot)` / `(disclosure, rules)`.
2. **Disclosure:** `published_at` vs `rule.created_at` (CSE epoch vs PG
   `RETURNING created_at`). Inject ±5m / ±1h on those data stamps — fire only
   when published is strictly after created; no wall-clock gate.
3. **Price cross:** fires on prev→curr level transition; snapshot `ts` skewed
   ±5m / ±1h still claims the same `event_key` when `snapshot.id` is set.
4. **Daily move:** Colombo day key comes from `snapshot.ts` (prefer CSE
   `lastTradedTime`), not host now; ±1h trade-time skew within the same SLT
   day keeps one `move:{rule}:{day}` key.
5. **Poller residual (minor):** disclosure HTTP `fromDate`/`toDate` and
   `is_market_open` use host clock. During the 09:30–14:30 SLT poll window,
   ±1h cannot flip the Colombo calendar day; off-hours force ticks near
   midnight are ops edge, not claim gating. Health `last_tick_at` /
   `alert_latency_ms` are host-relative ops signals only.

## Result

**No new medium+ defects.** Claim paths already satisfy the shrunk WS-087
pass criterion. Characterization pin: `tests/test_wave87_clock_skew.py`.

## Gate

`DATABASE_URL= pytest -m 'not integration' --cov=chime --cov-fail-under=100`
green at review HEAD (+ this pin).
