# Epoch 1 — Code review: TESTS

**Scope:** `tests/test_dual_eval_lock.py`, `test_bot_handlers.py`, `test_health_honesty.py`, `test_notify_retry.py`, `test_poller_resilience.py`, plus disclosure/adapter tests touched in Epoch 1 (`test_disclosure_rules.py`, `test_adapters_normalize.py`, `test_adapters_circuit.py`).  
**HEAD reviewed:** `2751414` (post same-pass adversarial fixups).  
**Method:** Diff each test’s assertions against production call graph and WAVE1 acceptance; prefer concrete “test green while bug/gap remains” over style nits.  
**Verdict:** Several Epoch 1 closes are still **test-theater or incomplete probes**. Dual-eval event_key + orphan `/unwatch` copy + disclosure rule fail-closed are real. WS-083 and WS-077 remain under-proven relative to their own criteria.

---

## Ranked findings

### 1. HIGH — `test_notify_retry.py` closes WS-083 without the storm probe

**What the tests prove:** One `send_message` call: `RetryAfter` → one `asyncio.sleep` → bare retry succeeds; `RetryAfter(999)` sleeps ≤ 30.5s.

**What production still does:** Per-message sleep under the poller advisory lock (`Poller.run_once` unlocks only in `finally` after prices + disclosures + `_retry_unsent`). Cap is **per call**, not global. Nested `RetryAfter` on the retry path returns `False` (leaves `message_sent=false`); `NetworkError`/`TimedOut` never retry — **none of these are tested**.

**False confidence:** Cap test + board “closes: WS-083” read as storm-fixed. WAVE1_ADVERSARIAL pass criterion still requires burst ≥20 claimed sends, tick wall-time / lock-hold ceiling, and bounded unsent amplification. A green suite still allows `K × min(retry_after, 30) + 0.5` lock hold and unbounded `_retry_unsent` walks.

**Accuracy note:** The 30s cap is a real mitigation and is correctly pinned; calling the *cluster* closed on these two tests is not.

---

### 2. HIGH — `test_health_honesty.py` under-delivers WS-077 acceptance

**Acceptance (WAVE1_QUALITY):** lock-skip → health not OK; watchlist + disclosure-leg fail + OK prices → not OK; price circuit-open → not OK; JSON/error-field shape (or `HealthState`) pinned.

**What shipped:** Two Poller-flag tests (circuit-open with watchlist; lock skip). No `HealthState.update`, no HTTP 503/`/health` body, no disclosure-leg case in this file.

**Gaps that keep a bug green:**

| Gap | Why it matters |
|---|---|
| No `price_poll_ok` / `disclosure_poll_ok` asserts on circuit-open | `last_tick_ok=False` alone can pass while leg flags stay stale/`True` |
| Lock-skip does not assert unlock-on-success path elsewhere | Degraded ticks never assert `advisory_unlock` awaited — lock leak in `finally` would not fail these tests |
| Disclosure degradation only in `test_poller_resilience` | Split coverage; WS-077 file cannot regress-lock the honesty claim alone |
| No wiring through `chime.health.HealthState` / status code | Ops reads JSON `status`/`lock_held_skip`/`last_error`; flags-only unit tests miss response shape regressions |

Disclosure-leg → `disclosure_poll_ok is False` + `last_tick_ok is False` **does** exist in resilience (`test_poller_survives_junk_then_ok`) — real pin, wrong home, still no health JSON.

---

### 3. MEDIUM — `test_dual_eval_optional_advisory_lock_mock` is mock no-op theater

**Real value in the file:** Snap ids 10 vs 11 → identical `event_key` → `FakeAlertLog` second claim False; different minute → two keys. Matches WS-066 intent (CI-always UNIQUE semantics without Neon).

**Theater:** `test_dual_eval_optional_advisory_lock_mock` only drives `AsyncMock(side_effect=[True, False])`. It never constructs `Poller`, never holds a pooled connection, never interacts with `Storage.try_advisory_lock` implementation. Real lock proof remains `test_advisory_lock.py` (DB-gated). This third test cannot fail on a production lock bug.

**Secondary mismatch (acceptable if documented):** `FakeAlertLog.claim_and_send` is not `Storage.claim_alert` + separate `send`; dual-eval still correctly encodes `(rule_id, event_key)` uniqueness. Do not treat it as dual-`run_once` proof (that remains integration / WS-065).

---

### 4. MEDIUM — `test_bot_handlers.py` still incomplete vs WS-068 (and never covers WS-067)

**Fixed and pinned (real):** cancel not-found / success; unwatch with watch row; orphan path copy (`wasn't on your watchlist` + deactivated count) — matches current `cmd_unwatch` after `2751414`.

**Still missing vs acceptance:**

- **Cross-user non-deactivation** — `deactivate_alert` / `deactivate_rules_for_symbol` are SQL-scoped by `user_id`, but tests only script AsyncMock return values for one user. A regression that drops the `user_id` predicate would not fail.
- **Cancel edges in production, untested:** missing args → usage; non-numeric id; `rule_id <= 0`; `#7` via `lstrip("#")`.
- **Unwatch edges untested:** missing args; `normalize_symbol` reject; `removed=False` and `deactivated=0` (plain “wasn't on watchlist”).
- **WS-067 never landed** in this file — no `/watch`, `/alert`, `/myalerts`, `/mywatchlist`. Filename/harness exist only for cancel/unwatch.

Handlers that mock storage cannot catch TOCTOU in `create_alert_rule` (WS-009) — out of scope for these units, but the suite still has **zero** concurrent create tests.

---

### 5. MEDIUM — Adapter normalize locks UTC-midnight `dateOfAnnouncement` without gate interaction

`test_announcement_uses_date_of_announcement_when_created_date_null` asserts `published_at == 2026-06-30 00:00:00+00:00`. That **characterizes** `_parse_date_of_announcement(...).replace(tzinfo=UTC)`, including the Colombo-date → UTC-midnight skew called out in Epoch 1 adversarial review.

**Bug can remain green:** No test builds `announcement_to_disclosure` → `evaluate_disclosure_rules` where a SLT filing date string falsely clears `published > created_at` (false positive) or blocks a same-day afternoon filing (false negative). Undated→epoch and `created_at is None` fail-closed in `test_disclosure_rules.py` are solid; the dated-string path is not end-to-end gated.

---

### 6. MEDIUM — `test_poller_resilience.py` false names, thin hours, force always on

| Issue | Detail |
|---|---|
| `test_poller_survives_junk_then_ok` | Name implies junk trade rows then recovery; body only raises `RuntimeError` on announcements. Trade-summary junk skip (`TradeSummaryRow` ValidationError continue) remains untested at list level (WS-069 still open). |
| Market hours table | Covers Fri 09:30 open, 14:31 closed, Saturday. Missing **09:29**, **exact 14:30** (inclusive close in `is_market_open`), Sun, and UTC Fri→SLT Sat edge called for in WS-073. |
| All `run_once` calls use `force=True` | Never proves `force=False` skips outside hours **without** taking the advisory lock. Hours helper alone does not cover the Poller early-return branch. |
| Circuit-open overlap | Near-duplicate of `test_health_honesty` circuit case; neither asserts `advisory_unlock` after degraded success path. |
| WS-020 pins | `test_disclosure_poll_skips_price_only_symbols` / `_fetches_only_disclosure_symbols` are accurate and valuable. |

---

### 7. MEDIUM — Adapter circuit tests are narrow (correct but incomplete contrast)

`test_adapters_circuit.py` correctly proves open breaker → `CircuitOpenError` re-raised (WS-017). It does **not** contrast with HTTP-OK empty `reqCompanyAnnouncement` → `[]` (the failure mode the WS was written to prevent: empty success masking open circuit). Poller resilience covers poller-level Exception handling, not the adapter empty-vs-open distinction in one place.

---

### 8. MINOR — Notify kwargs / timedelta / failure branches uncovered

- First-call assert checks `chat_id`/`text` only; comment claims `disable_web_page_preview` on first send and bare retry — **not asserted** (production first call sets `disable_web_page_preview=False`; retry omits it).
- `_retry_delay_seconds(timedelta)` exists for PTB v22.2+; tests only pass int `RetryAfter` (suite already emits `PTBDeprecationWarning`).
- No test that nested `RetryAfter` / `NetworkError` / `TimedOut` / generic `TelegramError` return `False` without extra sleeps.

---

### 9. MINOR — Disclosure rules strong; adapter→rules epoch path not wired

`test_disclosure_rules.py` correctly pins equality, `created_at is None`, naive/aware. Missing explicit: disclosure with `published_at=1970-01-01` (adapter undated path) never fires against a normal rule — implied by `published <= created` but not named as adapter contract.

---

## What the suite does prove (do not reopen)

| Area | Proof |
|---|---|
| WS-066 core | Dual snap ids → one `event_key` → one FakeAlertLog send; minute contrast |
| WS-068 orphan copy | Honest reply when watch missing but rules deactivated |
| WS-002 / WS-074 core | Fail-closed None `created_at`; equality; naive/aware no TypeError |
| WS-017 (adapter raise) | Circuit open does not return `[]` from fetch helpers |
| WS-020 | Price-only watchlist skips announcement HTTP; mixed symbols fetch only disclosure symbols |
| RetryAfter cap | Sleep ceiling ≤ 30.5s for a single message |

---

## Priority fixes (tests only)

1. **WS-083:** Add burst probe (mock Bot `RetryAfter` on ≥20 sends inside one `run_once` or `_retry_unsent` loop); assert lock-hold / sleep budget ceiling or reopen the cluster. Cover nested RetryAfter → `False`.
2. **WS-077:** Drive `HealthState` (or handler) for lock-skip + disclosure-leg + circuit-open; assert `price_poll_ok` / `disclosure_poll_ok` / `lock_held_skip` / HTTP 503 shape; assert `advisory_unlock` after degraded locked tick.
3. **WS-068:** Cross-user FakeStorage case; cancel `#id` / invalid / missing-args; unwatch empty deactivated.
4. **Delete or rewrite** `test_dual_eval_optional_advisory_lock_mock` — point at real `test_advisory_lock` or Poller lock-skip instead.
5. **Adapter+rules:** One case `dateOfAnnouncement` date-only × `created_at` near midnight SLT boundary; list-level junk trade row skip (WS-069).
6. **Poller:** Rename junk test; add `force=False` outside-hours early return; 09:29 / 14:30 boundaries.

---

## Scorecard impact

| Epoch 1 WS | Test-review call |
|---|---|
| WS-066 | **Keep closed** (drop optional lock mock from the proof claim) |
| WS-068 | **Closed for orphan copy**; acceptance incomplete without cross-user + parse edges |
| WS-077 | **Reopen or mark debt** — Poller flags only; not health honesty suite |
| WS-083 | **Reopen** — cap characterization ≠ storm criterion |
| WS-017 / WS-020 / WS-002 | **Keep** with noted residual mediums on dated-string gate / empty-OK contrast |
