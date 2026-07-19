# Portfolio Factory Score — Plan A (locked)

**KPI (locked):**
```
repo_score(r)     = min(proper_commits(r), clusters_closed(r))
portfolio_score   = Σ repo_score(r)   over all enrolled factories
```

**Not the KPI:** raw `git rev-list --count`, whitespace farms, split fixes.

**Horizon:** Multi-year climb across many products. Quiverly is **node 1** (~148 `repo_score` so far).

**Near-term (active):** [CHIME_HORIZON.md](CHIME_HORIZON.md) — Quiverly `repo_score` **2K–3K** (midpoint 2500).  
**Later:** 10K portfolio / 50M fantasy — only after this band.

**Authority:** Each repo still obeys its own constitution (for Quiverly: `CLAUDE.md` + `COMMIT_FACTORY.md`). Farming banned everywhere.

---

## 1. Why this can run for hours (and sessions)

A single Cloud Agent session has a wall clock. The **factory** outlives it:

| Layer | Duration | Mechanism |
|---|---|---|
| **Wave** | minutes | ≤8 agents, disjoint `OWNED_FILES`, verify |
| **Session** | hours | Orchestrator loops waves until timeout / human stop |
| **Campaign** | days–years | New sessions resume from board + scoreboard |
| **Portfolio** | years | Add repos; sum `repo_score` |

**Anti-idle rule:** When a board clears, **immediately open the next epoch board** with fence-legal fuel. Never stop because “we did N waves.” Stop a *lane* only on CLEAN×2 with no fuel left inside fences.

---

## 2. Long-run session protocol (hours)

Every orchestrator session:

```
0. git pull; make factory-status; read PORTFOLIO_PLAN + AGENTIC_LOOP
1. while session_budget_remaining AND (OPEN items OR refill_possible):
     a. Pack wave ≤8 OPEN items (path-disjoint)
     b. Spawn implementers
     c. make factory-verify (or scripts/factory/verify.sh)
     d. Spawn ≤4 adversarial; fix REFUTE same wave
     e. update_scoreboard; commit+push; update PR
     f. if board empty → open next EPOCH_N_BOARD (pre-seeded backlog)
     g. Log wave to docs/factory/passes/SESSION_LOG.md
2. Write HANDOFF.md: HEAD, score, next OPEN, known DEFERs
3. Exit cleanly so the *next* session continues without re-planning
```

**Session budget knobs (set per run):**

| Knob | Default | Meaning |
|---|---|---|
| `MAX_WAVES` | 50 | Soft cap per session (not a farm target) |
| `MAX_WALL_MINUTES` | 240 | Prefer stop with handoff before hard kill |
| `CONCURRENCY` | 8 | Hard max 16 |
| `REFILL` | true | Auto-open next epoch when board clears |

---

## 3. Quiverly fuel pipeline (keeps hours busy)

Pre-seeded epoch ladder (fence-legal only):

| Epoch | Theme | Approx clusters |
|---|---|---|
| 5 | Deploy / secrets / empty states / migrate tests | ~7 |
| 6 | Dash UX polish, a11y, loading/error, symbol deep links | ~10 |
| 7 | Bot UX polish, /help, NFA consistency, rate-limit docs | ~8 |
| 8 | Observability: more health fields, runbooks, compose profiles | ~8 |
| 9 | Quality ratchet: cov→85 modules, more DB integration | ~10 |
| 10 | API completeness vs contract gaps; CSRF audit tests | ~8 |
| 11+ | Only after human fence expansion OR new product node | — |

When Epoch N clears → open N+1 from this ladder (or `scripts/factory/refill_board.py`).

**Estimated Quiverly-only proper ceiling:** hundreds–low thousands. Operating band **2K–3K**: [CHIME_HORIZON.md](CHIME_HORIZON.md).

---

## 4. Multi-repo enrollment (portfolio climb)

For each new product:

1. Copy factory kit: `AGENTIC_LOOP`, boards, `verify.sh`, `loop_status.py`, `SCOREBOARD.json`.
2. Set product fences (non-goals) in that repo’s constitution.
3. Register in `docs/factory/PORTFOLIO_NODES.json`:
   ```json
   { "repo": "org/chime", "path": ".", "score_file": "docs/factory/SCOREBOARD.json" }
   ```
4. Meta job (later): `scripts/factory/portfolio_sum.py` reads all nodes → `portfolio_score`.

**Until other repos exist:** Quiverly runs solo; `portfolio_score == chime.repo_score`.

---

## 5. What “outstanding” means over long runs

Every wave must move a quality bar. Reject:

- README thrash, import-only, rename-only  
- Splitting one fix into N commits  
- Manufacturing findings to fill `MAX_WAVES`  
- Minors-only waves with no bar movement (anti-churn → refill different fuel or stop lane)

---

## 6. Operator checklist (start a multi-hour run)

```bash
git checkout cursor/epoch2-agentic-loop-cb19 && git pull
make factory-status
# Orchestrator: spawn wave on OPEN items
make factory-verify
python3 scripts/factory/update_scoreboard.py
git push && # update PR
# Repeat until wall clock / handoff
```

Resume next session from `docs/factory/HANDOFF.md`.

---

## 7. Success metrics (report weekly / per session)

| Metric | Use |
|---|---|
| `portfolio_score` | Primary |
| `repo_score` per node | Fairness / bottlenecks |
| `waves_completed` | Throughput |
| `refuted_fixed_same_wave` | Quality |
| `raw_commit_count` | **Ignore** for goals |

Climb toward **2K–3K Quiverly `repo_score` first** — product truth and fuel map in [CHIME_HORIZON.md](CHIME_HORIZON.md).
