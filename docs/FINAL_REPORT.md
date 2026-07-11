# Chime — Stage A final report

## Stage A delivered

Telegram-first CSE alerting end-to-end:

| Piece | Status |
|---|---|
| CSE adapter (`tradeSummary`, `companyInfoSummery`, `getAnnouncementByCompany`) | Done — retries, circuit breaker, per-row tradeSummary skip |
| Postgres schema + migrate | Done — `db/migrations/001_initial.sql` |
| Poller (market hours Asia/Colombo) | Done — snapshots, disclosures, advisory lock, unsent retry |
| Rule engine | Done — price above/below crossing, daily % crossing, disclosure |
| Telegram bot | Done — `/start`, `/watch`, `/unwatch`, `/alert`, `/cancel`, `/myalerts`, `/mywatchlist` |
| Health HTTP | Done — `/health` reflects DB + last tick (incl. lock-skip / degraded poll) |
| Idempotent claims | Done — `alert_log UNIQUE(rule_id, event_key)` + session advisory lock |

Product plan: [CLAUDE.md](../CLAUDE.md). Endpoint probe: [endpoint_probe_report.md](endpoint_probe_report.md).

## Passes run (1–4)

| Pass | Role | Outcome |
|---|---|---|
| 1 | Adversarial audit + fixes | Critical/high: disclosure backfill, disarm-before-claim, `/cancel`+`/unwatch`, dual-poller, health, latency honesty, junk rows, move crossing, START copy, upstream errors, disclosure URL, Colombo dates |
| 2 | Re-audit + fixes | Critical: sticky session advisory lock (Pass 1 lock was broken with the pool). High: health on lock-skip. Medium: null `createdDate` epoch, disclosure-leg health, disarm-after-claim intent |
| 3 | Adversarial re-check | Zero findings above minor → CONVERGE candidate |
| 4 | Final adversarial re-check | Zero findings above minor → **STOP** ([PASS4_AUDIT.md](PASS4_AUDIT.md)) |

## Quality bar (honest)

| # | Bar | Score | Proof |
|---|---|---|---|
| 1 | Alert correctness (crossing) | **pass** | `pytest` unit tests for above/below/gap/move/disclosure filters; `chime.rules` 100% cov |
| 2 | Zero dup / zero loss | **pass** | Claim-before-disarm; crossing-stable `event_key`; session lock held on one pooled connection until unlock (`tests/test_advisory_lock.py` when `DATABASE_URL` set) |
| 3 | Latency | **partial** | `alert_latency_ms` logs **claim→send**. CSE print→Telegram is **poll-interval bounded** (default 60s + jitter) — **not** p95&lt;5s end-to-end. README documents this. |
| 4 | Resilience | **pass** | Circuit open / junk tradeSummary row / disclosure HTTP errors covered in tests |
| 5 | Ops | **pass** | `/health` 200/503; structured logs; secrets from env; migrate CLI |
| 6 | Code quality | **pass** | See commands below |
| 7 | Bot UX | **pass** | `/cancel`, honest START (disclosures need explicit `/alert … disclosure`), upstream vs not-found |

### Proof commands (this environment, 2026-07-11)

```text
$ python3 -m ruff check chime tests
All checks passed!

$ python3 -m mypy chime
Success: no issues found in 15 source files

$ python3 -m pytest -o addopts='-q --cov=chime.rules --cov-report=term-missing --cov-fail-under=85'
55 passed, 3 skipped in ~1.5s
chime/rules.py  77 stmts  0 miss  100%
```

Skipped tests: integration paths that need `DATABASE_URL` (incl. advisory-lock dual-holder). With Neon/Postgres set, `tests/test_advisory_lock.py` exercises real `pg_try_advisory_lock` across two `Storage` instances.

## Deferred (not Stage A blockers)

- Bulk `approvedAnnouncement` for large watchlists (latency at scale)
- Sub-5s CSE→Telegram (would need much faster polling + CSE load budget)
- Live deep-link UX verification of `#announcementId` on cse.lk
- Unbounded unsent retry / dead-letter after N permanent Telegram failures
- Concurrent identical `/alert` IntegrityError handling
- `both` SIGTERM polish; `tick` without `--force` still forces (`force or True`)
- Same-minute rearm + identical price `event_key` collision (intentional dual-poller tradeoff)
- `Storage(max_size=1)` deadlock risk while holding advisory lock (default `max_size=4`)
- Parse `dateOfAnnouncement` when `createdDate` is null (currently epoch fail-closed)
- Automated dual-poller kill test in CI without optional DB

## How to run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # TELEGRAM_BOT_TOKEN + DATABASE_URL
python -m chime migrate
python -m chime both   # or: bot | poller | tick --force
```

Health: `http://127.0.0.1:8080/health` (override `HEALTH_HOST` / `HEALTH_PORT`).

Bot commands: `/watch`, `/unwatch`, `/alert SYMBOL above|below|move|disclosure`, `/cancel ALERT_ID`, `/myalerts`, `/mywatchlist`.

## Latency claim (do not oversell)

- **Instrumented:** claim → Telegram send (`alert_latency_ms`); target p95&lt;5s for that segment under normal Telegram.
- **Not claimed:** CSE last trade → Telegram p95&lt;5s. That path is bounded by `POLL_INTERVAL_SECONDS` (default 60) plus jitter and per-symbol disclosure pacing.
