# Epoch 2 Board — Agentic Loop Fuel

**Branch:** `cursor/epoch2-agentic-loop-cb19`  
**Status:** OPEN  
**Parent:** Factory loop STOP ledger + DASH foundation  

Items are `OPEN` | `IN_PROGRESS` | `DONE` | `DEFER`.  
Each DONE needs: commit SHA + verify proof in pass report.

## CORE (STOP ledger + spine)

| ID | Item | Status | Notes |
|---|---|---|---|
| E2-C01 | CORE-003 DOA-only: fail-closed gate when only DOA (store DOA for display) | DONE | |
| E2-C02 | CORE-005 await in-flight tick on shutdown (timeout) | OPEN | |
| E2-C03 | Claim+disarm single DB transaction | OPEN | |
| E2-C04 | Persist delivered-guard (survive restart) — `message_sent` optimistic or delivery lease | OPEN | |
| E2-C05 | Unsent SKIP LOCKED / lease so RetryAfter need not hold advisory lock | OPEN | |
| E2-C06 | tradeSummary miss → health flag / log watched_missing | DONE | `_poll_prices`: `watched_missing` + `watched_symbols_missing` log; `price_ok=False` |
| E2-C07 | Dead-letter user/ops notify (bot message or structured alert) | OPEN | |

## OPS

| ID | Item | Status |
|---|---|---|
| E2-O01 | Expand cov gate beyond rules (`--cov=chime` with floors) | OPEN |
| E2-O02 | Storage pool `max_size >= 2` guard when advisory lock used | OPEN |
| E2-O03 | Factory verify script + loop_status in CI or make | DONE |

## DASH (largest fuel)

| ID | Item | Status |
|---|---|---|
| E2-D01 | `web/` Next.js + Tailwind + shadcn scaffold | OPEN |
| E2-D02 | Demo session auth per ADR 001 | OPEN |
| E2-D03 | CSRF bootstrap; logout requires CSRF | OPEN |
| E2-D04 | Read APIs: watchlist, alerts, fires, health (Postgres only) | OPEN |
| E2-D05 | Brand-first shell page (no fake trading terminal) | OPEN |
| E2-D06 | THIRD_PARTY.md + dash smoke script | OPEN |

## Wave packing (≤8 agents)

**Wave A (this session start):** C01, C02, C06, O01, O02, D01, D02, O03  
**Wave B:** C03, C04, C05, C07, D03, D04  
**Wave C:** D05, D06 + adversarial CLEAN×2

## Stop for Epoch 2

All OPEN → DONE or DEFER with reason; then CLEAN×2 on epoch2 branch → open Epoch 3 board (dash CRUD), **do not idle**.
