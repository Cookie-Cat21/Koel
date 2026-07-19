# Factory HANDOFF

**Updated:** 2026-07-11  
**Branch:** `cursor/epoch11-drain-cb19`  
**PR:** https://github.com/Cookie-Cat21/chime/pull/6  
**KPI:** Portfolio Plan A — `factory_score` (not raw commits)

## Resume

```bash
git pull origin cursor/epoch11-drain-cb19
make factory-status
make factory-wave
make factory-verify   # clears DATABASE_URL (unit path)
```

## State

- Lifetime `factory_score` ≈ 140 (`SCOREBOARD.json`)
- Epochs **11–17 CLEAR**; **Epoch 18 ACTIVE** for thin polish / pre-seed cleanup
- Loop docs: `AGENTIC_LOOP.md`, `PORTFOLIO_PLAN.md`, `LONG_RUN_OPS.md`

## Note

Prefer lowest non-STAGED epoch with OPEN. Never farm commits. Fence = CLAUDE.md
non-goals + no cse.lk from `web/`.
