# Factory Loop Pass L01

**Branch:** `cursor/factory-loop-cb19`  
**HEAD at verify:** `35e27d4a3f49c7d4831e14b273cfbcdd9323c3dd`  
**Date:** 2026-07-11  

## Theme commits (accepted)

| Concern | Commit subject |
|---|---|
| Dead-letter unsent after 5 attempts | `fix(core): dead-letter unsent alerts after 5 attempts` |
| DOA Asia/Colombo midnight | `fix(core): dateOfAnnouncement as Asia/Colombo midnight` |
| `createdDate <= 0` missing | `fix(core): treat createdDate<=0 as missing timestamp` |
| Bot cmd rate limit | `fix(bot): per-user command rate limit` |
| Health 503 + py312 | `test(ops): health 503 pin; align tooling to py312` |
| CSRF bootstrap freeze | `docs(dash): freeze CSRF bootstrap (no logout exemption)` |
| Makefile / compose DX | `ops(dx): make help/up/down; README compose blurb` |
| Lock cleanup + health redact | `fix(ops): advisory lock cleanup; redact remote health` |

## Adversarial REFUTE of L01 claims

All seven L01 themes **PASS** in code (no hard refute). Residuals deferred to L02+.

## Verify proof (post-L01 HEAD — before L02 edits)

Initial verify hit ruff I001 in `tests/test_bot_rate_limit.py` (fixed in L02). Full green verify moved to L02 after claim-disarm fix.

## Findings carried to L02

| ID | Sev | Summary |
|---|---|---|
| CORE-001 | HIGH | `_claim_and_send` returned False on send fail → disarm skipped |
| OPS-HEALTH-001 | HIGH | bot-only `/health` never refreshed from DB |
| NOTIFY-001 | MEDIUM | RetryAfter retry dropped `disable_web_page_preview` |
| CORE-008 | MINOR→fix | Settings rate limit not passed into `build_application` |
| CORE-006 | MINOR→fix | `_ms_to_dt(None)` used `now()` |
| TEST-RA-001 | MEDIUM | RetryAfter sleep cap untested |
| OPS-MAKE-001 | MEDIUM | `make test-unit` missing |

## Stop criteria

Not converged (findings > minor remained). Continue L02.
