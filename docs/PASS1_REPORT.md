# Stage B — Pass 1 report

## What changed

Fixed top adversarial findings from `docs/PASS1_AUDIT.md`:

1. **Disclosure backfill** — `evaluate_disclosure_rules` skips `published_at <= rule.created_at`
2. **Disarm-before-claim** — claim+send first, then `set_armed(False)`
3. **`/cancel ALERT_ID`** — deactivate own rules; `/unwatch` deactivates owner rules for symbol
4. **Dual poller** — `pg_try_advisory_lock` + crossing-stable `event_key` (minute+price fingerprint)
5. **Health honesty** — `last_tick_ok=False` when watchlist set and price poll fails; poller-only health loop
6. **Latency** — `alert_latency_ms` logged; README documents poll-interval SLO honestly
7. **Per-row tradeSummary** — bad rows skipped, good rows kept
8. **Daily move crossing** — requires `|prev_pct| < thr <= |curr_pct|`; first observation baselines
9. **START copy** — disclosures need `/alert SYMBOL disclosure`
10. **CSE upstream vs bad ticker** — bot distinguishes unreachable vs not found
11. **Disclosure URL** — `#announcementId` fragment, no fake query
12. **Date window** — Asia/Colombo for disclosure from/to dates

## Proof

```
ruff check koel tests     → All checks passed
mypy koel                 → Success
pytest                     → 57 passed, koel.rules 100% coverage
```

## Quality bar score (Pass 1)

| # | Item | Score | Notes |
|---|---|---|---|
| 1 | Alert correctness | pass | Crossing + move crossing + disclosure created_at filter; unit proven |
| 2 | Zero dup / zero loss | pass* | Advisory lock + claim-before-disarm + unsent retry; dual-poller integration not fully automated |
| 3 | Latency p95 &lt; 5s | partial | claim→send instrumented; CSE→Telegram = poll interval (documented) |
| 4 | Resilience | pass | Circuit open / junk row / disclosure HTML error handled |
| 5 | Ops | pass | Health reflects tick failures; secrets from env |
| 6 | Code quality | pass | ruff+mypy+pytest green, rules 100% |
| 7 | Bot UX | pass | /cancel, clearer /start, upstream errors |

## Deferred to Pass 2

- Bulk `approvedAnnouncement` to cut disclosure latency at scale
- Lower default poll interval under polite rate budget
- Automated dual-poller kill test
- Verify live announcement deep-link UX on cse.lk
