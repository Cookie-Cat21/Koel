# R1 — Adversarial review: WAVE1_CORE

**Reviewed:** [WAVE1_CORE.md](../workstreams/WAVE1_CORE.md)  
**Against:** [COMMIT_FACTORY.md](../COMMIT_FACTORY.md), [METRICS.md](../METRICS.md), [FINAL_REPORT.md](../../FINAL_REPORT.md), `chime/poller.py`, `chime/rules.py`, plus adapter/bot/CLI spot-checks  
**Date:** 2026-07-11  
**Verdict:** **needs rework**

Catalog is mostly real deferred backlog, not filler — but it ships one **factually obsolete** workstream, overstates one “critical” path the DB already prevents, clusters two bulk-disclosure items that cannot ship independently, violates METRICS commit sizing, and proposes a Pass-1 set that includes the obsolete item. Fix the catalog before implementation Pass 1.

---

## 1. Verdict

**needs rework** — not “scrap and rewrite.” Keep ~15/20. Replace/rewrite the weak slots below; do not start Pass 1 from the “Suggested first CORE” list as written.

Stage A already CONVERGED (Pass 3–4). CORE Wave 1 should be **residual defects + scale**, not a second Stage A. Several WS are correct; the catalog’s integrity is undermined by WS-007’s false premise and by WS-003/004/019 gating problems.

---

## 2. Ranked improvements (max 15)

### Critical

1. **Drop or rewrite WS-007 — premise is false on current code.**  
   `poller._evaluate_price_snaps` disarms **after successful claim**, even when Telegram leaves `message_sent=False` (explicit comment + `set_rule_armed(..., False)`). `_retry_unsent` only marks sent. FINAL_REPORT Pass 2 already landed “disarm-after-claim intent.” Shipping WS-007 as stated farms a ghost fix.

2. **Rewrite WS-003 AC — it embeds WS-004.**  
   AC requires “bulk feed (plus name/symbol mapping)” while WS-004 is a separate 3-commit dependency. That is one cluster (METRICS §5), not two parallelizable WS. Either merge or strip mapping from WS-003 AC.

3. **Cap estimated commits to `{1,2,3}`.**  
   WS-003 (`4`) violates METRICS. Inflates `remaining_proper` and invites micro-commit farming.

### High

4. **Reorder: WS-020 before WS-003.**  
   `_poll_disclosures` iterates **every** watched symbol with per-call sleep even when `disclosure_rules` is empty. Cheap fix; reduces CSE load without inventing bulk ingest. Doing bulk first optimizes the wrong path.

5. **WS-002 severity honesty.**  
   Bug in `evaluate_disclosure_rules` is real (`created_at is None` skips backfill filter). But `alert_rules.created_at` is `TIMESTAMPTZ NOT NULL`. Live flood requires a broken mapper / hand-built rule, not normal Storage reads. Keep WS; stop treating it as production-hot without that caveat. Gate on: engine fail-closed + UTC-aware compare tests.

6. **WS-008 needs a product decision gate, not a dual AC.**  
   FINAL_REPORT labels same-minute rearm+identical-price collision an **intentional** dual-poller tradeoff. AC demands both “new alert after rearm same minute” and “dual-poller same-tick still one claim” without specifying the new key design. Ungated → implementers will thrash or break bar #2.

7. **WS-019 is mostly already proven — rewrite to the real gap.**  
   `tests/test_rules_move.py` already covers first-obs baseline, cross, same-day suppress via `move_fired_keys`, `previous_close` derivation, null both. Remaining issue: `_event_key_move` uses `snapshot.ts.date()` and CSE `ts` is **UTC** (`adapters/cse.py`), so Colombo calendar day near midnight is wrong. Current AC reads like re-running Stage A.

8. **Replace Suggested Pass-1 list.**  
   Listed set includes obsolete WS-007 and skips WS-020 (highest ROI latency/resilience cheap win). See §5.

### Medium

9. **WS-017 is accurate and under-prioritized relative to bulk.**  
   `fetch_announcements_for_symbol` / `fetch_approved_announcements` swallow `CircuitOpenError` → `[]`. Poller treats that as success per symbol (`any_failure` stays false). Silent disclosure miss while health can stay green when rules exist. Fix before WS-003.

10. **WS-011 ∩ QUALITY WS-065 — declare ownership.**  
    Dual-poller kill/claim proof appears in both CORE and QUALITY. One lane owns the integration test; the other links. Duplicate catalog rows inflate backlog without double value.

11. **WS-006 depends on failure taxonomy that does not exist.**  
    `notify.send_message` returns bool only; Forbidden/blocked vs RetryAfter/NetworkError are collapsed. Dead-letter “after N permanent failures” is ungated until permanent vs transient is classified. Split or prepend a notify-classification WS.

12. **WS-012 is two concerns.**  
    `_run_both` SIGTERM gap and `force=args.force or True` are both real (`__main__.py`), but one concern per commit / preferably one WS or an explicit 2-commit cluster. As written, agents will bundle unrelated CLI fixes.

13. **WS-016 comment-lie in bot.**  
    `normalize_symbol` comments “accept bare ticker” but only uppercases; no `.N0000` resolve. WS is valid; AC must specify lookup strategy (try `SYM.N0000` then fail / stock table) or it stays vague.

### Minor

14. **WS-005 soft gate.**  
    “Manual probe note in docs/” alone does not meet proper-commit bar unless URL shape change + unit test land. Keep probe as AC annex, not the deliverable.

15. **WS-014 line-budget is real but low urgency.**  
    `/start` currently appends full `HELP_HINT` (16 lines combined). Factory bar #7 is unmet. Fine for Pass 2+; not spine-critical.

---

## 3. WS ids — duplicates / vague / ungated / out-of-fence

| Class | IDs | Notes |
|---|---|---|
| **Obsolete / false premise** | WS-007 | Disarm-after-claim already in `poller.py`; not a remaining defect |
| **Duplicate / overlapping clusters** | WS-003↔WS-004 | Mapping required by 003 AC and owned by 004 |
| **Cross-lane duplicate** | WS-011 ↔ QUALITY WS-065 | Same dual-poller proof |
| **Near-duplicate of done tests** | WS-019 (as written) | Overlaps existing move tests + QUALITY WS-064 |
| **Vague** | WS-016, WS-018, WS-019 (day-boundary) | Mapping source / drift scope / UTC vs Colombo unspecified |
| **Ungated** | WS-008, WS-006 (sans taxonomy), WS-003 (sans map strategy), WS-011 (CI DB optional) | Need design or deps before AC is satisfiable |
| **Out-of-fence** | *(none)* | No portfolio / screener / TA / competitor scrape |
| **Commit-size fence break** | WS-003 | `estimated commits: 4` vs METRICS `{1,2,3}` |

---

## 4. Proposed splits / merges / rewrites (keep CORE = 20)

| Action | WS | Replacement / change |
|---|---|---|
| **DELETE** | WS-007 | Slot freed |
| **MERGE** | WS-003 + WS-004 → **WS-003** | Title: *Bulk `approvedAnnouncement` + company→symbol map*. AC: one poll path; unmatched logged/skipped; per-symbol fallback; commits **3** max. Drop separate WS-004 id. |
| **REWRITE** | WS-019 | Title: *Move `event_key` uses Asia/Colombo calendar day*. AC: UTC midnight ≠ Colombo midnight fixtures; existing move crossing tests remain regression-only. commits **1–2**. |
| **REWRITE** | WS-008 | Gate: written product decision (accept silent drop vs second-granularity/`rearm_seq` in key). Until signed, status=`blocked`. Do not implement in Pass 1. |
| **SPLIT** | WS-012 → keep as two-commit cluster in one WS | Commit A: honest `tick` (`force=args.force`). Commit B: SIGTERM/`both` shutdown parity with `run_poller_forever`. |
| **SPLIT dependency** | WS-006 | Prepend failure class into same WS or new slot: *Classify Telegram errors (permanent vs transient)* then dead-letter. |
| **NEW (fills WS-004 slot)** | **WS-004′** | *Notify: permanent vs transient Telegram errors* — map `Forbidden`/blocked chat → permanent; `RetryAfter`/`TimedOut`/`NetworkError` → transient; feeds WS-006. commits **2**. |
| **NEW (fills WS-007 slot)** | **WS-007′** | *CSE non-JSON / HTML-200 must fail circuit* — adapter treats HTML/empty body as upstream failure (aligns adversarial WS-086); poller health degrades. commits **2**. |
| **KEEP as-is (minor AC polish)** | WS-001, WS-002, WS-005, WS-009, WS-010, WS-011*, WS-013–WS-018, WS-020 | *WS-011: “owned by CORE; QUALITY WS-065 becomes link-only” |

**Post-rework CORE 20:**  
001, 002, **003(merged)**, **004′(notify taxonomy)**, 005, 006, **007′(HTML/non-JSON)**, 008(blocked until decision), 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, **019(rewritten)**, 020.

Dependency sketch (corrected):

```
WS-020 ──────────────┐
WS-001 ──┐           ├─► WS-003 (bulk+map)
         └───────────┘
WS-004′ ─► WS-006
WS-017 ──► (before trusting disclosure health under bulk)
WS-010 ──► WS-011
WS-008 = blocked
```

---

## 5. Top 5 CORE workstreams for implementation Pass 1

Run these first (disjoint files feasible under ≤8 agents; highest correctness / silent-fail ROI):

| Rank | WS | Why first |
|---|---|---|
| 1 | **WS-002** | Engine fail-closed for missing `created_at` + aware datetime compare — pure `rules.py`, tests only; closes backfill-flood contract hole |
| 2 | **WS-017** | Circuit-open → `[]` is a live silent disclosure miss; adapter + poller health — bar #4 |
| 3 | **WS-001** | `dateOfAnnouncement` when `createdDate` is null — undated rows currently epoch fail-closed; real filings can never alert |
| 4 | **WS-020** | Stop HTTP+sleep on price-only watchlists — one-file poller change, immediate CSE budget win, prerequisite hygiene before bulk |
| 5 | **WS-012** *(tick half)* or **WS-009** | Pick one ops/UX correctness bug: `force or True` lies; concurrent `/alert` can IntegrityError on partial unique index. Prefer **WS-012 tick fix** (trivial, ungates honest ops) **and** land **WS-009** if an 6th agent is free |

**Do not** put in Pass 1: WS-003/004 bulk (scale, after 020+017+001), WS-007 (obsolete), WS-008 (ungated), WS-011 (needs DB CI / after WS-010), WS-014–016 (UX polish).

**Reject** WAVE1_CORE’s suggested set `{001,002,006,007,009,012,013,017}` until WS-007 is removed and WS-020 is added.

---

## Code-check anchors (reviewer evidence)

| Claim | Evidence |
|---|---|
| WS-007 false | `poller.py` claim-then-disarm regardless of send ok |
| WS-017 true | `cse.py` `except CircuitOpenError: return []` on announcement fetches |
| WS-020 true | `_poll_disclosures` `for symbol in symbols` (all watched), not disclosure-rule subset |
| WS-012 true | `__main__.py` `force=args.force or True`; `_run_both` no signal handlers |
| WS-002 true (engine) / overstated (prod DB) | `rules.py` skips filter when `created_at is None`; migration `NOT NULL` |
| WS-001 true | `announcement_to_disclosure` epochs on null `createdDate`; ignores `dateOfAnnouncement` |
| WS-019 partial | move tests exist; `_event_key_move` uses UTC `snapshot.ts.date()` |

---

## Bottom line

WAVE1_CORE is a usable backlog spoiled by one dead WS, one overscoped bulk cluster, and a Pass-1 recommendation that fails its own quality bar. **Rework the five table rows in §4, then execute §5.** Do not inflate proper-commit estimates past METRICS.
