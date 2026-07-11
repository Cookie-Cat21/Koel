# Factory HANDOFF

**Updated:** 2026-07-11  
**Branch:** `cursor/epoch11-drain-cb19`  
**PR:** open for this branch (base `main`)  
**KPI:** Portfolio Plan A — `factory_score` (not raw commits)

## Resume

```bash
git pull origin cursor/epoch11-drain-cb19
make factory-status
# Continue OPEN Epoch 15 items; refill when empty
make factory-verify   # clears DATABASE_URL (unit path)
```

## State

- See `SCOREBOARD.json` for lifetime score  
- Active board: `EPOCH15_BOARD.md` (refilled after Epoch 14 CLEAR)  
- Loop: `AGENTIC_LOOP.md` + `PORTFOLIO_PLAN.md` + `LONG_RUN_OPS.md`
- Prior: Epochs 10–14 cleared on this lineage; Epoch 15 is resilience proofs + thin UX/ops

## E14 -> E15 refill path

Epoch 14 CLEAR -> `make factory-refill` -> Epoch 15 active. Epoch 14 drained
coverage and ops-honesty residuals, then Epoch 15 opened focused proof/docs/UX
items: claim leases, dead-letter notify, tradeSummary health detail, TG-OK
ledger docs, handoff logging, and `/cancel` copy.

Canonical factory verification is `make factory-verify`, which runs the unit
path with `DATABASE_URL=` via `scripts/factory/verify.sh`:
`DATABASE_URL= pytest -q --tb=line`.

## Next wave hint

Drain Epoch 15 OPEN rows only. Do not invent out-of-fence fuel.
