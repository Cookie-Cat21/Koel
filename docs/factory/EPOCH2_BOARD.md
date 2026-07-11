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
| E2-C02 | CORE-005 await in-flight tick on shutdown (timeout) | DONE | `8477cf6` await `_tick_task` (30s); `tests/test_shutdown_await.py` |
| E2-C03 | Claim+disarm single DB transaction | OPEN | |
| E2-C04 | Persist delivered-guard (survive restart) — `message_sent` optimistic or delivery lease | OPEN | |
| E2-C05 | Unsent SKIP LOCKED / lease so RetryAfter need not hold advisory lock | OPEN | |
| E2-C06 | tradeSummary miss → health flag / log watched_missing | DONE | `1a1739e` `_poll_prices` + `tests/test_watched_missing.py` |
| E2-C07 | Dead-letter user/ops notify (bot message or structured alert) | OPEN | |

## OPS

| ID | Item | Status | Notes |
|---|---|---|---|
| E2-O01 | Expand cov gate beyond rules (`--cov=chime` with floors) | DONE | `--cov=chime --cov-fail-under=60` (measured ~63% unit; 70/85 not yet achievable) |
| E2-O02 | Storage pool `max_size >= 2` guard when advisory lock used | DONE | `Storage.__init__` raises ValueError if `max_size < 2`; `tests/test_pool_guard.py` |
| E2-O03 | Factory verify script + loop_status in CI or make | DONE | |

## DASH (largest fuel)

| ID | Item | Status | Notes |
|---|---|---|---|
| E2-D01 | `web/` Next.js + Tailwind + shadcn scaffold | DONE | `2934773` Next 16 App Router + Tailwind v4 + shadcn (radix) |
| E2-D02 | Demo session auth per ADR 001 | DONE | `2934773` `POST /api/v1/auth/demo`, `/login`, signed HttpOnly `chime_session` |
| E2-D03 | CSRF bootstrap; logout requires CSRF | DONE | CSRF double-submit helpers; `POST /auth/logout` requires `X-CSRF-Token`; login exempt |
| E2-D04 | Read APIs: watchlist, alerts, fires, health (Postgres only) | DONE | `GET` watchlist, alerts, alerts/history, health (+ me); session + DATABASE_URL only |
| E2-D05 | Brand-first shell page (no fake trading terminal) | OPEN | |
| E2-D06 | THIRD_PARTY.md + dash smoke script | OPEN | partial: `2934773` `docs/THIRD_PARTY.md` (+ web deps); smoke script still open |

## Wave packing (≤8 agents)

**Wave A (this session start):** C01, C02, C06, O01, O02, D01, D02, O03  
**Wave B:** C03, C04, C05, C07, D03, D04  
**Wave C:** D05, D06 + adversarial CLEAN×2

## Stop for Epoch 2

All OPEN → DONE or DEFER with reason; then CLEAN×2 on epoch2 branch → open Epoch 3 board (dash CRUD), **do not idle**.
