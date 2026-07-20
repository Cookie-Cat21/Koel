# Wave 1 — Adversarial catalog (WS-081 … WS-100)

**Lane:** CORE / OPS / DASH (investigation)  
**Type:** Audit / failure-scenario probes for a future pass  
**Baseline:** Stage A CONVERGE ([PASS4_AUDIT.md](../../PASS4_AUDIT.md), [FINAL_REPORT.md](../../FINAL_REPORT.md))  
**Constitution:** [COMMIT_FACTORY.md](../COMMIT_FACTORY.md)

These workstreams do **not** implement features. Each defines a concrete failure to reproduce or refute. Pass = scenario cannot occur (or is documented + mitigated). Fail = reproducible defect above minor → file a finding and schedule fix commits in an implementation wave.

`commits if fix needed`: `0` = audit-only doc/test addition sufficient; `1–5` = likely production fix commits if the probe fails.

---

## WS-081 — Market open/close inclusive boundary

| Field | Content |
|---|---|
| **id** | WS-081 |
| **title** | Market open/close inclusive boundary |
| **failure scenario** | `is_market_open` uses `open_t <= local.time() <= close_t`. At exactly `09:30:00` CSE may not yet print; at exactly `14:30:00` last prints may still arrive, or the exchange may have already stopped. Off-by-one second / inclusive close causes either a wasted poll that looks "healthy" with stale prices, or a missed final tick that never re-arms crossing rules until next day. |
| **how to probe** | Unit-test `is_market_open` at `09:29:59`, `09:30:00`, `09:30:01`, `14:29:59`, `14:30:00`, `14:30:01` Asia/Colombo on a weekday; compare against a frozen CSE fixture (or logged live sample) for whether `tradeSummary` still updates in those windows. Confirm poller skip log vs run at each boundary. |
| **pass/fail criterion** | **Pass** if documented intended semantics match exchange behavior and tests lock the boundary; **fail** if inclusive close causes post-close false alerts or open-second skip loses a real print that should fire. |
| **commits if fix needed** | 1–2 |
| **risk if unaddressed** | Silent miss of open/close prints; ops confusion when health shows "ok" but no snapshots near close. |

---

## WS-082 — Asia/Colombo has no DST (ZoneInfo honesty)

| Field | Content |
|---|---|
| **id** | WS-082 |
| **title** | Asia/Colombo has no DST |
| **failure scenario** | Host TZ or `MARKET_TZ` mis-set to a DST zone (e.g. `Europe/London`, `America/New_York`) shifts market window by 1h seasonally. Alternatively, naive UTC comparison without `ZoneInfo("Asia/Colombo")` drifts relative to SLT. Colombo observes no DST — any DST-aware offset logic is a footgun. |
| **how to probe** | Freeze clock across a synthetic DST transition date for a DST zone vs `Asia/Colombo`; assert open/close wall times stay `09:30`/`14:30` SLT year-round. Grep for bare `datetime.now()` / local TZ assumptions outside `settings.market_tz`. Run poller with `MARKET_TZ=Europe/London` and show hours shift (negative control). |
| **pass/fail criterion** | **Pass** if only `Asia/Colombo` (or equivalent fixed-offset) is used for market gates and tests prove no DST jump; **fail** if wrong TZ silently shifts the poll window. |
| **commits if fix needed** | 1–2 |
| **risk if unaddressed** | Hours of missed alerts or overnight false polls after any deploy with wrong env. |

---

## WS-083 — Telegram RetryAfter storm under burst fires

| Field | Content |
|---|---|
| **id** | WS-083 |
| **title** | Telegram RetryAfter storm |
| **failure scenario** | Many rules fire in one tick (market open gap). `send_message` sleeps once on `RetryAfter` then retries once; concurrent sends can each sleep, block the poller tick, exhaust the tick budget, leave `message_sent=false` rows, and retry-amplify on the next tick → sustained flood / prolonged tick hold. |
| **how to probe** | Inject a mock Bot that raises `RetryAfter(retry_after=N)` for the first K sends; fire ≥20 claimed events in one `run_once`. Measure tick wall time, count of unsent rows, and whether subsequent ticks pile on. Optionally inject nested RetryAfter on the single retry path. |
| **pass/fail criterion** | **Pass** if burst sends back off globally (or queue) without blocking advisory-lock hold unboundedly, and unsent retry is bounded; **fail** if one storm stalls the poller or multiplies Telegram calls without a ceiling. |
| **commits if fix needed** | 2–4 |
| **risk if unaddressed** | Lock held too long → dual-poller skip storms; delayed alerts; Telegram ban risk. |

---

## WS-084 — Neon pool exhaustion while advisory lock held

| Field | Content |
|---|---|
| **id** | WS-084 |
| **title** | Neon pool exhaustion with held lock |
| **failure scenario** | Session advisory lock holds one pooled connection (`_lock_conn`) for the whole tick. With `Storage(max_size=1)` (or Neon free-tier effective pool of 1 under concurrent bot queries), every other DB call deadlocks waiting for a free connection while the lock connection is checked out. Deferred in FINAL_REPORT as `max_size=1` footgun. |
| **how to probe** | Integration test: `Storage(..., max_size=1)`, acquire advisory lock, then attempt `health_check` / claim / watchlist query on the same Storage from another task. With `max_size=2`, run bot command + poller tick concurrently against Neon. Assert timeout/deadlock vs success. |
| **pass/fail criterion** | **Pass** if default config cannot deadlock under bot+poller load and `max_size<2` is rejected or documented+tested; **fail** if held lock + small pool hangs the process. |
| **commits if fix needed** | 1–3 |
| **risk if unaddressed** | Production hang on Neon; health 503 forever; missed alerts until restart. |

---

## WS-085 — Dashboard auth bypass (future thin web)

| Field | Content |
|---|---|
| **id** | WS-085 |
| **title** | Dashboard auth bypass |
| **failure scenario** | Factory unlocks thin web (watchlist / alerts / fire history). If API routes trust a client-supplied `telegram_id` / cookie without signed session, an attacker enumerates users' watchlists and alert thresholds (market-sensitive personal data). Or CSRF on state-changing routes. |
| **how to probe** | Once `web/` + API exist: call read/write endpoints with forged `telegram_id`, missing session, expired token, and cross-origin POSTs. Attempt IDOR on another user's `alert_rules` / `alert_log`. Record which routes are public (health-only) vs gated. |
| **pass/fail criterion** | **Pass** if every non-public dash route requires a verified session bound to `users.id` and IDOR tests fail closed; **fail** if any user data is readable/writable without auth or via parameter tampering. |
| **commits if fix needed** | 2–5 |
| **risk if unaddressed** | Privacy breach; alert sabotage; compliance / trust failure before launch. |

---

## WS-086 — CSE returns HTML error page as 200

| Field | Content |
|---|---|
| **id** | WS-086 |
| **title** | CSE HTML error page |
| **failure scenario** | cse.lk (or CDN/WAF) returns HTTP 200 with an HTML body (`<!DOCTYPE…`, maintenance page) instead of JSON. Adapter `response.json()` throws or partially parses; circuit may not open if errors are swallowed per-row; poller marks `last_tick_ok=True` with zero useful snapshots → silent data starvation. |
| **how to probe** | Replay recorded HTML bodies (and empty/`null` bodies) through `CSEClient` normalize paths for `tradeSummary`, `companyInfoSummery`, `getAnnouncementByCompany`. Assert structured error logs, circuit trip after `fail_max`, and health `price_poll_ok=False` / tick not "ok". |
| **pass/fail criterion** | **Pass** if non-JSON is classified as upstream failure, circuit opens, health degrades; **fail** if poller continues "green" with no snapshots or crashes the loop. |
| **commits if fix needed** | 1–3 |
| **risk if unaddressed** | Hours of false healthy polling with no alerts; hard-to-debug outage. |

---

## WS-087 — Clock skew between app host and Postgres / CSE

| Field | Content |
|---|---|
| **id** | WS-087 |
| **title** | Clock skew across host, DB, and CSE |
| **failure scenario** | App host clock ahead/behind Postgres `now()` or CSE `createdDate` ms epochs. Disclosure filters using `created_at` / "seen since last tick" windows miss rows or treat epoch-fail-closed rows oddly; `alert_latency_ms` and health `last_tick_at` mislead ops; market-hours gate disagrees with real exchange clock. |
| **how to probe** | Inject ±5m / ±1h skew in tests for `datetime.now(UTC)` vs stored snapshot `ts` vs disclosure `published_at`. Confirm crossing + disclosure rules still claim correctly. Document reliance on host NTP; check Neon `SELECT now()` vs app UTC in a live probe script. |
| **pass/fail criterion** | **Pass** if rules key off snapshot/disclosure timestamps (not wall-clock windows that break under skew) and ops docs require NTP; **fail** if ±5m skew drops disclosures or double-fires. |
| **commits if fix needed** | 1–3 |
| **risk if unaddressed** | Intermittent miss/dup under VM clock drift; bad latency dashboards. |

---

## WS-088 — Duplicate bot + poller processes (split deploy)

| Field | Content |
|---|---|
| **id** | WS-088 |
| **title** | Duplicate bot and poller processes |
| **failure scenario** | Two `koel both` (or bot+poller on two hosts) run: advisory lock serializes ticks (good), but two bots long-poll Telegram → `getUpdates` conflict, dropped commands, or duplicate UX replies. Or one poller without lock ID alignment (different DB) double-sends. Pass 1 fixed dual-poller for same DB; split-brain across envs remains. |
| **how to probe** | Start two processes with same `DATABASE_URL` + token: assert only one holds lock per tick; assert Telegram updater conflict is logged/handled. Start two pollers against different DBs sharing one bot token. Kill -9 holder mid-tick; confirm lock releases (session end) and standby resumes without dup claims (`UNIQUE(rule_id, event_key)`). |
| **pass/fail criterion** | **Pass** if multi-poller same-DB is safe (lock + claim) and multi-bot same-token fails loudly or is ops-forbidden; **fail** if duplicate Telegram messages or silent command loss without health signal. |
| **commits if fix needed** | 1–3 |
| **risk if unaddressed** | User-visible dup alerts / dead bot; eroded "zero dup" quality bar. |

---

## WS-089 — Same-minute rearm `event_key` collision

| Field | Content |
|---|---|
| **id** | WS-089 |
| **title** | Same-minute rearm event_key collision |
| **failure scenario** | Crossing-stable `event_key` plus same-minute rearm with identical price can collide under intentional dual-poller tradeoff (FINAL_REPORT deferred). Second legitimate cross in the same minute may `ON CONFLICT DO NOTHING` and never notify. |
| **how to probe** | Construct two snapshots same minute, same price, rule re-armed between them; evaluate rules → claim twice. Assert second claim inserts or is explicitly documented as accepted loss. Add regression test named for this edge. |
| **pass/fail criterion** | **Pass** if collision is impossible under single-poller semantics **or** documented accepted tradeoff with test; **fail** if single-poller loses a real second cross without documentation. |
| **commits if fix needed** | 1–2 |
| **risk if unaddressed** | Rare missed alert on volatile names; hard to reproduce in prod. |

---

## WS-090 — Unbounded unsent Telegram retry / no dead-letter

| Field | Content |
|---|---|
| **id** | WS-090 |
| **title** | Unbounded unsent retry |
| **failure scenario** | Claimed rows with `message_sent=false` are retried every tick forever (FINAL_REPORT deferred). Permanent errors (blocked bot, chat not found, 400) accumulate; each tick walks a growing set; storage/CPU climb; user never gets a dead-letter signal. |
| **how to probe** | Seed N unsent `alert_log` rows with a send stub that always returns False / raises permanent `TelegramError`. Run many ticks; measure row growth, tick duration, and absence of max-attempt / DLQ. Classify transient vs permanent in the stub matrix. |
| **pass/fail criterion** | **Pass** if permanent failures stop retrying after N attempts (or move to dead-letter) and tick time stays bounded; **fail** if retries are unbounded with no ops signal. |
| **commits if fix needed** | 2–3 |
| **risk if unaddressed** | Gradual poller degradation; noisy logs; never-resolved "ghost" alerts. |

---

## WS-091 — Concurrent identical `/alert` IntegrityError

| Field | Content |
|---|---|
| **id** | WS-091 |
| **title** | Concurrent identical /alert IntegrityError |
| **failure scenario** | User double-taps `/alert SYMBOL above PRICE` (or two devices). Unique constraint on alert rules (or race before insert) raises `IntegrityError`; bot surfaces a 500-ish / opaque error instead of idempotent "already exists". Deferred in FINAL_REPORT. |
| **how to probe** | Parallel `asyncio.gather` of two identical create-alert storage calls; invoke bot handler twice concurrently with mocks. Assert user-facing reply is kind and exactly one active rule remains. |
| **pass/fail criterion** | **Pass** if duplicate create is idempotent or returns a clear "already watching that threshold" message; **fail** if uncaught exception or duplicate active rules. |
| **commits if fix needed** | 1–2 |
| **risk if unaddressed** | Bot UX bar failure; possible duplicate rules if constraint missing. |

---

## WS-092 — `both` SIGTERM / tick `--force` polish

| Field | Content |
|---|---|
| **id** | WS-092 |
| **title** | both SIGTERM and tick force-or-True |
| **failure scenario** | (a) `koel both` does not cleanly stop scheduler + updater + health + unlock on SIGTERM → stuck advisory lock until TCP drop, orphan threads. (b) `tick` path uses `force=args.force or True` so `--force` is effectively always on — operators cannot dry-run market-hours gating via `tick`. |
| **how to probe** | Read `__main__.py` + poller shutdown; send SIGTERM to `both` under load with held lock; assert unlock + exit code 0 within timeout. Run `tick` without `--force` outside hours and assert skip (today it forces). Fix or document. |
| **pass/fail criterion** | **Pass** if SIGTERM releases lock and stops cleanly, and `tick` honors `--force` only when set; **fail** if lock sticks past process exit window or `tick` always forces. |
| **commits if fix needed** | 1–2 |
| **risk if unaddressed** | Deploy rollouts stall next poller; misleading CLI for ops drills. |

---

## WS-093 — Null `createdDate` / undated disclosure fail-closed

| Field | Content |
|---|---|
| **id** | WS-093 |
| **title** | Null createdDate disclosure fail-closed |
| **failure scenario** | Rows with null `createdDate` map to epoch and fail-closed (PASS4 leftover). Real CSE announcements that only populate `dateOfAnnouncement` are never alerted — silent miss for disclosure rules. |
| **how to probe** | Fixture rows: null `createdDate` + valid `dateOfAnnouncement`; null both; future-dated junk. Run normalize + disclosure rule filter. Live-sample probe: count how often production-shaped payloads omit `createdDate`. |
| **pass/fail criterion** | **Pass** if undated-but-real rows are dated via fallback field **or** explicitly counted in metrics as dropped-with-reason; **fail** if live CSE often omits `createdDate` and users get zero disclosure pings. |
| **commits if fix needed** | 1–3 |
| **risk if unaddressed** | Core product promise ("new disclosure ping") fails for affected symbols. |

---

## WS-094 — Disclosure deep-link `#announcementId` on cse.lk

| Field | Content |
|---|---|
| **id** | WS-094 |
| **title** | Disclosure URL deep-link verification |
| **failure scenario** | Bot messages include a constructed cse.lk URL with `#announcementId` (or similar). Live site ignores the hash / requires query params → user lands on generic announcements page and cannot find the filing (FINAL_REPORT deferred live verification). |
| **how to probe** | Take 3 recent real announcement IDs from adapter samples; open constructed URLs in a fetch/browser check; confirm the specific filing is visible. Diff against network traffic on the announcements UI. |
| **pass/fail criterion** | **Pass** if link resolves to the exact announcement (or a working search URL); **fail** if link is a dead hash or wrong page. |
| **commits if fix needed** | 1–2 |
| **risk if unaddressed** | Alert fires but user cannot act — trust erosion. |

---

## WS-095 — Health endpoint unauthenticated exposure

| Field | Content |
|---|---|
| **id** | WS-095 |
| **title** | Health endpoint exposure |
| **failure scenario** | `/health` binds default `127.0.0.1:8080` but ops may set `HEALTH_HOST=0.0.0.0`. Details may leak `last_error`, lock status, DB ok — useful to attackers mapping outage windows. No auth on health is normal, but binding + payload must be intentional. |
| **how to probe** | Document default bind; scan response JSON keys; deploy-config review for public bind. Ensure no secrets/tokens in health body. Optional: separate liveness (shallow) vs readiness (detailed) for public vs private. |
| **pass/fail criterion** | **Pass** if defaults are loopback-only, no secrets in payload, and public-bind guidance exists; **fail** if tokens/connection strings appear or docs push `0.0.0.0` without warning. |
| **commits if fix needed** | 0–2 |
| **risk if unaddressed** | Recon aid; accidental secret leak via error strings. |

---

## WS-096 — Circuit half-open stampede after CSE outage

| Field | Content |
|---|---|
| **id** | WS-096 |
| **title** | Circuit half-open stampede |
| **failure scenario** | After `fail_max`, circuit opens. On reset, half-open allows one probe — but per-endpoint breakers + many symbols may still fan out simultaneous calls when circuit closes, hammering cse.lk (compliance: polite rate limits) and re-tripping immediately. |
| **how to probe** | Force-open all endpoint breakers; advance time past `reset_timeout`; run a full tick with a large watchlist mock. Count outbound HTTP calls in the first recovering tick; assert pacing / single-flight half-open behavior. |
| **pass/fail criterion** | **Pass** if recovery is single-flight or rate-limited and does not exceed polite budget; **fail** if first closed tick thundering-herds CSE. |
| **commits if fix needed** | 1–3 |
| **risk if unaddressed** | IP block / WAF attention; prolonged outage loops. |

---

## WS-097 — Weekend / holiday poll skip vs CSE special sessions

| Field | Content |
|---|---|
| **id** | WS-097 |
| **title** | Weekend and holiday market calendar |
| **failure scenario** | Poller skips Sat/Sun via `weekday() >= 5` but does not know CSE holidays. Conversely, rare special / half-day sessions may need polling outside assumptions. Holiday weekday → wasted polls and possible false "market open" health; special Saturday session → missed alerts. |
| **how to probe** | Document CSE holiday list source (public calendar only — not competitors). Simulate a known holiday weekday and confirm product decision: poll-and-no-op vs calendar skip. Confirm weekend skip tests exist. |
| **pass/fail criterion** | **Pass** if holiday behavior is an explicit accepted decision with tests for weekends; **fail** if product claims holiday awareness but code only checks weekday. |
| **commits if fix needed** | 0–3 |
| **risk if unaddressed** | Noise polls on holidays; rare miss on special sessions. |

---

## WS-098 — Overnight gap crossing at first open tick

| Field | Content |
|---|---|
| **id** | WS-098 |
| **title** | Overnight gap crossing at open |
| **failure scenario** | Price closes below threshold Friday, opens above Monday. Crossing logic with missing/stale `prev` snapshot may skip (no baseline) or fire incorrectly on first tick after gap. Quality bar requires gap/missing-prev tests — probe end-to-end through poller claim path, not only `rules.py` units. |
| **how to probe** | DB fixtures: Friday snapshot below, Monday open above; armed rule; run `run_once(force=True)`. Repeat missing prev entirely. Assert exactly one claim + send for true cross; none for "already above without cross". |
| **pass/fail criterion** | **Pass** if poller+storage path matches unit crossing semantics (one fire on true gap cross); **fail** if E2E drops or double-fires the open gap. |
| **commits if fix needed** | 1–2 |
| **risk if unaddressed** | Worst user-visible miss: big overnight move, no ping. |

---

## WS-099 — Advisory unlock failure / connection drop mid-tick

| Field | Content |
|---|---|
| **id** | WS-099 |
| **title** | Connection drop mid-tick with held advisory lock |
| **failure scenario** | Neon drops the idle/held lock connection mid-tick (or unlock raises). `finally` unlock fails; process thinks it unlocked; server may still hold lock until backend session GC. Standby pollers skip (`poll_lock_held`) until timeout — alert blackout. |
| **how to probe** | Integration: acquire lock, close underlying connection abruptly, call `advisory_unlock` / `close()`, start second Storage and `pg_try_advisory_lock`. Measure time-to-reacquire. Ensure health sets `last_tick_ok=False` on unlock errors. |
| **pass/fail criterion** | **Pass** if drop is detected, health degrades, and lock is reclaimable within a bounded session-timeout window documented for Neon; **fail** if blackout persists without signal. |
| **commits if fix needed** | 2–4 |
| **risk if unaddressed** | Multi-minute silent alert outage after blip. |

---

## WS-100 — Dashboard session fixation / CSRF on alert mutations

| Field | Content |
|---|---|
| **id** | WS-100 |
| **title** | Dashboard session fixation and CSRF on mutations |
| **failure scenario** | Companion to WS-085: even with login, a fixed session cookie issued pre-auth, or missing CSRF/SameSite on `POST` alert/watchlist mutations, lets a malicious site create/cancel alerts as the victim — undermining Telegram-first trust when web is unlocked. |
| **how to probe** | Threat-model review of planned Next.js auth (cookie flags, rotation on login, CSRF for mutations, SameSite). Write failing security tests/checklist before DASH implement. Attempt cross-site POST once scaffold exists. |
| **pass/fail criterion** | **Pass** if sessions rotate on login, cookies are `Secure`/`HttpOnly`/`SameSite=Lax|Strict`, and mutating routes reject CSRF; **fail** if checklist incomplete before first dash write API ships. |
| **commits if fix needed** | 2–5 |
| **risk if unaddressed** | Account takeover of alert config; malicious threshold spam to Telegram. |

---

## Roll-up

| ID | Title | Commits if fix | Primary lane |
|---|---|---|---|
| WS-081 | Market open/close boundary | 1–2 | CORE |
| WS-082 | Colombo no-DST / TZ honesty | 1–2 | CORE |
| WS-083 | Telegram RetryAfter storm | 2–4 | CORE |
| WS-084 | Neon pool + held lock | 1–3 | CORE |
| WS-085 | Dashboard auth bypass | 2–5 | DASH |
| WS-086 | CSE HTML error page | 1–3 | CORE |
| WS-087 | Clock skew | 1–3 | CORE |
| WS-088 | Duplicate bot+poller processes | 1–3 | OPS/CORE |
| WS-089 | Same-minute rearm event_key | 1–2 | CORE |
| WS-090 | Unbounded unsent retry | 2–3 | CORE |
| WS-091 | Concurrent identical /alert | 1–2 | CORE |
| WS-092 | SIGTERM + tick force polish | 1–2 | OPS/CORE |
| WS-093 | Null createdDate disclosures | 1–3 | CORE |
| WS-094 | Disclosure deep-link | 1–2 | CORE |
| WS-095 | Health endpoint exposure | 0–2 | OPS |
| WS-096 | Circuit half-open stampede | 1–3 | CORE |
| WS-097 | Weekend/holiday calendar | 0–3 | CORE |
| WS-098 | Overnight gap at open | 1–2 | CORE |
| WS-099 | Lock connection drop mid-tick | 2–4 | CORE |
| WS-100 | Dash session fixation / CSRF | 2–5 | DASH |

**Count:** 20 workstreams (WS-081 … WS-100).  
**Next:** Schedule probes in an adversarial implementation pass; promote failing probes to findings with proof before fix commits.
