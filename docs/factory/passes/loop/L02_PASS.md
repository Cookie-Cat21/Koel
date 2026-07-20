# Factory Loop Pass L02

**Branch:** `cursor/factory-loop-cb19`  
**HEAD at verify:** (see commit after this report lands)  
**Date:** 2026-07-11  

## Closed from L01 adversarial

| ID | Sev | Fix commit |
|---|---|---|
| CORE-001 | HIGH | `1780b86` disarm after claim even when send fails |
| OPS-HEALTH-001 | HIGH | `306f418` bot-mode health from DB |
| NOTIFY-001 / TEST-RA-001 | MEDIUM | `02d5a41` kwargs + sleep-cap test |
| CORE-006 | MINOR | `ebf001f` `_ms_to_dt(None)` → epoch |
| CORE-008 | MINOR | included in `306f418` Settings → `build_application` |
| OPS-MAKE-001 | MEDIUM | `1fcc8fb` `make test-unit` + compose `--wait` |

## Verify proof

```
ruff check koel tests  → All checks passed
mypy koel              → Success: no issues found in 15 source files
pytest -q               → green (3 skipped DB tests without DATABASE_URL)
rules cov               → 100%
```

## Deferred (> minor residual backlog for L03+)

| ID | Sev | Notes |
|---|---|---|
| CORE-002 | MEDIUM | Same-minute same-price re-cross event_key collision |
| CORE-003 | MEDIUM | DOA-only publish lag vs createdDate |
| CORE-004 | MEDIUM | Lock held across Telegram sends / disclosure sleeps |
| CORE-005 | MEDIUM | Shutdown does not await in-flight tick |
| TEST-DPOL-001 | HIGH (test) | Concurrent Poller.run_once dual-lock not proven |
| TEST-DL-001 | HIGH (test) | Dead-letter DB path unproven |
| CI-INT-001 | MEDIUM | Integration job can pass with all DB tests skipped |
| OPS-COV-001 | MEDIUM | Coverage gate is rules-only |

## Convergence

Not yet — residuals above minor remain. L03 = adversarial on L02 + pick next highest.
