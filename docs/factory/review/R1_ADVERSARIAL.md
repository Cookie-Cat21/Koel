# R1 — Meta-review: WAVE1_ADVERSARIAL catalog (WS-081…WS-100)

**Reviewer role:** Adversarial plan reviewer of the adversarial catalog itself  
**Inputs:** [WAVE1_ADVERSARIAL.md](../workstreams/WAVE1_ADVERSARIAL.md), [PASS1_AUDIT.md](../../PASS1_AUDIT.md), [PASS2_AUDIT.md](../../PASS2_AUDIT.md), [PASS4_AUDIT.md](../../PASS4_AUDIT.md), [FINAL_REPORT.md](../../FINAL_REPORT.md), [COMMIT_FACTORY.md](../COMMIT_FACTORY.md), [INDEX.md](../workstreams/INDEX.md) / [WAVE1_CORE.md](../workstreams/WAVE1_CORE.md)  
**Baseline claimed:** Stage A CONVERGE (Pass 3+4, zero findings above minor)

---

## 1. Verdict

**Fear-padded probe catalog with a real core — not a clean probe catalog.**

Rough split of the 20 rows:

| Bucket | Count | IDs |
|---|---|---|
| Real unknown / underexercised probes | ~7 | 081, 083, 086, 093*, 094, 096, 099 |
| Known Stage A deferred defects already owned by CORE WS | ~7 | 084≡010, 089≡008, 090≡006, 091≡009, 092≡012, 093≡001, 094≡005 |
| Already closed by Stage B → regression-only | ~4 | 088 (same-DB lock), 089 (accepted tradeoff), 098 (gap units), 082 (mostly) |
| Premature / no surface / checklist theater | ~5 | 085, 087, 095, 097, 100 |

\*093 is both a real product risk and a duplicate of CORE WS-001.

The catalog’s stated contract — *“do not implement; reproduce or refute”* — is violated by rows that FINAL_REPORT and Pass 1/2 already **proved** as defects (`force or True`, unbounded unsent, IntegrityError, sticky-lock `max_size=1` footgun). Re-labeling known bugs as “probes” is audit theater: it burns an adversarial pass to rediscover what CORE Pass 1 should just fix.

Worse: **INDEX already assigns the same deferred work to CORE WS-001…012 and QUALITY WS-073/075/076/077.** Scheduling WS-084/089/090/091/092/093/094 as adversarial workstreams doubles the factory graph and invites two agents to “probe” and “implement” the same concern — banned by COMMIT_FACTORY concurrency/ownership rules.

Pass 4 CONVERGE means “no new finding above minor under code review,” not “every deferred medium is imaginary.” A honest adversarial wave would: (a) regression-lock Stage B closes, (b) hand known deferred to CORE as fix commits, (c) run only probes that can still *surprise*. This catalog does not make that cut.

**Score:** ~35% fear / padding / premature DASH, ~35% duplicate backlog, ~30% worth running as probes.

---

## 2. Already closed by Stage B → regression-only (not new WS)

Do **not** schedule these as fresh adversarial workstreams. Fold into QUALITY regression / CI; promote only if a probe *fails*.

| ID | Why closed / accepted | What remains |
|---|---|---|
| **WS-088** (same-DB dual poller) | Pass 2 fixed sticky `_lock_conn`; Pass 4 verified lock hold through `run_once`/`finally`/`close()`. Crossing-stable `event_key` + claim dedupe. | Regression: `tests/test_advisory_lock.py` (needs `DATABASE_URL`). Multi-bot same-token / split-DB brain → OPS runbook, not CORE probe theater. |
| **WS-089** | FINAL_REPORT deferred as **intentional** dual-poller tradeoff; Pass 2 #11 already documented. CORE WS-008 + QUALITY WS-075 own any decision to change keys. | One named regression test asserting current behavior + comment pointing at the tradeoff. Not an open “fail if collision.” |
| **WS-098** | Pass 1 **refuted** overnight-gap scare; `TestGapOpen` / missing-prev semantics are Stage A strength. | Optional E2E through `run_once`+claim if QUALITY wants depth — not WS-098 as if the bug were unexplored. |
| **WS-082** (happy path) | Market gate + disclosure date window already use `Asia/Colombo` / `settings.market_tz` (Pass 1 #13 hold). | Keep a negative-control test (`MARKET_TZ=Europe/London` shifts window). Do not re-open as research. |
| **WS-093** (epoch fail-closed half) | Pass 2/4 closed the `published_at=now()` flood by mapping null `createdDate` → epoch fail-closed. | Residual is **product miss** via ignored `dateOfAnnouncement` — that is CORE **WS-001**, not a mystery probe. |

Also **not probes** — already proven open defects (fix commits, not “reproduce or refute”):

| ID | Proof | Owner |
|---|---|---|
| **WS-092** | Pass 1 #15/#16, Pass 2 #10, live `__main__.py`: `force=args.force or True` | CORE **WS-012** |
| **WS-090** | Pass 1 #17, Pass 2 #8, FINAL_REPORT deferred | CORE **WS-006** |
| **WS-091** | Pass 1 #14, Pass 2 #9, FINAL_REPORT deferred | CORE **WS-009** |
| **WS-084** | FINAL_REPORT deferred; sticky lock *creates* the footgun | CORE **WS-010** |

Calling these “adversarial probes” after CONVERGE is dishonest. The failure scenario is already in the audit trail.

---

## 3. Probes that lack a feasible probe method

| ID | Defect | Feasible? |
|---|---|---|
| **WS-085** | Dash auth bypass | **No.** `web/` does not exist. “Once API exists” is a DASH threat-model checklist (belongs under WS-023 / DASH_IA), not a Stage A probe. |
| **WS-100** | Session fixation / CSRF | **No.** Same. Companion to 085; zero mutating routes to POST. |
| **WS-087** | Host/DB/CSE clock skew | **Weak.** ±5m injection on rule timestamps is a unit assertion (“don’t gate on wall clock”); “check Neon `now()` vs app” is an ops script, not a pass/fail failure scenario. CSE exchange-clock disagreement is not controllable. Pass criterion mixes three systems into mush. |
| **WS-097** | CSE holidays / special sessions | **Not a probe unless product claims holiday awareness.** CLAUDE.md: weekdays 09:30–14:30. Weekend skip is already testable; holiday calendar is a product decision / accepted pollution. “Document a public calendar” ≠ reproduce a defect. Special Saturday sessions are rare folklore without a cited CSE source in-repo. |
| **WS-095** | Health bind / payload recon | **Checklist, not probe.** Defaults are loopback; pass/fail is doc review. “0–2 commits” admits padding. |
| **WS-094** (as written) | Deep-link UX | **Partially.** Fetch/HEAD of constructed URLs is feasible; “open in browser / confirm filing visible” is flaky against SPA/hash routing and duplicates CORE WS-005. Needs a concrete HTTP assertion or CDN `filePath` fallback test — not vibes. |
| **WS-081** (live half) | Inclusive open/close vs CSE prints | Unit boundaries are feasible; “frozen CSE fixture for whether tradeSummary updates at 14:30:00” needs a **recorded** sample. Without that fixture, live half is blocked / cargo-cult. |
| **WS-099** | Neon drops lock connection mid-tick | Feasible only with real Postgres/Neon and connection murder; flaky in CI. Method exists but is **integration-hard** — mark `slow`/`integration`, don’t pretend unit purity. |

---

## 4. Ranked improvements (max 15)

1. **Partition the catalog into four lists** before any epoch: (A) Stage B regression suite, (B) known deferred → CORE fix commits, (C) true surprise probes, (D) DASH security appendix. Delete the fiction that all 20 are the same animal.
2. **Kill duplicate IDs.** Map 084→010, 089→008, 090→006, 091→009, 092→012, 093→001, 094→005, 088→011/QUALITY-065. Adversarial lane keeps only non-overlapping rows.
3. **Do not “probe” `force or True`.** Schedule WS-012 as the first CORE commit; adversarial review verifies the fix — classic AUDIT→IMPLEMENT, not rediscovery.
4. **Demote WS-085/100** to [DASH_IA.md](../DASH_IA.md) / WS-023 acceptance gates: “no write API ships without session + CSRF tests.” Zero ADVERSARIAL WS until `web/` scaffold lands.
5. **Kill WS-097 as a workstream.** Record weekend tests under QUALITY WS-073; holiday behavior = one sentence in CLAUDE/README (“poll on weekdays; holidays may no-op”).
6. **Shrink WS-087** to a single code invariant: disclosure/price rules must not use host wall-clock windows for claim eligibility. Drop NTP sermon as a WS.
7. **Demote WS-095** to OPS release checklist (HEALTH_HOST warning already Pass 1 territory).
8. **Add severity × likelihood scores** (Pass 1 style). Flat “1–5 commits if fix” without score lets holiday folklore sit next to lock blackout.
9. **Require proof artifacts on probe methods:** mock call counts (083/096), HTML body fixtures in `docs/sample_responses/` (086), recorded boundary ticks (081), Neon reconnect timing bound (099). No artifact → blocked, not “pass.”
10. **Cap first adversarial epoch at ≤5 true probes** plus regression pack. COMMIT_FACTORY: quality over count; 20 parallel “investigations” is catalog cosplay.
11. **WS-089 pass criterion is already met** by FINAL_REPORT documentation of accepted tradeoff. Close or convert to QUALITY characterization test — stop listing as open failure.
12. **WS-083 pass criterion needs a number:** e.g. global TokenBucket / single send queue; tick wall time &lt; N; advisory lock hold &lt; M; ≤1 RetryAfter sleep in-flight. “Back off globally” is hand-wavy.
13. **WS-096 needs polite budget:** max outbound HTTP per recovering tick as function of watchlist size / `fail_max`. Compliance fence in CLAUDE.md demands this.
14. **WS-093:** stop framing fail-closed as the bug. The bug is silent miss when `dateOfAnnouncement` is present — align wording with CORE WS-001 acceptance (parse fallback **or** metrics `dropped_undated`).
15. **Ban browser-automation theater** in probe methods unless verification skill/tools are in-scope. Prefer `httpx` assertions against public cse.lk only (compliance).

---

## 5. Top 5 probes worth running in the first implementation epoch

Only rows that can still yield a **new** finding or harden a deferred risk that CORE might under-test. Prefer running **after** or **alongside** the matching CORE fix where noted — not instead of deleting the duplicate WS.

| Rank | ID | Why |
|---|---|---|
| 1 | **WS-083** RetryAfter storm | Real production path (`notify.send_message` sleeps once per call). Burst at open can hold the advisory lock and starve ticks. **Not** duplicated as a CORE WS. Highest surprise potential. |
| 2 | **WS-099** Lock connection drop mid-tick | Sticky-lock design’s residual blackout mode. Pass 4 verified happy path only. Neon blips are plausible. Pair with CORE WS-010/011. |
| 3 | **WS-086** CSE HTML-as-200 | Resilience bar says single endpoint failure must not kill the loop; HTML 200 / empty body is a distinct failure mode from junk JSON rows already tested. Fixture-cheap. |
| 4 | **WS-096** Circuit half-open stampede | Compliance-critical (polite cse.lk). Circuit exists; recovery fan-out under large watchlist is underexercised. Measurable with mocked transport. |
| 5 | **WS-081** Market inclusive boundary | Small surface, high ops confusion risk; unit-lock `09:29:59`…`14:30:01` immediately. Defer live CSE correlation until a sample exists — still worth the unit half. |

**Explicitly not in top 5:** 090/091/092/084/093/094 — already owned by CORE backlog; implement there, adversarially review the *diff*. 085/100 — no surface. 098/089/088 — regression only.

---

## 6. Kill / defer list

### Kill (remove from ADVERSARIAL wave or merge away)

| ID | Action |
|---|---|
| **WS-085** | Kill as ADVERSARIAL WS. Move to DASH auth acceptance. |
| **WS-100** | Kill as ADVERSARIAL WS. Same. |
| **WS-097** | Kill. Weekend coverage → QUALITY; holiday = accepted non-goal unless constitution changes. |
| **WS-095** | Kill as WS. One OPS checklist bullet. |
| **WS-089** | Kill as open probe. Characterization/regression only; any key change = CORE WS-008. |
| **WS-098** | Kill as WS. Gap/missing-prev already Stage A; optional QUALITY E2E. |

### Defer / rehome (do not run as “probes” in epoch 1)

| ID | Action |
|---|---|
| **WS-090** | Defer to CORE **WS-006** implement. |
| **WS-091** | Defer to CORE **WS-009** implement. |
| **WS-092** | Defer to CORE **WS-012** implement (proven bug). |
| **WS-084** | Defer to CORE **WS-010** implement + test. |
| **WS-093** | Defer to CORE **WS-001** implement. |
| **WS-094** | Defer to CORE **WS-005**; adversarial may spot-check URLs after fix. |
| **WS-088** | Defer same-DB half to QUALITY/CI regression; multi-bot token → OPS runbook. |
| **WS-082** | Defer to QUALITY WS-073 negative-control; not a research wave. |
| **WS-087** | Defer indefinitely or collapse to one unit invariant; not epoch-1. |

### Keep (true adversarial lane, epoch 1)

**WS-083, WS-086, WS-096, WS-081 (unit), WS-099 (integration).**

---

## Bottom line

WAVE1_ADVERSARIAL reads like a brainstorm that was numbered to fill WS-081–100. Pass 1–4 already did the hard adversarial work; this catalog mostly **replays deferred leftovers and invents DASH nightmares**, while under-weighting the few scenarios Stage B never load-tested (RetryAfter under lock, HTML 200, half-open stampede, lock-drop blackout).

Ruthless factory move: **cut the wave to five probes**, **delete the duplicates**, and **stop calling known bugs investigations**.

