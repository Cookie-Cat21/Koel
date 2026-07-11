# Factory Loop Pass L07

**Branch:** `cursor/factory-loop-cb19`  
**HEAD:** (see git after commit)  
**Date:** 2026-07-11  

## Adversarial outcome

NOT_CLEAN initially — 2–3 new MEDIUMs.

## Closed this pass

| Finding | Fix |
|---|---|
| Post-CORE-004 still `block_on_retry_after=False` | `__main__` wrappers → `True` |
| Off-hours skip `_retry_unsent` | `_retry_unsent_with_lock` on closed market |
| Same-tick dup if mark+DL fail | `_delivered_ok_ids` skip in `_retry_unsent` |

## ACCEPT-DEFER (unchanged)

CORE-003, CORE-005, OPS-COV-001, silent DL UX, pool contention, tradeSummary miss (ops signal), claim/disarm non-transactional crash window.

## Convergence

Need CLEAN × 2 consecutive after this pass.
