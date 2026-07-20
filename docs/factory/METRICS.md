# Quiverly — Factory Metrics

**Purpose:** Define how we measure *proper commits* and factory health.  
**Authority:** Subordinate to [COMMIT_FACTORY.md](COMMIT_FACTORY.md) and [CLAUDE.md](../CLAUDE.md).  
**Rule:** Counts without proof do not move the score.

---

## 1. Commit taxonomy (message tags)

Prefix the subject with exactly one primary tag. Optional second tag only when the concern truly spans two lanes (rare; prefer splitting).

| Tag | Counts as proper? | Use when |
|---|---|---|
| `feat` | Yes | User-visible behavior in bot or core alert spine |
| `fix` | Yes | Bug/correctness fix with a failing case before or a regression test after |
| `test` | Yes | Coverage or proof that raises a quality-bar item (not empty stubs) |
| `ops` | Yes | CI, Docker, health, logging, secrets, one-command run |
| `docs` | **Only if** | Docs unblock a gate or correct a constitution/fence error — not narrative thrash |
| `dash` | Yes | Thin web dashboard work inside the DASH fence |

### Examples (good)

```
feat(bot): add /alert SYMBOL move PERCENT parser
fix(rules): re-arm price-above after gap fill
test(rules): cover missing previous snapshot
ops(ci): run ruff mypy pytest on PR
docs(factory): define proper-commit scorecard
dash(web): read-only watchlist page from API
```

### Examples (bad — do not ship for score)

```
docs: polish README wording
chore: sort imports
refactor: rename helpers for clarity
feat: split alert fix into 4 tiny commits
```

Format: `<tag>(scope): <imperative ≤72 chars>` — one concern, acceptance criterion already in the pass plan.

---

## 2. What never counts toward factory score

These may exist in git history if a human insists, but **score = 0**:

| Exclusion | Why |
|---|---|
| Whitespace / import-sort / rename-only | Inflates history |
| README / marketing thrash without product change | Noise |
| Split of one logical fix into N commits | Farming |
| Work refuted by adversarial review and not fixed in-pass | Failed gate |
| Fence violations (portfolio, screener, TA, competitor scrape, etc.) | Rejected |
| Manufactured audit findings to fill `MAX_PASSES` | Gaming |
| Planning-only / catalog / METRICS edits that don’t unblock a gate | Meta ≠ product |
| Failed verify (`ruff` / `mypy` / `pytest` / dash smoke red) | No proof |
| Duplicate of an already-accepted fix | No new value |

**Formula (honest):**

```
proper_commits(pass) = |commits that pass COMMIT_FACTORY “proper commit”|
clusters_closed(pass) = |distinct WS or BAR items closed with proof|
factory_score(pass)  = min(proper_commits(pass), clusters_closed(pass))
```

Raw `git rev-list --count` is **not** a KPI. Docs/ops commits score only with `closes: WS-###` or `closes: BAR-#` in the body.
Rejected, refuted, or excluded commits do not enter the sum.
Minors-only passes that close zero clusters score **0** even if commits exist.

---

## 3. Per-pass scorecard template

Copy into each pass report under `docs/factory/`. Fill only with proof (command paths / log excerpts), not aspirations.

| Field | Value |
|---|---|
| Pass ID | `CORE-P0NN` / `DASH-P0NN` / `OPS-P0NN` |
| Lane | CORE \| DASH \| OPS |
| Date (UTC) | YYYY-MM-DD |
| Agents used | n (≤8 preferred, ≤16 hard) |
| Findings opened | n (by severity: blocker / major / minor) |
| Findings closed | n |
| Proper commits accepted | n |
| Proper commits rejected / excluded | n |
| Quality bars touched | list #1–#8 from COMMIT_FACTORY §2 |
| Verify | `ruff` ☐ `mypy` ☐ `pytest` ☐ dash smoke ☐ N/A |
| Adversarial review | pass ☐ / refute→fixed ☐ / refute→open ☐ |
| Fence violations | none ☐ / list |
| Stop signal? | 2 consecutive passes with 0 > minor? yes/no |
| Notes | ≤5 lines; link artifacts |

| Quality bar | Status this pass | Proof |
|---|---|---|
| 1 Alert correctness | unchanged / improved / regress | |
| 2 Zero dup / zero loss | … | |
| 3 Latency | … | |
| 4 Resilience | … | |
| 5 Ops | … | |
| 6 Code quality | … | |
| 7 Bot UX | … | |
| 8 Dash UX | … | |

---

## 4. Definition of Done (a pass)

A pass is **Done** only when all hold:

1. **Plan existed first** — each accepted commit’s acceptance criterion was written before implementation.
2. **Verify green** — `ruff`, `mypy`, `pytest` (and dash smoke when DASH files changed) run and recorded in the scorecard.
3. **Adversarial review closed** — no open concrete failure scenario against this pass’s commits; either no refute or fix landed same pass.
4. **Scorecard filed** — template above completed; proper vs excluded commits enumerated.
5. **Fences intact** — no CLAUDE.md / COMMIT_FACTORY violation in the diff.
6. **One concern per commit** — no bundling unrelated fixes to “look productive.”
7. **Lane hygiene** — no conflicting file ownership across concurrent agents in the wave.

If any item fails → pass is **not Done**; do not count its commits toward factory score until remediated.

**Lane epoch STOP:** two consecutive Done passes with zero findings above **minor**.

---

## 5. Remaining proper-commit backlog (from WS catalog, without gaming)

Source of truth: [workstreams/INDEX.md](workstreams/INDEX.md) + wave notes — not gut feel, not `MAX_PASSES × agents`.

### Estimate procedure

1. **Inventory** — list WS items still `open` / `partial` that map to a quality bar or an allowed lane deliverable.
2. **Cluster** — merge WS items that are the *same* concern (one proper commit may close several WS rows). Count **clusters**, not rows.
3. **Size** — each cluster → expected proper commits ∈ `{1, 2, 3}` only:
   - `1` = single concern, clear AC
   - `2` = implement + dedicated proof/test commit if AC demands it
   - `3` = rare (e.g. feat + fix discovered in-pass + test); justify in plan
4. **Backlog** =

   ```
   remaining_proper ≈ Σ over open clusters (expected_commits)
   ```

5. **Recompute every pass** after closes; never add synthetic WS rows to keep the number high.

### Anti-gaming rules

| Forbidden | Required instead |
|---|---|
| One WS → N micro-commits | One cluster → ≤3, usually 1 |
| New WS invented mid-pass to pad backlog | Only constitution/fence gaps → new WS via human-approved amend |
| Counting closed WS as remaining | Status must flip when merge lands |
| Equating catalog size (100) with backlog | Catalog is a *menu*; backlog is *open clusters* |
| Using `MAX_PASSES` as a target count | `MAX_PASSES` is a ceiling, not a quota |

---

## 6. KPI: reject vanity volume

**“Trillion commits”, “50M/10K raw commits on this repo”, or any raw commit-count KPI is rejected.** It rewards farming, thrash, and split fixes. It conflicts with the constitution: quality over count.

The **active** aspiration is **Quiverly `repo_score` ∈ [2000, 3000]** (midpoint 2500) — see [KOEL_HORIZON.md](KOEL_HORIZON.md). Larger portfolio numbers wait.

### Replacement KPIs (report monthly)

| KPI | Definition | Healthy signal |
|---|---|---|
| **Rolling 30-day proper-commit rate** | Count of commits that met §1 proper-commit rules in the last 30 days, by lane | Sustained rate with proof artifacts; not a spike of exclusions |
| **Quality bar posture** | Per bar #1–#8: `regress` / `hold` / `advance` vs prior month | No silent regress; advances backed by tests/ops proof |
| **Pass yield** | `proper_commits / Done passes` (30d) | Stable; collapse ⇒ thrash or over-splitting |
| **Refute rate** | Refuted findings / findings reviewed (30d) | Rising refute rate ⇒ slow down, fix review depth |
| **Backlog burn** | Δ `remaining_proper` month-over-month | Down without inventing WS filler |

Aspiration: **high proper-commit rate under the quality bar**, across Cloud Agent sessions — never fake volume.

```
health = f(proper_rate_30d, quality_bars, pass_yield, low_refute_surprises, honest_backlog)
≠ git_commit_count
≠ MAX_PASSES × agents
≠ “trillion”
```
