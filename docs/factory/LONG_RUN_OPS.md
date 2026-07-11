# Long-run session ops

Companion to [PORTFOLIO_PLAN.md](PORTFOLIO_PLAN.md). How a single agent session stays productive for **hours**.

## Heartbeat (every wave)

1. `make factory-status`  
2. If `OPEN=0` → run `python3 scripts/factory/refill_board.py` (opens next seeded epoch)  
3. Spawn ≤8 implementers  
4. `make factory-verify`  
5. Adversarial sample (or full if high-risk)  
6. `python3 scripts/factory/update_scoreboard.py`  
7. Append one line to `passes/SESSION_LOG.md`  
8. `git push`

## Do not exit early when

- Board still has OPEN items  
- Refill can open Epoch N+1  
- Verify is green and paths remain for dash/ops/test fuel  

## Do exit with HANDOFF when

- Approaching wall-clock limit  
- Clean streak ≥2 **and** refill returns NO_FUEL (fences exhausted)  
- Human says stop  

## Handoff template

See `HANDOFF.md` (overwrite each session end).
