# Tijori / CSE Phase 1 — ops enablement

Short flags for market browse + filing-brief plumbing. Full deploy: [PRODUCTION.md](PRODUCTION.md). Plan: [TIJORI_CSE_PLAN.md](../factory/TIJORI_CSE_PLAN.md).

## Market browse (`/market`)

No extra env. Poller already persists full `tradeSummary` into `stocks` + `price_snapshots` (watchlist empty still OK).

```bash
python -m chime migrate
# Seed browse once (ignores market hours), or leave poller/both running:
make tick                 # → python -m chime tick --force
# python -m chime poller  # or: both
# dash → /market (session); data = Postgres only
```

Empty board ⇒ no forced tick / poller not running, or `tradeSummary` empty that tick.

Top movers rows use one symbol+**Watch** link to `/symbols/[symbol]` (accessible name includes the ticker). Actual add stays on `/watchlist` (“Add via watchlist” note on the strip) — no inline watch POST from `/market`.

## AI briefs (`AI_BRIEFS_ENABLED`)

Default **off**. Stub in `chime/briefs/`; no LLM until explicitly enabled.

```bash
AI_BRIEFS_ENABLED=0          # leave off in prod until Phase 2
# Phase 2 live:
# AI_BRIEFS_ENABLED=1
# AI_API_KEY=…               # required; briefs_enabled() needs both
# AI_PROVIDER=gemini         # or: groq | openrouter (OpenAI-compatible chat)
# AI_MODEL=gemini-2.0-flash  # groq: llama-3.3-70b-versatile; openrouter: openai/gpt-4o-mini
```

## Advisory locks (poll vs brief claim)

Poll tick uses session `pg_try_advisory_lock(4_201_337)`; brief daily-cap claim uses transaction `pg_advisory_xact_lock(4_201_339)`. Wave 10 audit: **no deadlock** between them (distinct keys; brief drain after poll unlock; claim uses `SKIP LOCKED`). Do **not** unify the IDs — same key + `max_size=2` can pool-deadlock. Detail: [ADVISORY_LOCK_DEADLOCK.md](../factory/passes/ADVISORY_LOCK_DEADLOCK.md).

## PDF enrich sleep (`PDF_ENRICH_SLEEP_SECONDS`)

After alert claim, the poller fire-and-forgets legacy `POST /announcements` → `filePath` → CDN `pdf_url` enrichment **outside** the advisory lock and outside `run_once`'s await path (so sleeps never pin the tick or delay Telegram). Polite pause **before each symbol's** legacy call:

```bash
PDF_ENRICH_SLEEP_SECONDS=0.5   # default; set 0 to disable; raise if CSE rate-limits
```

Wired in `chime/config.py` → `Settings.pdf_enrich_sleep_seconds` (float; negative values clamp to 0).

## Bulk disclosure feed (`DISCLOSURE_BULK_FEED`)

Optional. Default **off** (`0`). When `1`, disclosure discovery uses one market-wide `POST /approvedAnnouncement` plus a unique `stocks` name→symbol map, then fail-soft to per-symbol `getAnnouncementByCompany` for uncovered tickers or on bulk/map errors. Still only runs for symbols with active disclosure rules.

```bash
DISCLOSURE_BULK_FEED=0   # default — per-symbol getAnnouncementByCompany only
# DISCLOSURE_BULK_FEED=1 # reduce HTTP for large disclosure watchlists
```

Flag name is `DISCLOSURE_BULK_FEED` (not `DISCLOSURE_BULK`). See `.env.example` and `tests/test_disclosure_bulk_feed.py`.
