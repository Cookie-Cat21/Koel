# Epoch 3 Board — Dash CRUD + ratchet (loop continues)

**Status:** OPEN  
**Parent:** Epoch 2 board empty (16/16 DONE)  
**Rule:** Do not idle. Fuel = thin dash mutations + quality.

## DASH CRUD

| ID | Item | Status |
|---|---|---|
| E3-D01 | POST/DELETE watchlist (parity bot; CSRF) | DONE |
| E3-D02 | POST alerts + cancel (idempotent create; CSRF) | DONE |
| E3-D03 | Symbol detail page: last price + disclosures from Postgres | DONE |
| E3-D04 | Fire history UI page | DONE |
| E3-D05 | Health page (ops) from API | DONE |
| E3-D06 | Mobile layout pass on shell pages | DONE |

## QUALITY / CORE ratchet

| ID | Item | Status |
|---|---|---|
| E3-Q01 | Raise `--cov-fail-under` toward 70 with new tests | OPEN |
| E3-Q02 | Integration: claim_unsent_batch dual-poller no double send | OPEN |
| E3-Q03 | web typecheck/lint in CI | OPEN |
| E3-Q04 | dash_smoke in CI (node) | OPEN |

## Wave packing

Wave A: D01 D02 D03 Q03  
Wave B: D04 D05 D06 Q01 Q02 Q04  
Then adversarial CLEAN×2 → Epoch 4 or STOP if fences exhausted.
