# Factory Loop Pass L04

**Branch:** `cursor/factory-loop-cb19`  
**Date:** 2026-07-11  

## Closed (HIGH/MEDIUM)

| ID | Commit |
|---|---|
| H2 disclosure crash window | `188883a` upsert + always evaluate |
| H3 send-OK mark fail (claim path) | `2b8a317` |
| M1 cancel still retried | `a9f73c1` `ar.active` filter |
| M2 non-atomic unwatch | `1c084a0` `unwatch_symbol` |
| TEST-INT-001 kill_restart | `4f21a2e` |

## Notes

H1 (late subscriber for already-ingested with `published_at <= created_at`) is **by design** backfill gate — not a bug.
