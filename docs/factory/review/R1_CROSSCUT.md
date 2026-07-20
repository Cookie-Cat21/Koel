# R1 — Cross-lane dependency & sequencing review

**Role:** Planning reviewer (docs only)  
**Inputs:** [WAVE1_CORE](../workstreams/WAVE1_CORE.md), [WAVE1_DASH](../workstreams/WAVE1_DASH.md), [WAVE1_OPS](../workstreams/WAVE1_OPS.md), [WAVE1_QUALITY](../workstreams/WAVE1_QUALITY.md), [WAVE1_ADVERSARIAL](../workstreams/WAVE1_ADVERSARIAL.md), [INDEX](../workstreams/INDEX.md), [DASH_IA](../DASH_IA.md), [COMMIT_FACTORY](../COMMIT_FACTORY.md)  
**Scope:** Dependency graph, duplicate WS, Pass 1–3 sequencing, blockers before `web/` code, Epoch 1 board (≤16 WS)

---

## 1. Dependency graph issues

### Soft cycle: WS-003 ↔ WS-004

| Issue | Detail |
|---|---|
| Declared | WS-003 → WS-004 (`WAVE1_CORE` sketch: `WS-003 ─► WS-004`) |
| Contradiction | WS-003 **acceptance** requires “bulk feed **(plus name/symbol mapping)**” — that *is* WS-004 |
| Fix | Flip order: **WS-004 before or inside WS-003**. Treat mapping as a prerequisite commit of the bulk path, or split WS-003 AC so bulk can land with “unmapped rows skipped” and WS-004 unlocks attribution. Do not schedule both as independent parallel agents. |

### Contradictory dep: WS-066 vs WS-065

| Declared | Also says |
|---|---|
| WS-066 **deps** WS-065 | “complements; **can land first** for CI” |

**Fix:** Soften INDEX/QUALITY deps: WS-066 has **no hard dep** on WS-065. Order: WS-066 (always-on) → WS-065 (DB) → WS-075 (characterization of tradeoff).

### Missing cross-lane edges (declared “none” but real)

| Consumer | Missing dep | Why |
|---|---|---|
| WS-011 (CORE dual-poller test) | WS-056 (OPS CI DB pytest) and/or WS-042 | Proof only lands if CI has `DATABASE_URL`; otherwise stays local-only |
| WS-065 (QUALITY dual-poller DB) | WS-056, WS-079 | Needs markers + integration job; overlaps WS-011 |
| WS-030+ (DASH API) | WS-042 (compose) for local proof; schema already exists | Agents will invent Neon URLs without compose |
| WS-039 (DASH smoke) | WS-042, WS-043 | Smoke without seed/DB is flaky by design |
| WS-047 (OPS latency export) | Soft: CORE `koel/health` / notify ownership | Implementation touches CORE paths; lane says “OPS-compatible” but files are CORE |
| WS-031 POST watchlist | Product decision vs CSE | DASH wave: “does **not** call cse.lk”; [DASH_IA](../DASH_IA.md): “validates via CSE adapter”. **Must resolve before WS-031 mutations** — either Postgres-only + known symbols, or shared CORE validation helper (not browser→CSE) |
| WS-074 (QUALITY disclosure TZ) | WS-001, WS-002 | Tests should land *after* or *with* CORE fail-closed/parse fixes, else they pin wrong behavior then thrash |
| WS-075 (QUALITY event_key) | WS-008 (CORE) | Characterization vs fix — if CORE changes key in Epoch 1, QUALITY must not lock “miss” as permanent without linking WS-008 |
| WS-068 orphan `/unwatch` | WS-013 | QUALITY may force copy fix that is CORE WS-013 — same concern, two lanes |

### Wrong / fuzzy lane ownership

| WS | Claimed lane | Problem |
|---|---|---|
| WS-011 | CORE (`tests/`) | Same proof goal as QUALITY WS-065; OPS WS-056 owns enabling CI |
| WS-043 | OPS (`scripts/` / `koel seed`) | If entry is `python -m koel seed`, touches `koel/` → CORE ownership conflict |
| WS-047 | OPS | Likely edits `koel/health.py` or notify path — CORE files |
| WS-053 | OPS | Reads health contract; must not change payload (ok) but probe in `koel` package → CORE |
| WS-012 / WS-092 | CORE vs ADVERSARIAL “OPS/CORE” | Same fix; adversarial should not own `__main__.py` |
| WS-085, WS-100 | ADVERSARIAL → DASH | Correct as **probes**; must not ship parallel auth implementation — gate DASH WS-023/038/032 |
| QUALITY WS-068/074 | QUALITY | May require product code changes; fence: QUALITY files tests only, file CORE finding for WS-013/002 |

### Intra-DASH contract drift (blocks graph clarity)

Not a cycle, but two “sources of truth” disagree before any code:

| Topic | WAVE1_DASH | DASH_IA |
|---|---|---|
| Auth | Bearer `DASH_API_SECRET` + `telegram_id` header/query | `POST /api/v1/auth/demo` → signed session; future Telegram Login |
| API prefix | `/api/...` | `/api/v1/...` |
| History route | `/alerts/fires` + `GET /api/alerts/fires` | `/alerts/history` + `GET /api/v1/alerts/history` |
| Cancel | `PATCH` `{ active: false }` | `DELETE /alerts/{id}` |

**Fix before Pass 1 DASH code:** one ADR wins (recommend: align WAVE1_DASH shared-secret stub *or* DASH_IA demo-session — pick one; freeze paths in WS-024). Treat WS-022 as already partially done via `DASH_IA.md` but **reconcile**, do not re-author a third sitemap.

### Declared graphs that are fine

- CORE: `WS-001 → WS-003 → WS-018`; `WS-010 → WS-011` — OK once WS-003/004 fixed  
- OPS: WS-041 hub; compose → make → smoke — OK  
- DASH: WS-021 → {022,023,025} → 024 → 030 → UI — OK after auth/path freeze  
- QUALITY: property chain 062→063→064 OK; bot 067→068 OK  

No hard directed cycle among WS-001…WS-100 except the **WS-003↔WS-004 soft cycle**.

---

## 2. Duplicate WS across lanes

Treat ADVERSARIAL as **probe/finding**, not a second implementation ticket. Merge IDs in the board; do not run two agents on the same files.

### CORE fix ↔ ADVERSARIAL probe (same defect)

| Fix (CORE) | Probe (ADV) | Topic |
|---|---|---|
| WS-001 | WS-093 | Null `createdDate` / `dateOfAnnouncement` |
| WS-005 | WS-094 | Disclosure deep-link |
| WS-006 | WS-090 | Dead-letter / unbounded unsent |
| WS-008 | WS-089 | Same-minute `event_key` collision |
| WS-009 | WS-091 | Concurrent `/alert` IntegrityError |
| WS-010 | WS-084 | Advisory lock + `max_size=1` |
| WS-012 | WS-092 | `both` SIGTERM + `tick --force` |

**Rule:** Schedule CORE fix; ADV probe either (a) becomes the acceptance test inside the CORE WS, or (b) runs as VERIFY after the fix — never a parallel “implement” agent.

### CORE/QUALITY overlap (same proof)

| CORE | QUALITY | Topic |
|---|---|---|
| WS-008 | WS-075 | Same-minute event_key (fix vs characterize) |
| WS-011 | WS-065 (+ WS-066) | Dual-poller single claim |
| WS-019 | WS-064 | Daily-move edges |
| WS-001/002 | WS-074 | Disclosure datetime gating |
| WS-013 | WS-068 | Orphan `/unwatch` honesty |
| WS-007/006 | WS-076 | Unsent retry / disarm |

**Rule:** One owner for production change (CORE); QUALITY owns tests that prove it. Collapse dual-poller to **WS-066 (unit) + WS-065 or WS-011 (one DB integration)**, not three.

### OPS ↔ QUALITY handoff (not duplicate if split cleanly)

| OPS | QUALITY | Split |
|---|---|---|
| WS-056 | WS-065, WS-079 | OPS = workflow + Postgres service; QUALITY = markers + test body |
| WS-044 | WS-070 | OPS = CI artifact; QUALITY = cov package list / thresholds |
| WS-047 | WS-072 | OPS = export path; QUALITY = honest harness that refuses false E2E SLO |

### DASH doc / IA overlap

| WS | Status |
|---|---|
| WS-022 | Largely satisfied by existing `DASH_IA.md` — do not re-implement; reconcile conflicts only |
| WS-023 vs DASH_IA §4 | **Duplicate auth designs** — pick one before WS-025+ |
| WS-024 vs DASH_IA §3 | Duplicate API sketches — merge into one frozen contract |

### Near-duplicates inside one lane

| Pair | Note |
|---|---|
| WS-054 vs WS-055 | Make canonical; justfile optional mirror — fine sequentially, not parallel |
| WS-081 vs WS-073 | ADV boundary probe vs QUALITY market-hours tests — same `is_market_open` surface |
| WS-082 vs WS-073 | TZ honesty overlaps Colombo tests |

---

## 3. Recommended Pass 1 / Pass 2 / Pass 3 sequencing

Constraint: **≤8 agents per pass**, disjoint file ownership, lanes CORE + DASH + OPS + QUALITY (ADV as verify/findings, not 5th implement lane).

### Pass 1 — Foundation + correctness spine (8 agents)

Unblock CI/DX and ship highest-value CORE correctness without `web/` product code. Constitution amend only for DASH fence.

| Slot | WS | Lane | Primary paths (disjoint) |
|---|---|---|---|
| 1 | **WS-021** | DASH | `CLAUDE.md`, `RESOURCES.md` (docs) |
| 2 | **WS-041** | OPS | `.github/workflows/ci.yml` |
| 3 | **WS-042** | OPS | `docker-compose.yml`, `.env.example` |
| 4 | **WS-061** | QUALITY | `docs/factory/TEST_GAP_MATRIX.md` |
| 5 | **WS-001** | CORE | adapter disclosure date parse + tests |
| 6 | **WS-002** | CORE | `rules` disclosure `created_at` fail-closed |
| 7 | **WS-006** | CORE | dead-letter unsent path (+ subsume WS-090 probe) |
| 8 | **WS-012** | CORE | `__main__` SIGTERM + honest `tick` (+ subsume WS-092) |

**Deferred from CORE’s own “first 8” list:** WS-007, WS-009, WS-013, WS-017 → Pass 2 (file contention with Pass 1 adapters/rules/`__main__`).  
**Reconcile in Pass 1 docs (no extra agent if WS-021 owner does it):** DASH_IA vs WAVE1_DASH auth/paths → single ADR note under `docs/factory/` (feeds WS-023/024).

**Pass 1 VERIFY:** ADV probes WS-093, WS-090, WS-092 against landed CORE (doc findings only).

### Pass 2 — Alert spine + OPS CI depth + QUALITY properties (8 agents)

| Slot | WS | Lane | Notes |
|---|---|---|---|
| 1 | **WS-007** | CORE | Disarm on retry success |
| 2 | **WS-009** | CORE | IntegrityError / concurrent alert (+ WS-091) |
| 3 | **WS-010** | CORE | Pool / lock footgun (+ WS-084) |
| 4 | **WS-017** | CORE | Circuit-open ≠ empty disclosures |
| 5 | **WS-013** | CORE | Honest `/unwatch` orphans |
| 6 | **WS-048** | OPS | Migrate on ephemeral Postgres in CI |
| 7 | **WS-062** | QUALITY | Hypothesis crossing primitives |
| 8 | **WS-066** | QUALITY | Dual-eval event_key without DB |

**After Pass 2 (same epoch, next wave if needed):** WS-054 (Make), WS-043 (seed), WS-044 (coverage artifact) — do not exceed 8 in this pass.

**Pass 2 VERIFY:** WS-084, WS-091; start WS-075 characterization only if WS-008 not yet scheduled.

### Pass 3 — Dual-poller proof + DASH contract freeze + bot tests (8 agents)

Still **no** `web/` app code beyond optional empty dir; freeze API/auth docs so Pass 4 can scaffold.

| Slot | WS | Lane | Notes |
|---|---|---|---|
| 1 | **WS-011** *or* **WS-065** | CORE/QUALITY | **Pick one** DB dual-poller E2E; prefer WS-065 body + OPS enablement |
| 2 | **WS-056** | OPS | CI integration job (`DATABASE_URL`) — pairs with slot 1 |
| 3 | **WS-008** | CORE | Same-minute event_key redesign or documented tradeoff (+ WS-089/075) |
| 4 | **WS-023** | DASH | Auth ADR + `.env.example` keys (reconciled with DASH_IA) |
| 5 | **WS-024** | DASH | Frozen `DASH_API.md` / OpenAPI (reconcile routes) |
| 6 | **WS-067** | QUALITY | Bot handler tests (watch/alert/my*) |
| 7 | **WS-019** | CORE | Daily-move day boundary (feeds WS-064 later) |
| 8 | **WS-054** | OPS | Makefile one-command DX |

**Then (Pass 4+, not this board’s “first code” for dash UI):** WS-025 scaffold `web/` → WS-030 → WS-031…

### Sequencing diagram (cross-lane)

```
Pass 1:  WS-021 ‖ WS-041 ‖ WS-042 ‖ WS-061 ‖ WS-001 ‖ WS-002 ‖ WS-006 ‖ WS-012
           │         │         │
Pass 2:    │       WS-048    (compose ready)
           │         │
           └─► WS-023/024 (Pass 3) ─► WS-025+ (Pass 4, after blockers §4)
CORE spine: 001/002 → (003/004 later) ; 006/007 ; 009/010/012/013/017 ; 008 with QUALITY 066→065
OPS:        041 → 048 → 056 ; 042 → 054 → 057
QUALITY:    061 → 062 → 066 → 065/011 ; 067 → 068
```

---

## 4. Blockers before any `web/` code

Do **not** start WS-025 (scaffold) until all of the following are true:

| # | Blocker | Owning WS / action |
|---|---|---|
| B1 | Constitution fence amended (thin dash allowed + non-goals explicit) | **WS-021** landed |
| B2 | Single auth design frozen (shared-secret stub **xor** demo session — not both sketches) | Reconcile **WS-023** + [DASH_IA](../DASH_IA.md) §4 |
| B3 | Single API contract frozen (`/api` vs `/api/v1`; fires vs history; PATCH vs DELETE cancel) | **WS-024** + DASH_IA §3 merge |
| B4 | Symbol validation rule for dash mutations (Postgres-only vs CORE helper; **no** browser→cse.lk) | Product note in WS-024 / WS-031 risk |
| B5 | Local Postgres path exists for API integration proof | **WS-042** (and prefer **WS-043** seed before write APIs) |
| B6 | Auth/CSRF threat checklist for mutations | ADV **WS-085** + **WS-100** as **pre-flight checklist** (tests/checklist doc), not post-hoc |
| B7 | CI green on Python spine so dash PRs don’t land on broken main | **WS-041** at minimum |
| B8 | No parallel FastAPI service decision flipped mid-flight | WAVE1_DASH lock (“Next Route Handlers only”) stands unless constitution re-amended |

**Explicitly not blockers:** WS-003 bulk disclosures, WS-016 ticker normalize, full QUALITY cov ratchet (WS-070), justfile (WS-055).

**COMMIT_FACTORY §9 tension:** It says Pass 1 DASH = scaffold `web/` + read-only watchlist. This review **overrides that for sequencing**: Pass 1 = WS-021 docs only; first `web/` code = after B1–B7 (Pass 3 contract → Pass 4 scaffold). Avoids scaffolding against an unstable auth/API sketch.

---

## 5. Proposed Epoch 1 board (exactly 16 workstreams)

First implementation PR series — max 16. Prefer merge IDs; ADV probes folded into acceptance of the CORE twin.

| # | WS ID | Lane | Epoch 1 role |
|---|---|---|---|
| 1 | **WS-021** | DASH | Amend constitution for thin dash |
| 2 | **WS-041** | OPS | GitHub Actions CI (ruff/mypy/pytest) |
| 3 | **WS-042** | OPS | docker-compose Postgres |
| 4 | **WS-061** | QUALITY | Test gap matrix |
| 5 | **WS-001** | CORE | Parse `dateOfAnnouncement` (incl. WS-093 probe) |
| 6 | **WS-002** | CORE | Fail-closed missing `rule.created_at` |
| 7 | **WS-006** | CORE | Dead-letter unsent (incl. WS-090) |
| 8 | **WS-007** | CORE | Disarm on successful unsent retry |
| 9 | **WS-009** | CORE | Concurrent `/alert` IntegrityError (incl. WS-091) |
| 10 | **WS-010** | CORE | Advisory-lock pool footgun (incl. WS-084) |
| 11 | **WS-012** | CORE | `both` SIGTERM + honest `tick` (incl. WS-092) |
| 12 | **WS-017** | CORE | Disclosure circuit-open honesty |
| 13 | **WS-023** | DASH | Freeze v1 auth ADR |
| 14 | **WS-024** | DASH | Freeze Postgres→JSON API contract |
| 15 | **WS-066** | QUALITY | Dual-eval event_key CI proof |
| 16 | **WS-054** | OPS | Makefile one-command DX |

### Explicitly deferred out of Epoch 1 (next boards)

| Deferred | Why |
|---|---|
| WS-025…WS-040 | `web/` UI — after B1–B7; Epoch 2 |
| WS-003, WS-004, WS-018, WS-020 | Bulk disclosure — high risk; after spine |
| WS-008, WS-011/065, WS-056 | Dual-poller / event_key redesign — Pass 3+ |
| WS-013…WS-016, WS-019 | Bot UX / normalize / daily-move — Epoch 2 CORE |
| WS-043…WS-053, WS-055, WS-057…WS-060 | OPS depth after CI+compose+make |
| WS-062…WS-064, WS-067…WS-080 | QUALITY expansion after matrix + WS-066 |
| WS-081…WS-100 as implement | ADV = verify against Epoch 1 twins; leftover probes (083, 085–088, 095–100) → Epoch 2 VERIFY |

### Epoch 1 success bar

- CI runs on every PR (WS-041); local DB via compose (WS-042); `make` path (WS-054)  
- Disclosure miss/flood pair fixed (WS-001, WS-002); unsent path bounded + disarms (WS-006, WS-007)  
- Bot create race + lock pool + process lifecycle hardened (WS-009, WS-010, WS-012, WS-017)  
- Dash **docs** ready (WS-021, WS-023, WS-024); **zero** `web/` application commits required to close Epoch 1  
- QUALITY has inventory + always-on dual-eval proof (WS-061, WS-066)

---

## Reviewer actions for orchestrator

1. Edit CORE deps: **WS-004 before WS-003** (or merge mapping into WS-003 commits).  
2. Mark ADV twins WS-084/089–094 as **verify-only** against CORE IDs above.  
3. Collapse dual-poller to one DB WS (011 **xor** 065) + WS-066.  
4. Reconcile DASH_IA ↔ WAVE1_DASH before WS-025.  
5. Treat COMMIT_FACTORY §9 “Pass 1 DASH scaffold” as **Pass 4** relative to this board.
