# Wave 1 — CORE lane workstreams (WS-001 … WS-020)

**Lane:** CORE (`chime/`, `db/`, `tests/` — non-UI)  
**Source:** Stage A baseline in [FINAL_REPORT.md](../../FINAL_REPORT.md), deferred backlog, Pass 1–4 audits, and current spine code.  
**Fence:** No portfolio / screener / TA / payments. Planning only — no product implementation in this file’s PR wave.

Each workstream is a real improvement toward alert correctness, zero-dup / zero-loss, disclosure fidelity, adapter resilience, or bot UX polish.

---

## WS-001 — Parse `dateOfAnnouncement` when `createdDate` is null

- **id:** WS-001
- **title:** Parse `dateOfAnnouncement` when `createdDate` is null
- **why it matters:** Undated CSE rows currently fail-closed to epoch (or historically stamped “now”), so real announcements can be silently never-alerted or incorrectly gated.
- **acceptance criterion:** Fixture with `createdDate=null` + parseable `dateOfAnnouncement` yields correct `published_at`; undated-with-neither still fails closed (no Telegram flood); unit tests cover both.
- **estimated commits:** 2
- **dependencies:** none
- **risk:** med

## WS-002 — Fail-closed disclosure eval when `rule.created_at` is missing

- **id:** WS-002
- **title:** Fail-closed disclosure eval when `rule.created_at` is missing
- **why it matters:** `created_at is None` currently skips the backfill filter and can fire every newly inserted historical disclosure.
- **acceptance criterion:** Rule with `created_at=None` + any disclosure → zero fireable events; UTC-aware normalize before compare; naive/aware inputs never raise `TypeError`.
- **estimated commits:** 1
- **dependencies:** none
- **risk:** low

## WS-003 — Bulk `approvedAnnouncement` path for large watchlists

- **id:** WS-003
- **title:** Bulk `approvedAnnouncement` path for large watchlists
- **why it matters:** Per-symbol `getAnnouncementByCompany` + sleep makes disclosure latency scale with watchlist size and burns CSE budget.
- **acceptance criterion:** With ≥20 watched symbols that have disclosure rules, one poll cycle uses bulk feed (plus name/symbol mapping) without N sequential CSE calls; rate-limit stays polite; existing per-symbol path remains fallback.
- **estimated commits:** 4
- **dependencies:** WS-001
- **risk:** high

## WS-004 — Company-name → symbol mapping for bulk disclosures

- **id:** WS-004
- **title:** Company-name → symbol mapping for bulk disclosures
- **why it matters:** `approvedAnnouncement` often has null `symbol`; without a reliable name map, bulk ingest cannot attribute filings to watched tickers.
- **acceptance criterion:** Sample CSE rows with null symbol but known company name map to the correct watchlist symbol; ambiguous/unmatched rows are logged and skipped (no wrong-symbol alert).
- **estimated commits:** 3
- **dependencies:** WS-003
- **risk:** high

## WS-005 — Verify and harden disclosure deep-link URLs

- **id:** WS-005
- **title:** Verify and harden disclosure deep-link URLs
- **why it matters:** Alert messages use `cse.lk/announcements#announcementId`; if the fragment does not open the filing, users get a dead or useless link — the disclosure alert’s primary value.
- **acceptance criterion:** Documented verified URL pattern (or alternate PDF/detail URL from CSE payload) used in `announcement_to_disclosure`; unit test asserts constructed URL shape; manual probe note in `docs/` for live fragment behavior.
- **estimated commits:** 2
- **dependencies:** none
- **risk:** med

## WS-006 — Dead-letter unsent alerts after N permanent Telegram failures

- **id:** WS-006
- **title:** Dead-letter unsent alerts after N permanent Telegram failures
- **why it matters:** Blocked users / permanent Telegram errors currently retry forever every poll cycle, burning API quota and log noise without delivery hope.
- **acceptance criterion:** After N consecutive failures (configurable), row is marked dead-lettered / abandoned and excluded from `unsent_alerts`; new alerts for other users still send; pytest covers permanent vs transient failure paths.
- **estimated commits:** 3
- **dependencies:** none
- **risk:** med

## WS-007 — Disarm price rules on successful unsent retry

- **id:** WS-007
- **title:** Disarm price rules on successful unsent retry
- **why it matters:** Claim-then-failed-send leaves `armed=True`; retry delivery never disarms, weakening the armed safety net if snapshot history is reordered or compacted later.
- **acceptance criterion:** Flaky send → claim with `message_sent=False` → retry success → rule `armed=False` until price rearm; exactly one Telegram; no sticky duplicate under sticky-above fixture.
- **estimated commits:** 2
- **dependencies:** none
- **risk:** med

## WS-008 — Same-minute rearm + identical-price `event_key` collision

- **id:** WS-008
- **title:** Same-minute rearm + identical-price `event_key` collision
- **why it matters:** After a cross, rearm, and same-minute re-cross at the same print, the minute+price `event_key` silently drops a legitimate second alert (dual-poller tradeoff made permanent).
- **acceptance criterion:** Synthetic same-minute re-cross after rearm delivers exactly one *new* alert; dual-poller same-tick still dedupes to one claim (no double Telegram).
- **estimated commits:** 2
- **dependencies:** none
- **risk:** high

## WS-009 — Concurrent identical `/alert` IntegrityError handling

- **id:** WS-009
- **title:** Concurrent identical `/alert` IntegrityError handling
- **why it matters:** Double-tap / parallel creates hit the partial unique index and can 500 the handler instead of returning the existing active rule.
- **acceptance criterion:** Two parallel identical `create_alert_rule` calls → exactly one active row; both bot replies succeed with a valid alert id; no unhandled IntegrityError in logs.
- **estimated commits:** 2
- **dependencies:** none
- **risk:** low

## WS-010 — Advisory-lock pool footgun (`max_size=1` / held connection)

- **id:** WS-010
- **title:** Advisory-lock pool footgun (`max_size=1` / held connection)
- **why it matters:** Session lock holds a pooled connection for the whole tick; `max_size=1` deadlocks other Storage ops; low pools still starve bot handlers during long disclosure legs.
- **acceptance criterion:** Config enforces `max_size >= 2` (or dedicated lock connection); documented; test or startup check fails fast on unsafe pool size; sole poller never self-starves on lock.
- **estimated commits:** 2
- **dependencies:** none
- **risk:** med

## WS-011 — Automated dual-poller kill / leader-election test

- **id:** WS-011
- **title:** Automated dual-poller kill / leader-election test
- **why it matters:** Zero-dup / zero-loss rests on sticky advisory lock + claim semantics, but CI currently skips real dual-holder proof without optional `DATABASE_URL`.
- **acceptance criterion:** With `DATABASE_URL` set (and a documented CI job or compose service), two Storage/poller holders prove exactly one cycle runs per tick and unlock leaves no orphaned `pg_locks` advisory row; kill mid-cycle still delivers ≤1 Telegram via claim+retry.
- **estimated commits:** 3
- **dependencies:** WS-010
- **risk:** med

## WS-012 — `both` SIGTERM polish + honest `tick --force`

- **id:** WS-012
- **title:** `both` SIGTERM polish + honest `tick --force`
- **why it matters:** `_run_both` ignores SIGTERM (unlike `run_poller_forever`); `tick` uses `force or True`, so market-hours gating is dead and `--force` is a lie.
- **acceptance criterion:** SIGTERM/SIGINT stops `both` cleanly (bot + poller + storage closed); `tick` without `--force` outside hours skips work; `tick --force` runs once regardless of hours.
- **estimated commits:** 2
- **dependencies:** none
- **risk:** low

## WS-013 — Honest `/unwatch` when orphan rules exist

- **id:** WS-013
- **title:** Honest `/unwatch` when orphan rules exist
- **why it matters:** If watchlist row is gone but active rules remain, `/unwatch` deactivates rules then claims the symbol “wasn’t on your watchlist.”
- **acceptance criterion:** Orphan active rules + `/unwatch SYMBOL` → rules inactive + reply reports deactivated count; neither watch nor rules → single “wasn’t watching” reply.
- **estimated commits:** 1
- **dependencies:** none
- **risk:** low

## WS-014 — Bot UX: `/start` ≤3 lines + tighter help surface

- **id:** WS-014
- **title:** Bot UX: `/start` ≤3 lines + tighter help surface
- **why it matters:** Factory bar requires one-round-trip commands and `/start` ≤3 lines; current START+HELP dumps a long command list that buries the product pitch and NFA line.
- **acceptance criterion:** `/start` reply ≤3 lines (incl. disclosure-needs-explicit-alert honesty + NFA); full command list available via `/help` only; pytest/parse snapshot asserts line budget.
- **estimated commits:** 2
- **dependencies:** none
- **risk:** low

## WS-015 — `/myalerts` shows armed / fire state + cancel hint

- **id:** WS-015
- **title:** `/myalerts` shows armed / fire state + cancel hint
- **why it matters:** Users cannot tell a disarmed sticky-above alert from an armed one, so they think Quiverly is broken after a fire until price rearms.
- **acceptance criterion:** `/myalerts` lists id, type, threshold, and armed/waiting-rearm for price rules; includes one-line `/cancel ALERT_ID` hint; empty state unchanged.
- **estimated commits:** 1
- **dependencies:** none
- **risk:** low

## WS-016 — Bare-ticker normalization (`.N0000` / common CSE forms)

- **id:** WS-016
- **title:** Bare-ticker normalization (`.N0000` / common CSE forms)
- **why it matters:** Users type `JKH` while CSE quotes `JKH.N0000`; lookup fails as not-found instead of resolving the common share class.
- **acceptance criterion:** `/watch JKH` and `/alert JKH above X` resolve to the canonical CSE symbol when uniquely mappable; ambiguous multi-class tickers ask the user to disambiguate; no false positive on unknown roots.
- **estimated commits:** 3
- **dependencies:** none
- **risk:** med

## WS-017 — Adapter: disclosure circuit-open must not look like empty success

- **id:** WS-017
- **title:** Adapter: disclosure circuit-open must not look like empty success
- **why it matters:** `fetch_announcements_for_symbol` returns `[]` on `CircuitOpenError`, so the poller can treat a hard outage as “no new filings” and keep health green when disclosure rules exist.
- **acceptance criterion:** Circuit open / transport failure propagates or returns a typed failure; `_poll_disclosures` sets `disclosure_poll_ok=False` and degrades health when disclosure rules are active; empty list only means “HTTP OK, zero rows.”
- **estimated commits:** 2
- **dependencies:** none
- **risk:** med

## WS-018 — Adapter resilience: partial bulk + schema drift logging

- **id:** WS-018
- **title:** Adapter resilience: partial bulk + schema drift logging
- **why it matters:** CSE payload drift or a bad announcement row must not abort the whole disclosure leg the way whole-response validation once killed price polls.
- **acceptance criterion:** Fixtures with 1 malformed + N valid announcement rows → N disclosures returned, malformed logged with endpoint+snippet; top-level schema break still fails the endpoint (circuit-counted) without killing the poller process.
- **estimated commits:** 2
- **dependencies:** WS-003
- **risk:** med

## WS-019 — Daily-move day-boundary and `previous_close` edge cases

- **id:** WS-019
- **title:** Daily-move day-boundary and `previous_close` edge cases
- **why it matters:** Move alerts key by calendar day and may derive `%` from `previous_close`; overnight / first tick / null `change_pct` edges can miss or double-count across Colombo midnight.
- **acceptance criterion:** Unit tests for: first observation baseline (no fire), cross within day (one fire), second cross same day (suppressed), new Colombo day allows new fire, null `change_pct` with valid `previous_close` computes correctly, null both → no fire.
- **estimated commits:** 2
- **dependencies:** none
- **risk:** med

## WS-020 — Poll only disclosure symbols that have disclosure rules

- **id:** WS-020
- **title:** Poll only disclosure symbols that have disclosure rules
- **why it matters:** Disclosure leg currently iterates every watched symbol even when only price alerts exist, amplifying CSE load and tick duration for no product gain.
- **acceptance criterion:** Watchlist of price-only symbols → zero announcement HTTP calls; symbols with active disclosure rules still polled; health `disclosure_poll_ok` stays true when no disclosure rules exist.
- **estimated commits:** 1
- **dependencies:** none
- **risk:** low

---

## Dependency sketch (planning)

```
WS-001 ─┐
        ├─► WS-003 ─► WS-004
        │         └─► WS-018
WS-010 ─► WS-011
(others independent)
```

## Suggested first CORE implementation pass (after plan merges)

Prioritize deferred FINAL_REPORT + correctness: **WS-001, WS-002, WS-006, WS-007, WS-009, WS-012, WS-013, WS-017** (fits ≤8 concurrent agents if file ownership is disjoint).
