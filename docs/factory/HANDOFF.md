# Factory HANDOFF

**Updated:** 2026-07-11  
**Branch:** `cursor/epoch11-drain-cb19`  
**PR:** open for this branch (base `main`)  
**KPI:** Portfolio Plan A — `factory_score` (not raw commits)

## Resume

```bash
git pull origin cursor/epoch11-drain-cb19
make factory-status
# Continue OPEN items; refill when empty
make factory-verify   # clears DATABASE_URL (unit path)
```

## State

- See `SCOREBOARD.json` for lifetime score  
- Active board: `EPOCH14_BOARD.md` (refilled after Epoch 13 CLEAR)  
- Loop: `AGENTIC_LOOP.md` + `PORTFOLIO_PLAN.md` + `LONG_RUN_OPS.md`
- Prior: Epochs 10–13 cleared on this lineage; Epoch 14 is coverage + ops honesty

## E13 -> E14 refill path

Epoch 13 CLEAR -> `make factory-refill` -> Epoch 14 active. Epoch 13 drained
8 residual reliability / API honesty items: watched-missing health detail,
delivery attempted OK checks, endpoint probe contracts, and final
alert-delivery documentation polish.

Canonical factory verification is `make factory-verify`, which runs the unit
path with `DATABASE_URL=` via `scripts/factory/verify.sh`:
`DATABASE_URL= pytest -q --tb=line`.

## Next wave hint

Drain Epoch 14 OPEN rows only. Do not invent out-of-fence fuel.
