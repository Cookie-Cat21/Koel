# Wave 1 — Quality / Test Lane (WS-061 … WS-080)

**Lane:** QUALITY (tests, harnesses, coverage proof — no product features)  
**Baseline:** Stage A `tests/` (12 modules, ~55 pytest cases; `koel.rules` 100% under `--cov=koel.rules`; bot handlers, dual-poller kill, and module coverage outside `rules.py` largely unproven)  
**Inputs:** [FINAL_REPORT.md](../../FINAL_REPORT.md) deferred list, [PASS2_AUDIT.md](../../PASS2_AUDIT.md) #5/#11/#12 + dual-poller residue, [PASS1_AUDIT.md](../../PASS1_AUDIT.md) latency/junk/crossing bars, `koel/rules.py` crossing + `created_at` filter  

Each workstream is planning-only. Commits listed are the intended implementation sequence when this wave executes — not done in the planning PR.

---

## WS-061 — Inventory missing tests vs quality bar

| Field | Content |
|---|---|
| **id** | WS-061 |
| **title** | Catalog coverage gaps vs bars 1–7 |
| **why** | Stage A proves `rules.py` heavily and leaves bot handlers, health, config/market hours, notify, and dual-poller kill paths under-tested (PASS2 #12; FINAL_REPORT deferred “automated dual-poller kill test”). Without an inventory, later WS duplicate or miss critical paths. |
| **acceptance criterion** | `docs/factory/TEST_GAP_MATRIX.md` exists: every `koel/*.py` (+ `adapters/`) mapped to existing `tests/test_*.py` or `UNCOVERED`; each quality bar row cites ≥1 gap or `covered`. Matrix checked into repo; no production code change. |
| **commits 1–5** | 1. Draft matrix skeleton from `koel/` file list. 2. Fill from `pytest --collect-only` + grep of test imports. 3. Map deferred FINAL_REPORT items → proposed WS ids. 4. Mark CI-skipped (`DATABASE_URL`) vs always-on. 5. Link matrix from this file’s index table. |
| **deps** | None (first QUALITY catalog commit) |
| **risk** | Low — doc-only; stale if code moves without refresh |

---

## WS-062 — Property tests for price crossing primitives

| Field | Content |
|---|---|
| **id** | WS-062 |
| **title** | Hypothesis properties for `crossed_above` / `crossed_below` |
| **why** | Table tests in `test_crossing.py` cover happy paths; float edges (exact threshold, negative prices, NaN/inf if ever present, equalities) are easy to miss. Properties encode the documented invariants in `rules.py` docstring. |
| **acceptance criterion** | `tests/test_crossing_properties.py` uses Hypothesis; properties hold: (a) `prev is None` ⇒ never True; (b) `crossed_above` iff `prev < thr <= curr`; (c) `crossed_below` iff `prev > thr >= curr`; (d) mutually exclusive for finite floats except impossible simultaneous equality cases. `pytest` green; Hypothesis in `[project.optional-dependencies] dev`. |
| **commits 1–5** | 1. Add `hypothesis` to dev deps. 2. Property file for primitives only. 3. Explicit examples for exact `thr` touch. 4. Reject/filter non-finite if domain forbids. 5. Wire `@settings` budget so CI stays &lt;2s. |
| **deps** | WS-061 (optional); none hard |
| **risk** | Low — pure functions; flaky if settings too loose or floats unbounded |

---

## WS-063 — Property tests for evaluate + rearm cycles

| Field | Content |
|---|---|
| **id** | WS-063 |
| **title** | Stateful properties: fire → disarm → rearm → recross |
| **why** | Unit tests cover sticky/rearm once each; property sequences catch illegal double-fire without rearm and missing rearm when price returns to the near side. |
| **acceptance criterion** | For random finite price sequences and thresholds, a simulated armed bit updated from `AlertEvent.set_armed` never emits two fireable events without an intervening rearm; `filter_fireable` never includes `trigger=="rearm"`. Proven by Hypothesis stateful or sequence test; documented in test docstring. |
| **commits 1–5** | 1. Extract tiny pure “apply events to armed” helper in test module (not prod). 2. Sequence generator for above rules. 3. Mirror for below. 4. Assert event_key uniqueness within a UTC minute+price when armed stays False. 5. Shrink examples checked into `# example` comments if valuable. |
| **deps** | WS-062 |
| **risk** | Medium — stateful Hypothesis can be slow/flaky; keep max_examples modest |

---

## WS-064 — Daily-move crossing properties

| Field | Content |
|---|---|
| **id** | WS-064 |
| **title** | Properties for `|pct|` crossing + first-obs baseline |
| **why** | PASS1 #9 / move crossing: first observation must not fire; fire only on `abs(prev_pct) < thr <= abs(pct)`; `move_fired_keys` suppresses same-day re-fire. Table tests exist; properties lock the contract. |
| **acceptance criterion** | Hypothesis tests: `prev_pct is None` ⇒ no move event; already-over-threshold first tick ⇒ no event; cross from below ⇒ one event with day-scoped `event_key`; key in `previous.move_fired_keys` ⇒ none. Covers derived pct from `previous_close` when `change_pct` is None. |
| **commits 1–5** | 1. Property file `test_move_properties.py`. 2. Baseline/None cases. 3. Cross-up and cross-down. 4. Idempotent same-day key. 5. previous_close derivation branch. |
| **deps** | WS-062 |
| **risk** | Low |

---

## WS-065 — Integration: dual-poller single claim (DB)

| Field | Content |
|---|---|
| **id** | WS-065 |
| **title** | Two pollers, one crossing → one Telegram |
| **why** | FINAL_REPORT deferred “automated dual-poller kill test”; PASS1 #5 / PASS2 #1 were about replica double-fire. `test_advisory_lock.py` proves lock holders but not end-to-end evaluate→claim under concurrent `run_once`. |
| **acceptance criterion** | With `DATABASE_URL`, test starts two `Poller`s (or two `Storage`+shared FakeCSE) forcing the same synthetic cross; assert exactly one `alert_log` row and FakeTelegram `send` count == 1. Marked `pytest.mark.integration`; skips cleanly without DB. |
| **commits 1–5** | 1. Shared FakeTelegram / FakeCSE fixtures in conftest or integration module. 2. Seed user+rule+baseline snapshot. 3. Concurrent `asyncio.gather(run_once, run_once)`. 4. Assert single claim + single send. 5. Document run recipe in TEST_GAP_MATRIX / README testing section. |
| **deps** | WS-061; sticky lock fix already in Stage A (PASS2 report) |
| **risk** | Medium — timing/flake on CI; needs real Postgres |

---

## WS-066 — Dual-poller without optional DB (in-process fake lock)

| Field | Content |
|---|---|
| **id** | WS-066 |
| **title** | CI-always dual-eval dedupe via event_key |
| **why** | FINAL_REPORT: automated dual-poller proof should not require Neon. Even without advisory lock, crossing-stable `event_key` must collapse two snapshot ids / two evaluators to one claim when Storage is mocked. |
| **acceptance criterion** | Unit/integration-style test with in-memory or AsyncMock `Storage.claim_alert` that enforces UNIQUE(rule_id, event_key): two evaluations with different `snapshot.id` but same minute+price → second claim returns conflict/False → one notify. Runs in default `pytest` (no `DATABASE_URL`). |
| **commits 1–5** | 1. Fake claim store dict. 2. Dual evaluate with snap ids 10 vs 11. 3. Assert one successful claim. 4. Same-minute identical price case documented. 5. Contrast test: different minute → two keys allowed. |
| **deps** | WS-065 (complements; can land first for CI) |
| **risk** | Low — does not prove real `pg_try_advisory_lock`; honest comment required |

---

## WS-067 — Bot handler unit tests: watch / alert / my\*

| Field | Content |
|---|---|
| **id** | WS-067 |
| **title** | Mocked Telegram handlers for core commands |
| **why** | `test_bot_parse.py` only covers `normalize_symbol` + START_TEXT. Handler wiring (storage calls, reply text, NFA framing) is untested. |
| **acceptance criterion** | `tests/test_bot_handlers.py` uses AsyncMock Update/Context + FakeStorage: `/watch`, `/alert … above|below|move|disclosure`, `/myalerts`, `/mywatchlist` each assert storage method called with expected args and reply contains disclaimer or honest disclosure copy where required. No network. |
| **commits 1–5** | 1. Handler test harness helpers. 2. `/watch` + `/mywatchlist`. 3. `/alert` variants + bad parse. 4. `/myalerts` formatting. 5. Assert START still ≤3 blocks via existing test kept green. |
| **deps** | WS-061 |
| **risk** | Low–medium — PTB Update shape can churn across versions |

---

## WS-068 — Bot handler unit tests: cancel / unwatch edges

| Field | Content |
|---|---|
| **id** | WS-068 |
| **title** | `/cancel` and `/unwatch` deactivation proofs |
| **why** | PASS2 #12 explicitly: no automated tests for cancel/unwatch; #7 UX when unwatch misses watchlist but deactivates rules. |
| **acceptance criterion** | Tests: `/cancel` → `deactivate_alert(user_id, id)` + confirmation; wrong id → kind error; `/unwatch` → remove_watch + `deactivate_rules_for_symbol`; orphan-rules path replies with deactivated count (or documents current behavior + locks it). Other user’s rules untouched (FakeStorage multi-user). |
| **commits 1–5** | 1. `/cancel` happy path. 2. `/cancel` not-found / not-owner. 3. `/unwatch` with watch row. 4. `/unwatch` orphan rules honesty. 5. Cross-user non-deactivation. |
| **deps** | WS-067 |
| **risk** | Low if handlers already fixed; may force small UX copy fix (still QUALITY-adjacent) |

---

## WS-069 — Adapter junk / partial-row fixtures

| Field | Content |
|---|---|
| **id** | WS-069 |
| **title** | Expand CSE normalize fixtures for junk rows |
| **why** | PASS1 #8 junk tradeSummary row; Stage A skips bad rows but fixture matrix is thin (`test_adapters_normalize.py` happy + null createdDate epoch). Need malformed price, string numbers, missing symbol, mixed good/bad list parsing if exposed. |
| **acceptance criterion** | Fixtures under `tests/fixtures/cse/` (JSON) + tests: 2 good + 1 null-price → 2 snapshots (or public parse helper returns 2); announcement null `createdDate` → epoch not `now`; empty id → None disclosure; oversized/partial dicts do not raise uncaught. |
| **commits 1–5** | 1. Add JSON fixtures from sample_responses trimmed. 2. Null/missing price cases. 3. Announcement undated + dated. 4. Batch/list parse test if API exists. 5. Assert structured log/skip side-effect via mock logger optional. |
| **deps** | WS-061 |
| **risk** | Low |

---

## WS-070 — Coverage gate beyond `rules.py`

| Field | Content |
|---|---|
| **id** | WS-070 |
| **title** | Broaden pytest-cov to critical packages |
| **why** | FINAL_REPORT quality bar only fails under `--cov=koel.rules`. Bot, poller, adapters, storage branches can regress at 0% measured coverage. |
| **acceptance criterion** | `pyproject.toml` / CI addopts cover at least `koel.rules`, `koel.bot` (parse+handlers once WS-067/068 land), `koel.adapters`, `koel.circuit` with documented fail-under thresholds (rules ≥85 kept; others start modest e.g. ≥60 and ratchet). `pytest` report shows no silent drop; term-missing reviewed for intentional excludes. |
| **commits 1–5** | 1. Measure current % per module (commit report snippet in docs). 2. Expand `--cov=` list. 3. Set initial fail-under. 4. Fill cheapest gaps blocking gate. 5. Document ratchet plan in TEST_GAP_MATRIX. |
| **deps** | WS-067, WS-069 (to make bot/adapter numbers honest) |
| **risk** | Medium — too-high threshold blocks unrelated CORE work; start modest |

---

## WS-071 — Mutation-test thought experiment (documented)

| Field | Content |
|---|---|
| **id** | WS-071 |
| **title** | Manual mutation scorecard for crossing + claim |
| **why** | 100% line coverage on `rules.py` does not prove assertion strength. A short mutmut/manual kill list shows which mutants today’s tests would miss (e.g. flip `<` to `<=` on rearm). |
| **acceptance criterion** | `docs/factory/MUTATION_THOUGHT_EXPERIMENT.md` lists ≥10 concrete mutants (operator flips in `crossed_*`, skip `prev is None`, drop `created_at` filter, weaken `event_key`, claim-before-disarm order) with **killed / survived / unknown** vs current suite; survivors become follow-up WS or explicit accepted risk. No requirement to run mutmut in CI yet. |
| **commits 1–5** | 1. Doc template + method. 2. Enumerate mutants from `rules.py`. 3. Enumerate poller claim/disarm order mutants. 4. Mark kill status by reasoning or one local mutmut run. 5. File survivor tickets → WS-062/063/068/075 as needed. |
| **deps** | WS-061; benefits from WS-062–064 |
| **risk** | Low — planning/doc; opinionated kill calls |

---

## WS-072 — Honest load / latency harness

| Field | Content |
|---|---|
| **id** | WS-072 |
| **title** | Latency harness that does not oversell CSE→TG |
| **why** | Quality bar 3 is **partial**: claim→send instrumented; CSE print→Telegram is poll-interval bounded (FINAL_REPORT). Need a harness that measures what we claim and refuses to assert p95&lt;5s end-to-end. |
| **acceptance criterion** | `scripts/latency_harness.py` or `tests/test_latency_harness.py` (marked optional/slow): records fake claim→send durations; prints p50/p95; documents that E2E lower bound ≥ `POLL_INTERVAL_SECONDS` simulation. README / harness `--help` states **not** a CSE→TG &lt;5s proof. CI may skip slow mark by default. |
| **commits 1–5** | 1. Harness stub + argparse. 2. Synthetic claim→send timing loop. 3. Poll-interval E2E simulation mode (honest fail if someone asserts &lt;5s E2E). 4. Sample output committed under `docs/factory/samples/`. 5. Link from FINAL_REPORT latency section note. |
| **deps** | WS-061 |
| **risk** | Low — must avoid false-green CI asserting impossible SLO |

---

## WS-073 — Market-hours / timezone edge tests

| Field | Content |
|---|---|
| **id** | WS-073 |
| **title** | Asia/Colombo session boundaries |
| **why** | Poller gates on 09:30–14:30 SLT weekdays; DST-less TZ still has UTC offset edges, weekends, exact open/close, and `force=True` bypass. Thin coverage today (`market_tz` only in resilience setup). |
| **acceptance criterion** | Unit tests (pure function or Poller helper): 09:29 skip, 09:30 run, 14:30 policy documented+tested, 14:31 skip; Sat/Sun skip; UTC Friday evening vs Colombo Saturday; `force=True` runs off-hours. No live clock dependency — inject `now`. |
| **commits 1–5** | 1. Extract or expose testable `is_market_open(now, tz)` if needed (minimal). 2. Open/close boundary table. 3. Weekend cases. 4. Force flag. 5. Parametrize IST-equivalent fixed datetimes. |
| **deps** | None hard |
| **risk** | Low–medium if logic is inlined in poller (small extract may be required) |

---

## WS-074 — Disclosure `created_at` / timezone compare cases

| Field | Content |
|---|---|
| **id** | WS-074 |
| **title** | Exhaustive disclosure gating datetime cases |
| **why** | PASS2 #4/#5: null `createdDate`→epoch, `created_at is None` fail-open residual, naive vs aware `TypeError`. Existing tests only before/after equal-ish UTC. |
| **acceptance criterion** | `test_disclosure_rules.py` (or sibling) covers: `published_at == created_at` ⇒ no fire; `created_at is None` ⇒ documented behavior (prefer fail-closed once CORE fixes; until then test locks current); naive vs aware ⇒ no crash (normalize or skip); epoch published_at never fires for normal rules; Colombo-local wall times converted consistently. |
| **commits 1–5** | 1. Equality boundary. 2. `created_at=None` case. 3. Naive/aware pair. 4. Epoch published_at. 5. Multi-rule same disclosure only matching symbol/type. |
| **deps** | WS-069 for adapter epoch; may pair with CORE fail-closed fix |
| **risk** | Low for tests; product fix may land in CORE lane |

---

## WS-075 — Same-minute rearm `event_key` collision test

| Field | Content |
|---|---|
| **id** | WS-075 |
| **title** | Lock intentional same-minute miss as known tradeoff |
| **why** | FINAL_REPORT deferred / PASS2 #11: rearm + recross same UTC minute + same print → identical `event_key` → silent miss. Must be an explicit test so a “fix” does not accidentally break dual-poller dedupe. |
| **acceptance criterion** | Test builds fire → rearm → recross with identical minute+price; documents expected claim conflict / zero second fire **or** (if CORE changes key) updates acceptance to exactly one new fire without breaking WS-066. Comment cites dual-poller tradeoff. |
| **commits 1–5** | 1. Reproduce collision in unit test. 2. Assert current behavior. 3. Cross-link FINAL_REPORT deferred bullet. 4. Optional xfail marker if redesign planned. 5. Guardrail test that dual-poller same-key still dedupes. |
| **deps** | WS-066 |
| **risk** | Low — characterization test; redesign is CORE |

---

## WS-076 — Idempotency + unsent retry under test expansion

| Field | Content |
|---|---|
| **id** | WS-076 |
| **title** | Claim conflict, send fail, retry success paths |
| **why** | `test_idempotency.py` exists; PASS2 #6 retry-success-without-disarm and unbounded unsent (deferred) need sharper scenarios so QUALITY lane detects CORE regressions. |
| **acceptance criterion** | Tests (unit with mocks): claim OK + send fail → armed stays True + `message_sent=False`; retry marks sent; second evaluate while sticky above ⇒ no new event_key; optional assert documenting disarm-on-retry gap until CORE fixes. No infinite retry loop in unit clock. |
| **commits 1–5** | 1. Fake claim/send failure. 2. Sticky no-refire. 3. Retry marks sent. 4. Document disarm gap assertion. 5. Cap/attempt counter placeholder test if field exists else skip. |
| **deps** | WS-065 or mock-only path |
| **risk** | Low |

---

## WS-077 — Health honesty regression suite

| Field | Content |
|---|---|
| **id** | WS-077 |
| **title** | `/health` 503 on lock-skip / disclosure-leg fail |
| **why** | PASS2 #2/#3: health lied on lock-starvation and disclosure-only failure. Stage A claims fixes — QUALITY must pin them so they cannot regress. |
| **acceptance criterion** | Tests force lock skip → health not OK; watchlist + disclosure fetch failures + OK prices → not OK (or documented degraded failing probe); circuit-open prices → not OK. Uses existing health helpers; no real HTTP required if `HealthState` is unit-tested. |
| **commits 1–5** | 1. Inventory current health tests. 2. Lock-skip case. 3. Disclosure-leg case. 4. Price circuit case refresh. 5. JSON shape assertions for error fields. |
| **deps** | WS-061 |
| **risk** | Low |

---

## WS-078 — Notify message contract tests

| Field | Content |
|---|---|
| **id** | WS-078 |
| **title** | Alert Telegram body: symbol, trigger, price, NFA, disclosure URL |
| **why** | MVP requires message contents; format helpers may be partially covered in `test_domain_format.py` but end notify path should lock string contract for price and disclosure events. |
| **acceptance criterion** | Given `AlertEvent` fixtures, rendered message includes symbol, trigger text, current price (price rules), disclosure URL+title (disclosure rules), and disclaimer snippet. Snapshot or substring asserts; no Telegram I/O. |
| **commits 1–5** | 1. Locate format/notify entrypoint. 2. Price-above message test. 3. Move message test. 4. Disclosure message + URL. 5. Disclaimer always present. |
| **deps** | None hard |
| **risk** | Low |

---

## WS-079 — Pytest markers, CI skip policy, slow/integration split

| Field | Content |
|---|---|
| **id** | WS-079 |
| **title** | Formalize `unit` / `integration` / `slow` markers |
| **why** | DB tests skip silently today; factory CI (OPS) needs a clear default (unit always) vs nightly/integration job. QUALITY owns the marker taxonomy. |
| **acceptance criterion** | `pytest.ini` / pyproject markers registered; all `DATABASE_URL` tests marked `integration`; latency harness `slow`; default addopts exclude `slow`; docs state how to run full suite with Neon. `pytest -m "not integration and not slow"` collects ≥ current always-on count. |
| **commits 1–5** | 1. Register markers. 2. Tag existing files. 3. Adjust addopts / CI snippet for OPS handoff. 4. Document in TEST_GAP_MATRIX. 5. Verify collect-only counts in proof block. |
| **deps** | WS-065, WS-072 |
| **risk** | Low |

---

## WS-080 — QUALITY wave verify + proof pack

| Field | Content |
|---|---|
| **id** | WS-080 |
| **title** | Close Wave 1 QUALITY with proof commands |
| **why** | Factory constitution: acceptance + proof (ruff/mypy/pytest). Wave needs a single rollup so orchestrators know QUALITY bar movement. |
| **acceptance criterion** | `docs/factory/WAVE1_QUALITY_REPORT.md` lists WS-061–079 status, proof command outputs, remaining survivors from mutation doc, and honest latency claim. `ruff` + `mypy` + default pytest green; integration noted as optional. |
| **commits 1–5** | 1. Report stub. 2. Paste proof commands. 3. Gap matrix delta vs WS-061. 4. Deferred leftovers → Wave 2 QUALITY ids. 5. Mark wave CONVERGE or CONTINUE. |
| **deps** | WS-061–079 (soft: report what landed) |
| **risk** | Low — process |

---

## Index (WS-061 … WS-080)

| ID | Title | Primary gap |
|---|---|---|
| WS-061 | Catalog coverage gaps vs bars 1–7 | Missing inventory |
| WS-062 | Hypothesis `crossed_*` properties | Crossing strength |
| WS-063 | Evaluate/rearm stateful properties | Crossing sequences |
| WS-064 | Daily-move crossing properties | Move semantics |
| WS-065 | Dual-poller DB integration | Replica single claim |
| WS-066 | Dual-eval event_key without DB | CI dual-poller |
| WS-067 | Bot handler mocks (core cmds) | Bot coverage |
| WS-068 | `/cancel` `/unwatch` handler tests | PASS2 #12 |
| WS-069 | Adapter junk fixtures | PASS1 #8 residue |
| WS-070 | Cov gate beyond rules.py | Measured gaps |
| WS-071 | Mutation thought experiment | Assertion quality |
| WS-072 | Honest latency harness | Bar 3 honesty |
| WS-073 | Colombo market-hours edges | Timezone |
| WS-074 | Disclosure created_at cases | PASS2 #4/#5 |
| WS-075 | Same-minute event_key tradeoff | FINAL deferred |
| WS-076 | Idempotency / unsent retry expand | PASS2 #6 |
| WS-077 | Health honesty regressions | PASS2 #2/#3 |
| WS-078 | Notify message contract | MVP message bar |
| WS-079 | Pytest marker / CI split | Ops handoff |
| WS-080 | Wave 1 QUALITY proof pack | Convergence |

## Suggested execution order

```
WS-061 → (WS-062 ∥ WS-069 ∥ WS-073 ∥ WS-078)
      → WS-063 → WS-064
      → WS-067 → WS-068
      → WS-066 → WS-065 → WS-075 → WS-076
      → WS-074 → WS-077
      → WS-070 → WS-071 → WS-072 → WS-079 → WS-080
```

Parallelism: up to 8 agents; keep `tests/conftest.py` and `pyproject.toml` single-writer per wave slice.
