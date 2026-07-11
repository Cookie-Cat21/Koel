# Chime — Agentic Factory Loop (perpetual)

**Status:** Active (Portfolio Plan A)  
**Authority:** [COMMIT_FACTORY.md](COMMIT_FACTORY.md) + [CLAUDE.md](../CLAUDE.md)  
**Portfolio KPI:** [PORTFOLIO_PLAN.md](PORTFOLIO_PLAN.md) — `portfolio_score = Σ min(proper, clusters)`  
**Long runs:** [LONG_RUN_OPS.md](LONG_RUN_OPS.md) — multi-hour session + multi-session handoff  
**Aspiration:** Maximize lifetime / portfolio `factory_score` with outstanding quality.  
**Banned:** Raw commit farming, trillion-count theater.

## 1. Loop (never idle while backlog remains)

```
while True:
  1. LOAD board (epoch open items + ACCEPT-DEFER + adversarial findings)
  2. if board empty:
       run scripts/factory/refill_board.py
       if NO_FUEL AND clean_streak >= 2: STOP lane
  3. PLAN wave: pick ≤8 OWNED_FILES-disjoint work items (hard max 16)
  4. IMPLEMENT via parallel agents
  5. VERIFY: make factory-verify; cite HEAD SHA
  6. ADVERSARIAL: ≤8 reviewers; REFUTE ⇒ fix same pass
  7. REPORT + update_scoreboard; push; update PR
  8. Append SESSION_LOG line
  9. if 0 findings > minor: clean_streak += 1 else clean_streak = 0
  10. NEVER stop for “N waves” or “commit count looks big”
  11. On wall-clock limit: write HANDOFF.md and exit (next session resumes)
```

## 2. Outstanding performance bar

Every accepted commit must move at least one of:

| Bar | Evidence |
|---|---|
| Alert correctness | Test or fix with scenario |
| Zero dup / zero loss | Lock/claim/retry/DL proof |
| Resilience | Failure path covered |
| Ops honesty | Health/CI/DX |
| Bot UX | Handler + test |
| Dash UX | Usable surface inside fence |
| Code quality | ruff/mypy/pytest green |

Minors-only churn → score 0, anti-churn STOP for that lane, then **open next fuel** (new epoch board), do not farm.

## 3. Concurrency

| Knob | Value |
|---|---|
| Preferred parallel implementers | 8 |
| Hard max | 16 |
| Preferred adversarial | 4–8 |
| Path intersect in a wave | **Fail the wave** |

## 4. Fuel refill (how the loop stays alive without farming)

When a lane CLEAN×2:

1. Pull next unused WS from catalog / product fence expansions **approved by constitution**.
2. Prefer **DASH** (largest surface) while `web/` incomplete.
3. Prefer **quality ratchet** (cov floors, integration proofs).
4. Prefer **real user-visible gaps** over doc thrash.
5. If no fuel remains inside fences → **global STOP** (honest).

## 5. Artifacts

| Path | Role |
|---|---|
| [PORTFOLIO_PLAN.md](PORTFOLIO_PLAN.md) | KPI A + multi-hour / multi-repo plan |
| [LONG_RUN_OPS.md](LONG_RUN_OPS.md) | Session heartbeat |
| [HANDOFF.md](HANDOFF.md) | Cross-session resume |
| `EPOCH*_BOARD.md` | Pre-seeded fuel (5+) |
| [SCOREBOARD.json](SCOREBOARD.json) | Machine-readable score |
| `scripts/factory/loop_status.py` | Status |
| `scripts/factory/refill_board.py` | Anti-idle refill |
| `scripts/factory/next_wave.py` | Wave packing |
| `scripts/factory/verify.sh` | Canonical verify |

## 6. Orchestrator prompt (every session — hours)

1. Read CLAUDE.md + PORTFOLIO_PLAN + this file + HANDOFF.  
2. `make factory-status` / `make factory-wave`.  
3. Spawn ≤8 implementers on OPEN (disjoint paths).  
4. `make factory-verify` + adversarial.  
5. Commit/push/update PR; append SESSION_LOG.  
6. If board empty → `make factory-refill` → continue.  
7. Repeat until wall-clock → write HANDOFF (do not abandon mid-wave).
