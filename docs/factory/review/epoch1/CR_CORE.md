# CR_CORE — Epoch 1 adversarial code review (CORE)

**Reviewer role:** Adversarial CORE CR (implementation, not catalog)  
**Scope:** `chime/rules.py`, `chime/adapters/cse.py`, `tests/test_disclosure_rules.py`, `tests/test_adapters_normalize.py`  
**Also checked:** `tests/test_adapters_circuit.py` (WS-017 companion), sample payloads under `docs/sample_responses/`  
**Closing commit under review:** `2c2e18f` (`fix(core): disclosure created_at fail-closed; date parse; circuit-open`)  
**Date:** 2026-07-11  
**Checks:** `created_at` fail-closed · `dateOfAnnouncement` parse edges · `CircuitOpenError` re-raise · naive/aware TZ · silent bugs · missing tests

---

## Verdict

**PASS WITH DEBT — WS-002 and WS-017 are honestly closed; WS-001 parse path is real but gate semantics are not “correct `published_at`.”**

No critical defect in the four focus files. Fail-closed on missing `rule.created_at` and circuit-open re-raise are implemented and unit-tested. Remaining issues are **medium** gate skew / semantic mismatch on the date-only fallback, plus **minor** untested format edges and a thin poller-bound circuit regression.

Do **not** invent a reopen of WS-002 or WS-017 on this evidence. WS-001 may stay “done with MEDIUM debt” (same call as `EPOCH1_ADVERSARIAL.md`).

---

## Ranked findings

### Critical

*(none)*

WS-002 fail-closed and WS-017 re-raise are present at the cited lines and covered by targeted tests. No production flood or silent-success path remains in these files for those two workstreams.

---

### High

*(none verified in focus files)*

Prior epoch adversarial HIGHs (WS-083 / WS-009 / WS-068) live outside this CR’s file set (`notify.py`, `storage.py`, `bot.py`) and are not re-litigated here.

---

### Medium

#### M1 — `dateOfAnnouncement` stamped as UTC midnight skews the backfill gate

**Where:** `chime/adapters/cse.py:136-148` (`_parse_date_of_announcement`), used at `204-206`

**What shipped:** `strptime(...).replace(tzinfo=UTC)` → date-only at **00:00:00 UTC**. Docstring admits “UTC midnight.” Sample CSE strings are Colombo-facing calendar dates (`"30 Jun 2026"` in `docs/sample_responses/getAnnouncementByCompany.json`).

**Concrete false positive (backfill fire):**

| Step | Value |
|---|---|
| Rule `created_at` | `2026-06-29 20:00 UTC` (early Jun 30 SLT) |
| Actual portal time | `2026-06-30 00:30 SLT` = `2026-06-29 19:00 UTC` (**before** rule) |
| Payload | `createdDate=null`, `dateOfAnnouncement="30 Jun 2026"` |
| Normalized | `published_at=2026-06-30 00:00:00+00:00` |
| Gate | `published > created` → **fires** historical filing |

**Concrete false negative (silent miss):** Rule created `2026-06-30 05:00 UTC`; same-day afternoon filing with only the date string → midnight UTC ≤ created → **never alerts**.

**Why MEDIUM not HIGH:** All checked sample rows carry a non-null `createdDate` (ms path preferred at `201-206`). Flood/miss only hits the null-`createdDate` fallback. Undated→epoch fail-closed still holds (`test_announcement_undated_still_epoch_fail_closed`).

**Fix direction:** Stamp as `Asia/Colombo` midnight then `.astimezone(UTC)`, or treat date-only as “unknown time” and fail-closed for gate purposes while still storing a date for display — product choice.

---

#### M2 — Sample semantics: `dateOfAnnouncement` is not portal publish day

**Where:** `chime/adapters/cse.py:199-206` fallback; evidence in `docs/sample_responses/getAnnouncementByCompany.json`

**Fact (not invented):** One sample row has `dateOfAnnouncement: "26 Jun 2026"` with `createdDate: 1782801386000` → `2026-06-30 06:36:26 UTC` / `12:06 SLT`. The string lags the portal `createdDate` by **four calendar days**.

**Concrete silent miss if `createdDate` were null:**

| Field | Result |
|---|---|
| Prefer `createdDate` (current, when present) | `2026-06-30…` → fires for a rule created `2026-06-28` |
| Fallback to parsed DOA only | `2026-06-26 00:00 UTC` → `published <= created` → **no fire** |

So even a “correctly parsed” DOA string can under-date a real portal appearance. WS-001 AC (“yields correct `published_at`”) is only half-met: the string parses, but it is the wrong clock for the disclosure gate when CSE omits `createdDate`.

**Test gap:** No fixture asserts behavior when DOA calendar ≠ a synthetic “would-have-been” publish day; only happy `"30 Jun 2026" → Jun 30 UTC midnight`.

---

#### M3 — WS-017 adapter re-raise is proven; poller disclosure×circuit pairing is not

**Where:** `chime/adapters/cse.py:307-317` (`_guarded`), `414-415`, `427-428`; tests in `tests/test_adapters_circuit.py:14-32`

**What is solid:** Pre-`2c2e18f` code swallowed `CircuitOpenError` → `[]` on both announcement fetches. That is gone. Unit tests open the breaker (`fail_max=1` + `record_failure`) and assert `pytest.raises(CircuitOpenError)`.

**Residual:** No test sets `fetch_announcements_for_symbol = AsyncMock(side_effect=CircuitOpenError(...))` on a `Poller` with active disclosure rules and asserts `disclosure_poll_ok is False` / `last_tick_ok is False`. Existing poller coverage uses `RuntimeError("html error page")` (`tests/test_poller_resilience.py`) or price-leg circuit-open only. If a future change catches `CircuitOpenError` specially and maps it to success while leaving other `Exception`s as failure, adapter tests still pass and the WS-017 failure mode returns.

**Severity:** MEDIUM as a **regression hole**, not a current live bug (poller `except Exception` already sets `any_failure=True` for `CircuitOpenError`).

---

### Minor

#### m1 — Declared DOA formats untested beyond `"30 Jun 2026"`

**Where:** `chime/adapters/cse.py:129-133`; tests `tests/test_adapters_normalize.py:91-125`

Code lists `%d %B %Y` (`"30 June 2026"`) and `%Y-%m-%d`. Suite only exercises `%d %b %Y`, `None`, and `"not-a-date"`. Empty/whitespace strings take the epoch path in code (`140-142`) with no test.

**Failure scenario:** Format regression that breaks only `"2026-06-30"` or full-month strings → silent epoch → miss; CI stays green.

---

#### m2 — Naive→UTC assumption is unstated product contract

**Where:** `chime/rules.py:21-25` (`_as_utc_aware`); tests `tests/test_disclosure_rules.py:117-138`

Naive inputs get `replace(tzinfo=UTC)`. That prevents `TypeError` (WS-002 AC met) and is consistent **if** every naive value is already UTC wall time. A naive Colombo-local `created_at` from a misconfigured driver / `fromisoformat` without offset would be shifted five hours thirty minutes in the gate.

Live path: `alert_rules.created_at` is `TIMESTAMPTZ`; asyncpg typically returns aware. Risk is hand-built rules / string coerce in `storage._row_to_rule`, not normal DB reads.

**Missing test:** Aware non-UTC `created_at` (e.g. `+05:30`) vs UTC `published_at` — `astimezone(UTC)` is implemented, never asserted.

---

#### m3 — Epoch `published_at` never fires — true, untested in rules suite

Adapter tests lock `1970-01-01` for undated rows. `evaluate_disclosure_rules` with epoch `published_at` + normal `created_at` is not in `test_disclosure_rules.py` (QUALITY WS-074 still open for that case). Behavior is correct by `published <= created`; lock it to stop a future “helpful” change that special-cases epoch.

---

#### m4 — `_ms_to_dt(None) → now()` footgun remains

**Where:** `chime/adapters/cse.py:123-126`

Announcement path no longer calls `_ms_to_dt(None)` (`createdDate is not None` guard). Helper still returns wall-clock now on `None`. Any future caller that passes null ms reintroduces the PASS2 flood. Prefer raising or returning epoch inside `_ms_to_dt`.

---

#### m5 — `createdDate=0` prefers epoch over a parseable DOA

**Where:** `chime/adapters/cse.py:201-206`

`if row.createdDate is not None` treats `0` as present → `1970-01-01`, ignoring `dateOfAnnouncement="30 Jun 2026"`. No CSE sample uses `0`; if the API ever sends `0` as a null sentinel, result is silent miss (fail-closed), not flood. Document or treat `<=0` as missing.

---

## Checklist results

| Check | Result |
|---|---|
| **`created_at` fail-closed** | **PASS.** `rules.py:210-212` skips when `created_at is None`; `test_missing_rule_created_at_fail_closed` locks it. Equality / before / after covered. |
| **`dateOfAnnouncement` parsing** | **PARTIAL.** Primary `"30 Jun 2026"` works; undated/unparseable → epoch. Gate uses UTC midnight (M1); DOA ≠ portal day in samples (M2); extra formats untested (m1). |
| **`CircuitOpenError` re-raise** | **PASS** at adapter (`cse.py` announcement methods + `test_adapters_circuit.py`). Poller×disclosure specific regression missing (M3). |
| **Timezone naive/aware** | **PASS** for TypeError; naive treated as UTC (m2 residual). |
| **Silent bugs** | No current swallow-`[]` on circuit-open. Residual silent miss paths are date-only gate skew (M1/M2), not flood. |
| **Missing tests** | See M3, m1, m2, m3. |

---

## What survives (do not reopen)

| WS | Evidence |
|---|---|
| **WS-002** | `created_at is None` → zero events; naive/aware pairs do not raise; equality boundary tested. |
| **WS-017** | `except CircuitOpenError: return []` removed from both announcement fetch methods; breaker-open unit tests raise. |
| **WS-001 (parse half)** | Null `createdDate` + `"30 Jun 2026"` → dated `published_at`; neither/unparseable → epoch, not `now()`. |

---

## Recommended follow-ups (not blockers to keep WS-002/017 closed)

1. Stamp DOA as Colombo midnight (or fail-closed date-only for the gate) — closes M1.  
2. Add poller test: disclosure rules + `CircuitOpenError` on announce fetch → `disclosure_poll_ok is False` — closes M3.  
3. Parametrize DOA fixtures: full month, ISO date, whitespace, empty — closes m1.  
4. Rules test: epoch `published_at` never fires — closes m3.

---

## Scorecard impact (CORE slice only)

| Claim | This CR |
|---|---|
| WS-002 done | Affirm |
| WS-017 done | Affirm (add M3 test debt) |
| WS-001 done | Affirm parse + undated fail-closed; **MEDIUM debt** on “correct `published_at`” for gate use |
