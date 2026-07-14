# Chime now → 2K–3K proper commits

**Status:** Active near-term plan (supersedes 10K / 50M as *operating* targets)  
**KPI:** Plan A — `repo_score = min(proper_commits, clusters_closed)` (not raw `git rev-list`)  
**Baseline:** `lifetime_factory_score` ≈ **148**; Epoch 18 board **CLEAR**; factory at **NO_FUEL** until refill  
**Band:** grow Chime (and only Chime for now) toward **`repo_score` ∈ [2000, 3000]**

---

## 1. What Chime is right now

**One-liner:** CSE market **dashboard** (cake) + **Telegram push** when rules fire (cherry). See [DASH_CAKE_CHERRY.md](DASH_CAKE_CHERRY.md) and the full max roadmap [CHIME_MASTER_PLAN.md](CHIME_MASTER_PLAN.md).

**Not yet:** portfolio/tax, heavy screener, full TA terminal, payments (phased unlocks in the master plan).

| Layer | Status | What it is |
|---|---|---|
| **Telegram bot** | Shipped | Cherry — register, watch, alert, list, cancel, fire push |
| **Poller** | Shipped | Market hours (09:30–14:30 SLT, weekdays); CSE JSON → snapshots → rules → send |
| **Rule engine** | Shipped | Price, move, disclosure, activity, filing metrics (flags) |
| **Postgres** | Shipped | Stocks, snapshots, disclosures, users, watchlist, rules, alert_log (+ delivery leases) |
| **Health / ops** | Shipped | `/health`, structlog, migrate CLI, Docker Compose, CI |
| **Dashboard** | Shipped (primary) | Next.js Overview / Browse / Watchlist / Alerts / History / Symbol / Health |

**Stack:** Python (`python-telegram-bot`, APScheduler) + Postgres + Next.js/Tailwind/shadcn for the thin dash.

**Provenance:** Stage A through Stage B Pass 4 hardened; factory Epochs 2–18 burned most pre-seed polish. Score **148** proper factory points so far.

---

## 2. What it does (user loop)

```
/start → /watch COMB.N0000 → /alert COMB.N0000 above 120
                ↓
     poller (≈60s, market hours) pulls cse.lk
                ↓
     rules match crossing / move / disclosure
                ↓
     Telegram push (NFA framing) + alert_log
```

Optional: manage the same data in the thin web UI (Postgres only — **no cse.lk from `web/`**).

| Alert type | Fires when |
|---|---|
| `price_above` / `price_below` | Price crosses threshold (armed/disarmed; not spam while still above) |
| `daily_move` | Absolute daily % move crosses threshold (once per Colombo day) |
| `disclosure` | New CSE announcement for a watched symbol after the rule was created |

Hardening already in: advisory lock (single poller), claim-before-disarm, unsent retry + dead-letter, circuit breakers, rate-limited bot, NFA copy.

---

## 3. What it can be (and what it must not)

### A. Best version of itself (inside today’s fences)

Stay the CSE equivalent of “Tijori Alerts”: **push that works when nothing is open.**

| Horizon | Outcome |
|---|---|
| **Reliability** | Boring production: Telegram Login on dash, dual-poller proofs, DLQ runbooks, honest latency dashboards |
| **Scale of attention** | Bulk disclosure path for large watchlists; safer symbol UX; fewer false quiet periods |
| **Ops excellence** | One-command deploy story, richer `/health`, coverage ratchets, integration proofs |
| **Dash as remote** | Management remote for the bot — never a trading desk; mobile-first CRUD + symbol truth |
| **Data asset** | Keep every snapshot/disclosure — future research without changing v1 product shape |

This band alone can feed **most of a 2K–3K Chime `repo_score`** if every commit closes a real cluster (fix, test, ops, dash polish, bot UX) — not docs thrash.

### B. Needs a human constitution amendment (do not plan as default fuel)

| Expansion | Why it’s a different product |
|---|---|
| Portfolio / P&L | Holdings & performance — competitors already do this |
| Screener / TA charts | Discovery & analysis — kills “background watcher” focus |
| Payments / native app | Distribution & monetization — after push is undeniable |
| Ceyfi merge | Explicitly deferred in CLAUDE.md |

### C. What success looks like (product, not score)

A CSE investor sets alerts once, closes Telegram, and **still gets the ping**. The dash is for setup/inspection. Competitors keep needing an open browser; Chime does not.

---

## 4. 2K–3K plan (Chime-only for now)

### Target

| Metric | Now | Near-term band |
|---|---|---|
| `repo_score` / `lifetime_factory_score` | ~148 | **2,000 – 3,000** |
| Gap | — | **~1,850 – 2,850** proper commits that each close a cluster |
| Raw git count | ~231 | **Ignored as KPI** |

Midpoint operating goal: **`portfolio_target = 2500`** (celebrate 2K; stretch stop at 3K or honest `NO_FUEL`).

### Why this band is honest

- Factory docs already estimate Chime-only proper ceiling at **hundreds → low thousands**.
- Epoch 18 is CLEAR → need **new fence-legal fuel**, not empty commits.
- 2K–3K ≈ 12–20× current score — hard, but not industrial multi-repo fantasy.
- Sibling products deferred until this band is hit or Chime truly exhausts fences.

### Fuel map (where ~2K points come from)

Do **not** treat the stale WS INDEX “77 backlog” rows as 77 free commits — many DASH items are already shipped. Re-inventory before each epoch.

| Fuel class | Examples (fence-legal) | Rough proper-commit yield |
|---|---|---|
| **CORE correctness** | Bulk disclosures (WS-003/004), event_key edges, daily-move day boundary, orphan unwatch, symbol normalization | 80–200 |
| **Delivery / zero-loss** | Dual-poller kill tests, lease edge cases, DLQ ops proofs | 40–100 |
| **Bot UX** | `/start` ≤3 lines, armed-state in `/myalerts`, better errors, help surface | 40–80 |
| **Adapter resilience** | Schema-drift logs, partial bulk, deep-link verify | 40–80 |
| **Dash production** | Telegram Login (or ADR-approved auth), CSRF/a11y polish, empty/error states, smoke→e2e | 150–400 |
| **Quality ratchet** | Cov floors by module, property/integration tests, latency harness | 200–500 |
| **Ops / CI / runbooks** | Deploy checklist, richer health fields, compose profiles, Dependabot hygiene | 100–250 |
| **Epoch polish waves** | Small, bar-moving fixes only (anti-churn: no minors-only pads) | 200–400 |
| **Human fence expansion** | Only if product owner unlocks a slice (still no portfolio/screener/TA by default) | variable |

**Sum of honest classes ≈ 850–2,000+.** Hitting the **top of 2K–3K** needs sustained quality ratchet + dash production auth + several CORE backlogs — or a later fence expansion. Hitting **2K** is the credible first finish line.

### Cadence (same factory loop)

```
refill EPOCH_N board (≤8–16 fence-legal items)
  → ≤8 implementers, path-disjoint
  → make factory-verify
  → adversarial; fix REFUTE same wave
  → update_scoreboard; push
  → repeat until score≥2000 (hold) / ≥2500 (goal) / ≥3000 (stretch)
  → STOP on CLEAN×2 + NO_FUEL (honest)
```

Concurrency: prefer 8, hard max 16. One concern per commit. Farming banned.

### Milestones

| Score | Meaning |
|---|---|
| **500** | Factory loop proven past polish epochs; CORE/DASH fuel flowing |
| **1,000** | Half-ish to floor; production-auth or bulk-disclosure should be in flight |
| **2,000** | **Floor hit** — Chime is a serious hardened node |
| **2,500** | Operating goal |
| **3,000** | Stretch ceiling without fence expansion; then STOP or amend constitution |

### Explicit non-goals for this band

- No raw-commit bots / `--allow-empty` / whitespace farms  
- No splitting one fix into N commits to “make 2K”  
- No inventing WS rows without product need  
- No portfolio / screener / TA / payments / native app  
- No chasing 10K/50M while this band is open  

---

## 5. Immediate next actions

| ID | Action | Owner |
|---|---|---|
| H-01 | Lock this doc as active scale plan; retarget scoreboard to **2500** | Done in this change |
| H-02 | Re-inventory WS INDEX vs shipped code → true OPEN clusters only | Next factory session |
| H-03 | `make factory-refill` → Epoch 19 board from true backlog (CORE + dash auth + tests) | Next session |
| H-04 | Prefer bulk disclosure + Telegram Login + dual-poller proof as first big clusters | Orchestrator |
| H-05 | Sibling product enrollment | **Deferred** until ≥2K or honest Chime `NO_FUEL` |

---

## 6. One-line answers

| Question | Answer |
|---|---|
| What is Chime? | CSE Telegram alert watcher (thin dash secondary). |
| What does it do? | Watch symbols; fire on price/move/disclosure; push on Telegram. |
| What can it be? | The default “ping me when CSE moves” tool — reliable, polite, not a terminal. |
| What are we scoring toward? | **2K–3K proper factory score on Chime**, midpoint **2500**. |
