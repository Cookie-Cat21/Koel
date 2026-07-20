# Tijori / CSE Phase 1 — ops enablement

Short flags for market browse + filing-brief plumbing. Full deploy: [PRODUCTION.md](PRODUCTION.md). Plan: [TIJORI_CSE_PLAN.md](../factory/TIJORI_CSE_PLAN.md).

Import/`migrate --help` smoke (no live CSE): `make tijori-smoke`.

## Market browse (`/market`)

No extra env. Poller already persists full `tradeSummary` into `stocks` + `price_snapshots` (watchlist empty still OK).

```bash
python -m koel migrate
# Seed browse once (ignores market hours), or leave poller/both running:
make tick                 # → python -m koel tick --force
# SECTORS_INGEST=1 make tick   # optional sector board for GET /api/v1/sectors
# python -m koel poller  # or: both
# dash → /market (session); data = Postgres only
```

Empty board ⇒ no snapshots yet — run `make tick` (or leave poller/both running), then refresh; or `tradeSummary` was empty that tick. `/market` empty copy points operators at `make tick`.

Top movers rows use one symbol+**Watch** link to `/symbols/[symbol]` (accessible name includes the ticker). Actual add stays on `/watchlist` (“Add via watchlist” note on the strip) — no inline watch POST from `/market`.

## AI briefs (`AI_BRIEFS_ENABLED`)

Default **off**. Stub in `koel/briefs/`; no LLM until explicitly enabled.

```bash
AI_BRIEFS_ENABLED=0          # leave off in prod until Phase 2
# Phase 2 live:
# AI_BRIEFS_ENABLED=1
# AI_API_KEY=…               # primary; backups alone also satisfy briefs_enabled()
# AI_PROVIDER=gemini         # or: groq | openrouter (OpenAI-compatible chat)
# AI_MODEL=gemini-2.0-flash  # groq: llama-3.3-70b-versatile; openrouter: openai/gpt-4o-mini
# Optional failover (429 / 5xx / timeout only — not permanent 4xx / empty text):
# AI_BACKUP_PROVIDERS=groq,openrouter
# AI_BACKUP_API_KEYS=…,…
# AI_BACKUP_MODELS=llama-3.3-70b-versatile,openai/gpt-4o-mini
```

### Telegram `/brief SYMBOL`

Read-only lookup of the latest **ready** filing brief for a symbol from Postgres (`get_latest_ready_brief`). Does **not** call an LLM and does not enqueue work.

| Reply | When |
|---|---|
| Usage + example | Missing args |
| Bad-symbol hint | Symbol fails normalize |
| `{SYMBOL}: AI briefs are off` + NFA | No ready row and `briefs_enabled()` is false |
| `{SYMBOL}: none yet` + NFA | No ready row and AI is enabled |
| Title + allowed filing URL + brief body + NFA | Ready brief found |

Rate-limited with other bot commands. Ops: leave `AI_BRIEFS_ENABLED=0` until a controlled soak; `/brief` still works for already-ready rows when AI is on.

## Load envelope (ops planning)

Planning numbers for one poller replica at defaults. Not SLOs — capacity / quota guardrails before a briefs-on soak.

### Price snapshots (~300 / min)

| Knob | Default | Effect |
|---|---|---|
| CSE board size | ~280–300 symbols | `tradeSummary.reqTradeSummery[]` (sample note: 282) |
| `POLL_INTERVAL_SECONDS` | `60` (+ `POLL_JITTER_SECONDS=5`) | One full-board persist per tick |

→ **~300 `price_snapshots` rows/min** during market hours (one row per symbol per tick). CSE HTTP stays **1** `POST /tradeSummary` per tick (bulk), not N per-symbol quote calls. Rule eval stays watchlist-scoped; empty watchlist still persists the board for `/market`.

Optional extras per tick (fail-soft): `SECTORS_INGEST=1` → one `POST /allSectors`; disclosure rules → bulk and/or per-symbol announcement calls; PDF enrich → polite `PDF_ENRICH_SLEEP_SECONDS` before each legacy symbol call (outside the poll lock). Soft global gap between CSE HTTP calls: `CSE_MIN_INTERVAL_SECONDS` (default `0` = off; raise if cse.lk rate-limits — applies on the shared `CSEClient`, including bot symbol lookup).

### Brief caps (Quiverly-side)

| Env | Default | Role |
|---|---|---|
| `AI_MAX_BRIEFS_PER_DAY` | `50` | Hard daily claim budget (`BRIEF_CAP_LOCK_ID`); `ready`/`failed` count toward it |
| `AI_BRIEF_SLEEP_SECONDS` | `0.5` | Pause between consecutive LLM calls in a drain |
| `AI_HTTP_TIMEOUT_SECONDS` | `30` | Provider HTTP timeout per LLM call |
| `AI_MAX_INPUT_CHARS` | `12000` | Truncate filing text before provider call |
| `PDF_MAX_BYTES` | `5242880` | Max PDF download for extract |
| `BRIEF_PDF_GRACE_SECONDS` | `120` | Wait for `pdf_url` before title-only summarize |
| `BRIEF_CDN_BACKOFF_SECONDS` | `300` | After transient CDN miss requeue, skip reclaim |
| `BRIEF_SKIPPED_PROMOTE_HOURS` | `24` | When AI is on, re-queue recent skipped ledger rows as pending (`0` = off) |
| `BOT_CMD_RATE_PER_MINUTE` | `20` | Per-user Telegram cmd window (includes `/brief`) |

Leave `AI_BRIEFS_ENABLED=0` until keyed; raising `AI_MAX_BRIEFS_PER_DAY` past free-tier RPD without a paid plan will 429 under a disclosure burst. CDN miss requeues **pending** (no daily-cap burn).

### Free provider API limits (verify in console)

Vendor free-tier RPM/RPD/TPM **drift by model and account** — confirm in [Google AI Studio](https://aistudio.google.com/) / [Groq console](https://console.groq.com/settings/limits) / OpenRouter dashboard before soak. Quiverly defaults are sized to sit **under** typical free ceilings:

| Provider (`AI_PROVIDER`) | Soft-default model | Free-tier planning envelope (approx.) | Quiverly fit |
|---|---|---|---|
| `gemini` | `gemini-2.0-flash` | Flash-class free rows often ~15 RPM / ~1.5k RPD (project-level; check Quotas) | `50` briefs/day + `0.5`s sleep ≪ RPD; well under RPM |
| `groq` | `llama-3.3-70b-versatile` | Often ~30 RPM / ~1k RPD / ~12k TPM (org-level) | Daily cap ≪ RPD; sleep keeps bursts off RPM |
| `openrouter` | `openai/gpt-4o-mini` | Free/route limits vary widely by model | Treat as bursty; keep Quiverly caps; prefer keyed paid route for soak |

On HTTP 429 the drain fails soft and retries on a later tick — do not disable pacing to “catch up.” Model IDs in `.env.example` may lose free eligibility; swap `AI_MODEL` to a current free Flash/chat row rather than raising Quiverly caps first.

## Advisory locks (poll vs brief claim)

Poll tick uses session `pg_try_advisory_lock(4_201_337)`; brief daily-cap claim uses transaction `pg_advisory_xact_lock(4_201_339)`. Wave 10 audit: **no deadlock** between them (distinct keys; brief drain after poll unlock; claim uses `SKIP LOCKED`). Do **not** unify the IDs — same key + `max_size=2` can pool-deadlock. Detail: [ADVISORY_LOCK_DEADLOCK.md](../factory/passes/ADVISORY_LOCK_DEADLOCK.md).

## Scheduled drains (`drain-pdfs` / `drain-briefs` / `drain-metrics`)

Backfill helpers for PDF enrich + filing metrics + AI briefs when the market-hours
poller is idle. Same CSE JSON + CDN path as the poller — **not** competitor scrapes.

```bash
python -m koel migrate
python -m koel drain-pdfs --limit 30          # watched symbols missing pdf_url
python -m koel drain-metrics --limit 30       # needs FINANCIAL_METRICS_ENABLED=1
python -m koel drain-briefs --limit 10        # needs AI_BRIEFS_ENABLED=1 + keys
# --all-symbols  → include non-watchlist rows (pdfs/metrics only)
```

Optional GitHub Action: `.github/workflows/pdf-metrics-drain.yml` (hourly +
`workflow_dispatch`). Requires `DATABASE_URL` secret; AI secrets only if
`run_briefs=true` / `vars.DRAIN_BRIEFS=1`.

## PDF enrich sleep (`PDF_ENRICH_SLEEP_SECONDS`)

After alert claim, the poller fire-and-forgets legacy `POST /announcements` → `filePath` → CDN `pdf_url` enrichment **outside** the advisory lock and outside `run_once`'s await path (so sleeps never pin the tick or delay Telegram). Polite pause **before each symbol's** legacy call:

```bash
PDF_ENRICH_SLEEP_SECONDS=0.5   # default; set 0 to disable; raise if CSE rate-limits
```

Wired in `koel/config.py` → `Settings.pdf_enrich_sleep_seconds` (float; negative values clamp to 0).

## CSE soft pacing (`CSE_MIN_INTERVAL_SECONDS`)

Adapter-level soft gap between consecutive cse.lk HTTP calls on one `CSEClient` (poller + bot share the client in `both` mode). No sleep before the first call; concurrent callers serialize on an internal pace lock. Default **off** so tick latency stays unchanged; raise under rate-limit pressure (distinct from `PDF_ENRICH_SLEEP_SECONDS`, which only paces legacy PDF enrich):

```bash
CSE_MIN_INTERVAL_SECONDS=0     # default; e.g. 0.2 if CSE starts 429/blocking
```

Wired in `koel/config.py` → `Settings.cse_min_interval_seconds` → `CSEClient(min_interval_seconds=…)`. Also covered by tick spacing (`POLL_INTERVAL_SECONDS` + jitter) and sequential disclosure HTTP (natural spacing under the poll lock — avoid long sleeps under the advisory lock).

## Snapshot retention (`SNAPSHOT_RETENTION_DAYS`)

Optional. Default **0** (off). After each successful market persist, delete `price_snapshots` older than N days for symbols **not** on any watchlist. Watched symbols keep full history. Fail-soft on cleanup errors — never degrades the tick.

```bash
SNAPSHOT_RETENTION_DAYS=0    # default — keep all board history
# SNAPSHOT_RETENTION_DAYS=14 # trim unwatched browse history
```

Wired in `koel/config.py` → `Settings.snapshot_retention_days`.

## Sector ingest (`SECTORS_INGEST`)

Optional. Default **off** (`0`). When `1`, each poll tick POSTs `/allSectors` and upserts the `sectors` table (fail-soft). Thin `GET /api/v1/sectors` reads Postgres only — empty `items` until ingest has run once.

```bash
SECTORS_INGEST=0             # default — skip
# SECTORS_INGEST=1 make tick # seed sector board once
```

Wired in `koel/config.py` → `Settings.sectors_ingest`. See `tests/test_sectors_ingest.py`.

## Bulk disclosure feed (`DISCLOSURE_BULK_FEED`)

Optional. Default **off** (`0`). When `1`, disclosure discovery uses one market-wide `POST /approvedAnnouncement` plus a unique `stocks` name→symbol map, then fail-soft to per-symbol `getAnnouncementByCompany` for uncovered tickers or on bulk/map errors. Still only runs for symbols with active disclosure rules.

```bash
DISCLOSURE_BULK_FEED=0   # default — per-symbol getAnnouncementByCompany only
# DISCLOSURE_BULK_FEED=1 # reduce HTTP for large disclosure watchlists
```

Flag name is `DISCLOSURE_BULK_FEED` (not `DISCLOSURE_BULK`). See `.env.example` and `tests/test_disclosure_bulk_feed.py`.

## Briefs-on soak (checklist)

1. Confirm provider free/paid quotas in console (table above).
2. Set `AI_API_KEY` + `AI_PROVIDER` / `AI_MODEL`; leave `AI_MAX_BRIEFS_PER_DAY=50` until proven.
3. Flip `AI_BRIEFS_ENABLED=1` on **one** replica; watch health + brief ledger (`pending` / `ready` / `failed`).
4. Keep `AI_BRIEF_SLEEP_SECONDS` ≥ `0.5`; do not raise the daily cap to “catch up” after 429s.
5. `/brief SYMBOL` stays read-only of ready rows — not a live LLM call.
