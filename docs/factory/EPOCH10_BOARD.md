# Epoch 10 Board — API completeness + CSRF audit

**Status:** OPEN

Fence-legal only. Theme: contract gaps vs `API_CONTRACT_V1.md`, CSRF audit
tests, thin dash polish. No portfolio P&L / screener / TA / payments.

| ID | Item | Status |
|---|---|---|
| E10-Q01 | CSRF header≠cookie mismatch → 400 csrf_failed unit | DONE |
| E10-Q02 | Logout happy-path clears session+CSRF cookies (RUN_WEB) | DONE |
| E10-Q03 | Contract order: missing session → 401 before CSRF check (doc+test) | DONE |
| E10-D01 | Empty disclosures state on symbol detail | DONE |
| E10-D02 | Alerts history empty copy when no fires | DONE |
| E10-O01 | Makefile/factory-verify smoke for portfolio_sum.py | DONE |
| E10-A01 | API_CONTRACT note: 401 beats csrf_failed when both would apply | DONE |
| E10-C01 | Adapter polite backoff / timeout error logged (unit) | DONE |

Never farm. One concern per commit.
