# Wave 89 — CSE HTTP status/CT/pace soft-accepts

**Verdict:** FIXED (medium+)  
**Date:** 2026-07-13  
**HEAD reviewed:** `c578d60a` (post w87 CLEAN; CSE fail-closed + `tests/test_wave89_medium_bugs.py` present)  
**Branch:** `cursor/tijori-cse-phase1-e44e`

## Findings (medium+)

1. **`CSEClient._request` status_code** — `True >= 400` is False, so a
   poisoned bool status soft-accepted as HTTP success mid poll (unlike CDN
   `int(True)==1` shape; new surface after w83 CDN close).
2. **`content-type`** — non-string CT mocks used to throw / mis-classify on
   `"json" not in …` before the non-JSON gate.
3. **`min_interval_seconds`** — `float(True)==1.0` soft-accepted a bool as a
   1s CSE pace.
4. **`_retryable`** — bool/non-int status must not classify retries.

## Fix

`koel/adapters/cse.py`: isinstance-guard status (raise on invalid), CT
string-guard, ctor rejects bool/non-finite interval, `_retryable` status
narrow. Pin: `tests/test_wave89_medium_bugs.py`.

## Gate

`DATABASE_URL= pytest -m 'not integration' --cov=koel --cov-fail-under=100`
green (100% stmts / 0 miss).
