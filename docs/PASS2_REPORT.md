# Stage B — Pass 2 report

## Findings fixed

From `docs/PASS2_AUDIT.md`:

1. **Critical — session advisory lock + pool** — lock now holds the pooled connection until unlock; proven by `tests/test_advisory_lock.py` (second Storage cannot acquire).
2. **High — health green while lock-starved** — lock skip sets `last_tick_ok=False`, `lock_held_skip=True`, `last_error=poll_lock_held`.
3. **Medium — null `createdDate` flood** — missing timestamps map to epoch 1970, not `now()`.
4. **Medium — disclosure-leg health** — `last_tick_ok` false when disclosure rules exist and disclosure poll fails.
5. **Medium — disarm after claim** — disarm on successful claim even if Telegram send failed (unsent retry delivers).

## Proof

```
ruff / mypy → clean
pytest → 58+ passed, chime.rules 100%
test_advisory_lock_blocks_second_holder → pass (Neon)
```

## Quality bar

| Item | Score |
|---|---|
| Alert correctness | pass |
| Zero dup / zero loss | pass (real session lock) |
| Latency p95 &lt; 5s claim→send | partial (instrumented; CSE→TG = poll interval) |
| Resilience | pass |
| Ops | pass |
| Code quality | pass |
| Bot UX | pass |

## Deferred (intentional / minor)

- Bulk `approvedAnnouncement` for large watchlists
- Sub-5s CSE→Telegram would require much faster polling + CSE load budget
- Live deep-link UX verification on cse.lk UI
