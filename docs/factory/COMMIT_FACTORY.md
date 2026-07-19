# Quiverly — Commit Factory Master Plan

**Status:** Planning reviewed (Wave R1) — see [review/IMPROVEMENTS.md](review/IMPROVEMENTS.md)  
**Branch intent:** Quality-gated agentic improvement of Quiverly only (Ceyfi merge deferred)  
**Co-authors:** Human product owner + Cursor Cloud Agents  

## 0. Constitution (overrides everything)

Read and obey [CLAUDE.md](../CLAUDE.md). Hard fences:

- Quality over count. A commit that exists only to inflate history is **rejected**.
- One concern per commit; disjoint files across concurrent agents.
- Compliance: NFA framing, polite cse.lk rate limits, never scrape competitors.
- Dashboard reads **Postgres / Quiverly API only** — no second unbounded cse.lk client from `web/`.
- Concurrency: **8 preferred, hard max 16**. “100 workstreams” = catalog in waves — never 100 simultaneous processes.
- Convergence: two consecutive passes with zero findings above **minor** → STOP that lane.
- **Also STOP** if a pass produces only minor fixes with no quality-bar movement (no infinite minor churn).
- Adversarial **REFUTE** ⇒ revert or fix in the **same pass** before scoring.

### Defaults locked for this factory

| Decision | Choice |
|---|---|
| Dashboard | **Unlock denser CSE dash** (Overview / Browse / Watchlist / Alerts / Symbol / Health) per [CHIME_MASTER_PLAN.md](CHIME_MASTER_PLAN.md). Portfolio/tax/heavy screener/TA = phased unlocks only after cake+cherry are excellent. |
| Dash data path | Postgres-backed API; CSE traffic stays in poller/bot adapters |
| Auth (v1) | Server-side session after verified identity — **not** client-supplied `telegram_id` + shared secret alone |
| PR style | One long-lived factory PR per epoch; pass reports in `docs/factory/` |
| Intensity | Aggressive throughput of *proper* commits; gates mandatory |
| Human role | Approve constitution/fence changes; orchestrator picks top findings within fences |
| Merge with Ceyfi | **Deferred** |
| Epoch 1 board | Fixed 16 WS in [review/IMPROVEMENTS.md](review/IMPROVEMENTS.md) — no feature flood |

## 1. What a “proper commit” is

A commit is accepted only if all are true:

1. **One concern** stated in the subject (imperative, ≤72 chars).
2. **Acceptance criterion** written before implementation (in the pass plan).
3. **Proof** attached in the pass report: command output for `ruff`, `mypy`, `pytest` (and dash smoke when relevant).
4. **No fence violation** of CLAUDE.md / this file.
5. **Adversarial reviewer** did not refute it with a concrete failure scenario — or the fix landed in the same pass.

### Banned

- Whitespace / import-sort-only / rename-only commits for count  
- README thrash without product change  
- Splitting one logical fix into N commits to farm the graph  
- Manufacturing audit findings to fill `MAX_PASSES`  
- Touching competitor sites / adding portfolio-P&L / screener / TA charts  

### Commit trailer (when human opts in)

```
Co-authored-by: <name> <email>
```

## 2. Quality bar (score every pass; claim only with proof)

| # | Bar | Pass means |
|---|---|---|
| 1 | Alert correctness | Crossing semantics; unit tests for baseline, gap, re-arm, missing prev |
| 2 | Zero dup / zero loss | Advisory lock + claim-before-disarm + unsent retry; kill-restart proof |
| 3 | Latency | claim→send instrumented; CSE→TG = poll-interval (honest); dash TTFB budget TBD |
| 4 | Resilience | Single CSE endpoint failure never kills the loop |
| 5 | Ops | structlog, health, graceful shutdown, secrets from env, one-command run |
| 6 | Code quality | ruff + mypy clean, pytest green, rules cov ≥85% |
| 7 | Bot UX | One round-trip commands; kind errors; /start ≤3 lines |
| 8 | Dash UX (new) | Watchlist/alerts usable on mobile+desktop; brand-readable first viewport; no fake trading terminal |

## 3. Lanes

| Lane | Path ownership | Goal |
|---|---|---|
| **CORE** | `chime/`, `db/`, `tests/` (non-UI) | Alert spine excellence |
| **DASH** | `web/` (new), dash API surface | Thin management dashboard |
| **OPS** | `.github/`, Docker, DX scripts, factory docs | CI, local one-command, observability |

Parallelize **within** a lane; never merge conflicting files across agents in one wave.

## 4. Pass loop (implementation epochs — after planning)

```
AUDIT → PLAN → IMPLEMENT (≤8 agents) → VERIFY → ADVERSARIAL REVIEW → REPORT
MAX_PASSES = 100 per lane epoch
STOP if 2 consecutive passes have 0 findings > minor
STOP if pass is minors-only with no quality-bar movement (anti-churn)
Each implementer declares OWNED_FILES; path intersect across agents ⇒ fail the wave
Verify proof must cite HEAD SHA at verify time
```

## 5. Planning phase (done)

- Catalog **100 planning workstreams** (WS-001…WS-100) — see [workstreams/INDEX.md](workstreams/INDEX.md).  
- Executed by **8 concurrent planning subagents** (CORE, DASH, OPS, QUALITY, ADVERSARIAL, IA, prompts, metrics) — concurrency capped; not 100 parallel processes.  
- Supporting docs: [DASH_IA.md](DASH_IA.md), [ORCHESTRATOR_PROMPTS.md](ORCHESTRATOR_PROMPTS.md), [METRICS.md](METRICS.md).  
- Planning PR: constitution amendment for thin dashboard + factory docs only (no feature flood).

## 6. Throughput model (honest)

```
proper_commits ≈ Σ over passes (accepted findings fixed)
```

Not `MAX_PASSES × agents`. Rejected / refuted work does not count.  
Aspiration: sustain a high rate of proper commits across many Cloud Agent sessions — not a fake trillion.

## 7. Dashboard fence amendment (summary)

Allowed in DASH lane:

- Watchlist CRUD (mirrors bot)  
- Alert CRUD + fire history  
- Symbol detail: last price, recent snapshots sparkline, disclosures  
- Health / last poll status (ops)  

Still forbidden: portfolio P&L, tax, screener, TA charts, payments, native app.

Stack when implementing: **Next.js + Tailwind + shadcn/ui** only; free/MIT components; log in `THIRD_PARTY.md`.

## 8. Document index

| Doc | Purpose |
|---|---|
| [COMMIT_FACTORY.md](COMMIT_FACTORY.md) | This master plan |
| [ORCHESTRATOR_PROMPTS.md](ORCHESTRATOR_PROMPTS.md) | Copy-paste Cloud Agent prompts |
| [METRICS.md](METRICS.md) | Proper-commit taxonomy, scorecards, KPIs |
| [PORTFOLIO_PLAN.md](PORTFOLIO_PLAN.md) | Multi-repo KPI A; Quiverly is node 1 |
| [CHIME_HORIZON.md](CHIME_HORIZON.md) | What Quiverly is / does / can be; active 2K–3K score band |
| [DASH_COMPONENT_FILTER.md](DASH_COMPONENT_FILTER.md) | Tremor/bookmark kits → fence + license filter |
| [DASH_IA.md](DASH_IA.md) | Thin dashboard IA + API sketch |
| [workstreams/INDEX.md](workstreams/INDEX.md) | WS-001…WS-100 catalog |
| [workstreams/WAVE*.md](workstreams/) | Per-wave planning outputs |
| [../CLAUDE.md](../CLAUDE.md) | Product constitution |
| [../FINAL_REPORT.md](../FINAL_REPORT.md) | Stage A baseline |

## 9. First implementation epoch (after plan merges)

1. Amend CLAUDE.md dashboard section (if not in this PR).  
2. Pass 1 CORE: top deferred items from FINAL_REPORT.  
3. Pass 1 DASH: scaffold `web/` + read-only watchlist from API.  
4. Pass 1 OPS: CI workflow running ruff/mypy/pytest.  
