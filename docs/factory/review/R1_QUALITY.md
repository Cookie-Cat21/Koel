# R1 — Adversarial review: QUALITY / test workstreams

**Scope:** `WAVE1_QUALITY.md` (WS-061…WS-080) vs current `tests/` + Stage A reports.  
**Baseline suite (accurate):** 11 test modules, **58** collected cases (`pytest --collect-only`); default run ≈ **55 pass / 3 skip** without `DATABASE_URL` (skips: `test_advisory_lock`, 2× `test_poller_integration`). `chime.rules` gated ≥85% / measured 100%.  
**Verdict:** Directionally useful on **real gaps** (bot handlers, health honesty pins, dual-poller claim, same-minute tradeoff lock). Inflated by Hypothesis theater on already-table-tested `rules.py`, process/doc WS that farm commit count, and several WS that **reinvent** `test_idempotency`, `test_domain_format`, move/crossing tables, and thin market-hours coverage. Cut/merge before Pass 1; do **not** broaden cov-fail gates yet.

---

## 1. Verdict

| Claim in WAVE1_QUALITY | Adversarial score |
|---|---|
| “Bot handlers, health, dual-poller kill largely unproven” | **Mostly true** for handlers + health lock/disclosure legs; **overstated** for dual-poller: lock holder is proven (`test_advisory_lock`), single-poller claim→send + kill/restart proven (`test_poller_integration`), in-memory unique claim proven (`test_idempotency`). Missing piece is **two concurrent `run_once` → one Telegram**, not “no dual-poller proof.” |
| Property suites (WS-062–064) as first-class strength | **Weak.** Crossing/move contracts are already encoded in ~26 table cases with exact-touch, prev-None, sticky/rearm, move day-key, `previous_close` derivation. Hypothesis adds little kill power unless aimed at mutants table tests miss — and WS-071 already proposes that cheaper as a doc. |
| Broad cov gate (WS-070) as Wave 1 close | **Premature.** Bot/handlers ≈0% measured; raising `--cov=` before WS-067/068 lands either fails CI or forces threshold theater (fail-under 60 with empty modules). |
| Wave size (20 WS) | **Too fat** for QUALITY-over-count constitution. ~8–10 implementation WS + 1 inventory + 1 proof pack is enough; merge reinventers. |

**Bottom line:** Pass 1 QUALITY should ship **handler + health + dual-eval characterization** tests, not a Hypothesis festival or cov-ratchet ceremony.

---

## 2. Ranked improvements (max 15)

Higher = fix the plan first (severity × impact ÷ effort).

| # | Improvement | Why |
|---|---|---|
| 1 | **Cut/defer WS-062–064 as separate landings** — fold any residual edges into existing `test_crossing.py` / `test_rules_move.py` as 2–3 parametrized cases | Suite already owns the contracts; Hypothesis deps + stateful flakiness violate “quality over count.” |
| 2 | **Merge WS-066 into `test_idempotency.py`** (add dual-snap-id / same-minute cases) — do not new FakeAlertLog module | `FakeAlertLog` + claim-twice already exists; only gap is “snap id 10 vs 11 → one key.” |
| 3 | **Collapse WS-078 into “keep green”** — do not open a WS | `test_domain_format.py` already asserts symbol, trigger, price, disclaimer, disclosure URL+title. |
| 4 | **Narrow WS-076** to poller-path residuals only (armed state after send fail / retry disarm doc) — drop re-simulating claim/retry | Covered by `test_idempotency` + `test_kill_restart_no_double_send`. |
| 5 | **Shrink WS-073** to missing boundaries only (09:29, exact 14:30 close policy, `force=True`, Fri UTC→Sat SLT) — do not rebuild market-hours suite | `test_market_hours_weekday_boundaries` already covers open, after-close, Saturday; `is_market_open` already extracted. |
| 6 | **Shrink WS-069** to **list-level** junk parse (2 good + 1 null-price → 2 snaps) — drop epoch/null-id that already pass | `test_announcement_with_no_ids_returns_none` + epoch-on-missing-`createdDate` already in adapters tests. |
| 7 | **Defer WS-070** until after handler + junk-list tests; keep sole fail-under on `chime.rules` | Premature gate blocks CORE/OPS for vanity %. |
| 8 | **Defer or delete WS-071** (mutation thought-experiment doc) | Doc-only mutant scorecards do not move bars 1–7; if kept, one commit max, no CI mutmut. |
| 9 | **Defer WS-072** latency harness | FINAL_REPORT + README already honest on claim→send vs poll-interval; harness risks false-green SLO theater (plan itself warns). |
| 10 | **Make WS-061 optional parallel** — must not gate handler/health WS | Inventory is fine; inventing `TEST_GAP_MATRIX` before filling real gaps is process padding. |
| 11 | **WS-065 acceptance: prove concurrent evaluate→claim**, not re-prove advisory lock alone | Lock already tested; acceptance must be two `Poller.run_once` + one `alert_log` / one send. |
| 12 | **WS-077 must pin lock-skip + disclosure-leg** — circuit-open already asserted | Only `last_tick_ok is False` on price circuit exists; PASS2 #2/#3 still unpinned. |
| 13 | **WS-074: equality + `created_at is None` + naive/aware** only — skip “Colombo wall times” sprawl until a bug appears | Before/after UTC already in `test_disclosure_rules.py`. |
| 14 | **WS-079 markers → OPS handoff**, not QUALITY Pass 1 | Taxonomy without CI jobs is docs churn; couple to OPS CI WS. |
| 15 | **Execution order rewrite:** handlers/health/dual-eval/tradeoff **before** properties/cov/mutation/latency | Current suggested order front-loads Hypothesis and buries PASS2 #12. |

---

## 3. Tests already covered that WS reinvent — cut/merge

| WS | Reinvents | Disposition |
|---|---|---|
| **WS-062** | `TestCrossedAboveBelow`, `TestExactTouch`, `test_prev_none_never_fires` | **Cut** as Hypothesis WS; optional 1–2 edge asserts in-file if mutant survivors appear. |
| **WS-063** | `TestStickyAndRecross`, `test_below_rearm_when_price_rises_back_above`, `filter_fireable` rearm exclusion | **Cut/merge** into one sequence table test if desired; no stateful Hypothesis. |
| **WS-064** | Entire `test_rules_move.py` (prev None, already-over, cross up/down, `move_fired_keys`, `previous_close` derivation, day key) | **Cut** — acceptance criteria already satisfied by suite. |
| **WS-066** | `FakeAlertLog` + `test_evaluate_claim_twice_sends_once` | **Merge** into idempotency file; add dual-snapshot-id case only. |
| **WS-076** (bulk) | `test_kill_and_restart_pending_send_once`, `test_kill_restart_no_double_send` | **Cut** duplicate claim/retry paths; keep only sticky-armed / disarm-on-retry **characterization** if CORE still gaps. |
| **WS-078** | `test_format_alert_message_*`, `test_disclosure_message_includes_url` | **Cut** WS entirely. |
| **WS-073** (partial) | `test_market_hours_weekday_boundaries` | **Shrink** to uncovered edges only. |
| **WS-069** (partial) | Happy trade row, null `createdDate`→epoch, empty id→None | **Shrink** to batch junk skip in `fetch_trade_summary` / row loop. |
| **WS-065** (partial overlap) | Single-poller crossing + sticky re-run in `test_poller_integration`; lock in `test_advisory_lock` | **Keep** but do not re-seed the single-poller happy path; only concurrent dual-poller. |

Not reinvented (genuine gaps): **WS-067, WS-068, WS-075, WS-077** (lock/disclosure health), **WS-065** concurrent claim, list-level junk in **WS-069**, equality/`created_at=None` in **WS-074**.

---

## 4. Coverage-gate expansions that are premature

| Proposal | Why premature |
|---|---|
| `--cov=chime.bot` fail-under (even ≥60) before WS-067/068 | Handlers untested → gate fails or forces meaningless import-only coverage. |
| `--cov=chime.adapters` fail-under before list-junk test | Current adapters tests hit normalize helpers only; HTTP fetch / per-row skip loop largely unmeasured — ratchet after WS-069 narrows. |
| Multi-package fail-under “ratchet plan” in same wave as first handler tests | Constitution: proof > ceremony. One gate (`chime.rules` ≥85) already green; expanding mid-wave fights CORE file owners on `pyproject.toml`. |
| Including `chime.poller` / `chime.storage` in fail-under | Heavy I/O branches; integration skips without DB → noisy CI; belongs Wave 2+ after markers (WS-079) + Neon job exist. |
| `chime.circuit` fail-under | **Least premature** of the set (`test_circuit.py` is strong) — still unnecessary Wave 1 work; optional measure-only snippet, no fail-under yet. |

**Pass 1 rule:** measure-only report OK; **no new `--cov-fail-under` packages** until handler + health + dual-eval tests land and percentages stabilize.

---

## 5. Property-test WS — high value vs theater

| WS | Rating | Rationale |
|---|---|---|
| **WS-062** (`crossed_*`) | **Theater** | Pure 3-arg predicates with exhaustive table + exact touch. Hypothesis will rediscover `prev < thr <= curr`. NaN/inf not in domain (floats from CSE/Pydantic). |
| **WS-063** (stateful rearm) | **Low / theater-risk** | One sticky + one rearm path already tested both sides. Stateful Hypothesis is flaky (plan admits) and slow for CI budget. Value only if mutation scorecard shows `<`/`<=` rearm survivors — then add **one** targeted example, not a strategy suite. |
| **WS-064** (daily move) | **Theater** | Acceptance bullets map 1:1 onto existing move tests. |
| **WS-075** (same-minute `event_key`) | **High value** (not Hypothesis — characterization) | Locks intentional dual-poller tradeoff so “fixes” cannot break dedupe; FINAL_REPORT deferred bullet. |
| **WS-066** dual-eval same key | **High value** (property-ish, not Hypothesis) | Encodes invariant “crossing identity independent of snapshot id”; CI-always. Prefer concrete dual-id examples over generators. |
| Any future Hypothesis on **disclosure datetime normalize** | **Medium** if CORE changes fail-closed/naive handling | Only after WS-074 examples exist; properties secondary. |

**Rule for QUALITY:** prefer **characterization + targeted examples** over Hypothesis until a mutant survives the current 58-case suite.

---

## 6. Top 5 QUALITY WS for Pass 1

Ordered for impact against CURRENT suite gaps (not WAVE1 suggested order):

| Rank | WS | Pass 1 role |
|---|---|---|
| **1** | **WS-068** (`/cancel` + `/unwatch`) | PASS2 #12 explicit hole; no test matches cancel/unwatch today. Highest UX regression risk. |
| **2** | **WS-067** (core bot handlers) | Same harness as #1; unlocks honest bot coverage later. Merge harness commits with WS-068 if single-writer on `tests/`. |
| **3** | **WS-077** (health honesty) | Pins Pass 2 lock-skip + disclosure-leg fixes; today only price-circuit `last_tick_ok` is asserted. |
| **4** | **WS-066** (narrowed: dual snap id → one claim, no DB) | Closes FINAL_REPORT “automated dual-poller kill without Neon” **honestly** via `event_key`; extend `test_idempotency.py`. |
| **5** | **WS-075** (same-minute rearm collision lock) | Prevents “smart” key redesign from breaking dual-poller dedupe; documents tradeoff. |

**Honorable next (Pass 1 stretch / Pass 2):** WS-065 (real dual `run_once` with DB), WS-074 equality/`created_at=None`, WS-069 list-junk only.

**Explicitly not Top 5:** WS-061, 062–064, 070–072, 078–080 (process/theater/reinvent/premature).

---

## Appendix — suite map (for orchestrators)

| Module | Cases | Owns |
|---|---|---|
| `test_crossing.py` | 16 | above/below, gap, sticky/rearm, exact touch, filters |
| `test_rules_move.py` | 10 | daily % crossing + day key + previous_close |
| `test_disclosure_rules.py` | 7 | fire/filter + created_at before/after |
| `test_idempotency.py` | 2 | in-memory UNIQUE claim + unsent retry |
| `test_poller_integration.py` | 2 | DB crossing→Telegram; kill/restart (skip w/o DB) |
| `test_advisory_lock.py` | 1 | real session lock blocks second holder (skip w/o DB) |
| `test_poller_resilience.py` | 3 | market hours sample; circuit health; disclosure HTTP survive |
| `test_adapters_normalize.py` | 5 | row map; epoch undated; empty id |
| `test_circuit.py` | 7 | breaker states |
| `test_bot_parse.py` | 3 | normalize_symbol + START ≤3 + NFA |
| `test_domain_format.py` | 2 | notify string contract (price + disclosure) |

Wave 1 QUALITY should **extend** this map, not clone it.
