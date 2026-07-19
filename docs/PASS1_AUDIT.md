# Pass 1 adversarial audit — Quiverly Stage A

**Verdict: Stage A is not done.** Crossing unit tests are solid; production paths still lose alerts, flood users, double-fire under replica race, and fail the latency / ops bars by design.

Ranking key: **score ≈ severity × user impact ÷ effort** (higher = fix first). Severity weights: critical≈4, high≈3, medium≈2, minor≈1. Effort: S≈÷1, M≈÷2, L≈÷3.

---

## Ranked findings

### 1. Disclosure backfill floods Telegram on first poll
- **Severity:** critical  
- **Score:** 20  
- **Failure scenario:** User runs `/alert JKH.N0000 disclosure`. Next poll calls `getAnnouncementByCompany` with `from_date = today − 1 year`. Every row is “new” to `disclosures`, so `insert_disclosure_if_new` returns each row and `evaluate_disclosure_rules` fires for **every historical announcement** (tens–hundreds of messages). Same flood if DB is wiped / new env with existing CSE history.  
- **Where:** `chime/poller.py:144–167`, `chime/storage.py:163–191`  
- **Fix:** On first ingest (or when creating a disclosure rule), **seed** disclosures with `ON CONFLICT DO NOTHING` / bulk insert **without** calling `_claim_and_send`. Only fire for rows with `published_at > rule.created_at` (or `seen_at` after a baseline watermark).  
- **Acceptance:** Create disclosure rule against a symbol with ≥5 historical announcements → zero Telegram sends; one new CSE announcement after baseline → exactly one send.  
- **Effort:** S  

### 2. Disarm-before-claim drops price alerts forever
- **Severity:** critical  
- **Score:** 16  
- **Failure scenario:** Crossing detected. Poller sets `armed=False` then crashes (OOM, deploy kill, DB blip) **before** `claim_alert`. Rule is disarmed, no `alert_log` row. Price stays above threshold → no rearm → **crossing never notifies**. User believes alert is armed.  
- **Where:** `chime/poller.py:122–131` (disarm loop before `_claim_and_send`)  
- **Fix:** Order: `claim_alert` first → send → then `set_rule_armed(False)`. On claim conflict, skip disarm. If send fails, keep claim (`message_sent=False`) and still disarm (or disarm only after successful claim).  
- **Acceptance:** Inject crash between evaluate and claim; after restart, either pending claim exists or rule still armed and next eligible cross (or same snap retry path) still delivers exactly one message.  
- **Effort:** S  

### 3. No way to deactivate / delete an alert
- **Severity:** high  
- **Score:** 12  
- **Failure scenario:** User typos threshold (`/alert JKH above 20` instead of `200`) or no longer wants a disclosure alert. `/myalerts` lists them; there is **no** `/cancel`, `/deletealert`, or deactivate command. Only workaround is inactive duplicate via re-create of the *same* threshold (storage deactivates identical active rules) — wrong threshold stays forever.  
- **Where:** `chime/bot.py` (handlers); `chime/storage.py:260–309` (create-only)  
- **Fix:** Add `/cancel ALERT_ID` or `/unalert SYMBOL [kind]` setting `active=FALSE`. List ids already shown in `/myalerts`.  
- **Acceptance:** Create alert → `/cancel <id>` → `/myalerts` empty → poller does not fire.  
- **Effort:** S  

### 4. `/unwatch` does not stop the owner’s rules (cross-user leak)
- **Severity:** high  
- **Score:** 12  
- **Failure scenario:** User A sets price alerts on `JKH`, then `/unwatch JKH`. User B still watches `JKH`. Poller loads **global** `watched_symbols()`, then `active_rules_for_symbols` — **User A’s rules still evaluate and Telegram A**. Conversely, if A is the only watcher, unwatch stops polling that symbol and A’s alerts go **silently dead** while still listed in `/myalerts`.  
- **Where:** `chime/poller.py:90–106`, `chime/bot.py:95–112`, `chime/storage.py:222–235`  
- **Fix:** On unwatch, deactivate that user’s rules for the symbol (or evaluate rules only for symbols on **that rule owner’s** watchlist). Keep `/myalerts` consistent.  
- **Acceptance:** A unwatches while B watches → A receives no further alerts; `/myalerts` reflects inactive/removed rules.  
- **Effort:** S  

### 5. Dual poller instances double-fire crossings
- **Severity:** critical  
- **Score:** 10  
- **Failure scenario:** Two `python -m chime poller` (or poller + both) share one DB. Both insert a new `price_snapshots` row for the same tick (ids 10 and 11). Both see `previous.price` below threshold and current above. `event_key` is `price:{rule_id}:{snapshot_id}` → **two distinct keys** → two claims → two Telegrams for one cross. `ON CONFLICT (rule_id, event_key)` does not help.  
- **Where:** `chime/rules.py:33–35`, `chime/poller.py:112–131`; no leader lock anywhere  
- **Fix:** Single-leader advisory lock (`pg_try_advisory_lock`) around the poll cycle, **or** change price `event_key` to a crossing identity that excludes snapshot id (e.g. `price:{rule_id}:{threshold}:{armed_generation}` / hash of prev→curr transition), **or** document and enforce one poller replica.  
- **Acceptance:** Run two pollers; force one synthetic cross → exactly one `alert_log` row and one send.  
- **Effort:** M  

### 6. Health lies when CSE is down; poller-only never updates health
- **Severity:** high  
- **Score:** 9  
- **Failure scenario:** `tradeSummary` circuit opens. `_poll_prices` logs and returns `[]`. `run_once` still sets `last_tick_ok = True`. Ops sees `/health` 200. In `python -m chime poller`, `HealthState` is never updated at all (always `ok=True`, empty details). Deploy looks healthy while alerts are frozen.  
- **Where:** `chime/poller.py:74–84`, `95–102`; `chime/__main__.py:82–103` vs `56–70`; test even asserts OK on circuit open (`tests/test_poller_resilience.py:60`)  
- **Fix:** Track `price_poll_ok` / `disclosure_poll_ok`; set `last_tick_ok=False` (or degraded) when watchlist non-empty and price fetch fails. Wire health updates into `_run_poller` like `_run_both`.  
- **Acceptance:** With watchlist + forced circuit open → `/health` 503 (or `status=degraded`) with explicit error field.  
- **Effort:** S  

### 7. Latency p95 &lt; 5s is structurally unmet (and unmeasured)
- **Severity:** high  
- **Score:** 8  
- **Failure scenario:** Default `POLL_INTERVAL_SECONDS=60` (+ jitter up to 5s). From CSE print → Telegram, design p50 ≈ 30s, p95 ≈ 60s+. Disclosure path is worse: sequential per-symbol HTTP + `0.2–0.5s` sleep (`poller.py:168–170`) — with 40 watched symbols, disclosure leg alone is ~8–20s+ before later symbols are even fetched. No latency metrics/histogram exist.  
- **Where:** `chime/config.py:41–42`, `chime/poller.py:149–170`, `.env.example`  
- **Fix:** Either lower interval toward ≤5s **with** polite CSE load budget, or explicitly revise the quality bar to “within one poll interval” and instrument `fired_at - snapshot.ts`. Prefer bulk `approvedAnnouncement` + name map over N per-symbol calls.  
- **Acceptance:** Documented SLO matches implementation; or p95(event→send) &lt; 5s under load test with ≥20 symbols.  
- **Effort:** L (to truly meet &lt;5s) / S (to re-scope + measure)  

### 8. One junk `tradeSummary` row aborts the entire price poll
- **Severity:** high  
- **Score:** 6  
- **Failure scenario:** CSE returns 282 rows; one has `price: null` or a string. `TradeSummaryResponse.model_validate` raises → `_poll_prices` returns `[]` → **all** symbols miss that cycle (and longer if circuit opens after retries).  
- **Where:** `chime/adapters/cse.py:289–298`  
- **Fix:** Validate row-by-row; skip/log bad rows; return partial list.  
- **Acceptance:** Fixture with 2 good + 1 bad row → 2 snapshots stored, no cycle exception.  
- **Effort:** M  

### 9. Mid-day `daily_move` fires immediately on “already exceeded”
- **Severity:** medium  
- **Score:** 6  
- **Failure scenario:** Stock is +4% since previous close. User sets `/alert JKH move 3`. Next poll sees `abs(change_pct) >= 3` and fires (level check, not cross of the % threshold). Surprising vs price crossing semantics; also fires on cold start with CSE-provided `percentageChange`.  
- **Where:** `chime/rules.py:137–164`  
- **Fix:** Require transition (`prev_pct < thr <= curr_pct`) **or** only arm after first observation / after `rule.created_at`.  
- **Acceptance:** Create move alert while already +4%; no fire until next day or until % crosses the threshold from below.  
- **Effort:** S  

### 10. `/start` copy implies disclosures without an explicit disclosure rule
- **Severity:** medium  
- **Score:** 6  
- **Failure scenario:** START text promises pings when “a new company disclosure drops.” `/watch JKH` alone creates **no** disclosure rule (`cmd_watch` only `add_watch`). User watches, never runs `/alert … disclosure`, never gets filings. CLAUDE MVP bullet “for a watched symbol” conflicts with command list / bot wiring.  
- **Where:** `chime/bot.py:24–28`, `65–92`; `CLAUDE.md:93–100`  
- **Fix:** Either auto-create disclosure rule on `/watch`, or change START/`/watch` reply to: “Disclosures need `/alert SYMBOL disclosure`.” Align CLAUDE.md.  
- **Acceptance:** Copy and behavior match; manual test script documents the chosen model.  
- **Effort:** S  

### 11. `symbol_exists` treats CSE outages as “invalid ticker”
- **Severity:** medium  
- **Score:** 6  
- **Failure scenario:** Transient 5xx / circuit open during `/watch` or `/alert`. `fetch_company_info` returns `None` or raises → `symbol_exists` → False → “Couldn't find SYMBOL on cse.lk” — user abandons a valid ticker.  
- **Where:** `chime/adapters/cse.py:386–391`, `chime/bot.py:79–84`, `164–168`  
- **Fix:** Distinguish not-found (validated empty/404-ish body) vs transport/circuit errors; reply “cse.lk unreachable, try again.”  
- **Acceptance:** Mock CSE timeout → bot does not claim symbol is invalid.  
- **Effort:** S  

### 12. Disclosure URL is likely a dead deep link
- **Severity:** medium  
- **Score:** 4  
- **Failure scenario:** Messages link to `https://www.cse.lk/announcements?id={announcementId}`. Probe report: `getAnnouncementById` → **204**; no evidence the Next.js page honors `?id=`. User taps alert → useless page.  
- **Where:** `chime/adapters/cse.py:186`, `docs/endpoint_probe_report.md:193`  
- **Fix:** Prefer CDN `filePath` when present (legacy), or company announcements URL without fake query; verify one live link in manual E2E.  
- **Acceptance:** Fired disclosure message URL returns HTTP 200 with the filing visible.  
- **Effort:** S  

### 13. Disclosure date window uses server local `date.today()`, not SLT
- **Severity:** medium  
- **Score:** 4  
- **Failure scenario:** Host in UTC near midnight: `from_date`/`to_date` skew vs Asia/Colombo; edge announcements dropped or window wrong on year boundary (`today.year - 1` also breaks on Feb 29).  
- **Where:** `chime/poller.py:144–146`  
- **Fix:** `datetime.now(ZoneInfo("Asia/Colombo")).date()`; use `relativedelta` / replace safely for −1 year.  
- **Acceptance:** Unit test with frozen UTC 18:30 (SLT next calendar day) uses Colombo dates.  
- **Effort:** S  

### 14. Concurrent identical `/alert` can IntegrityError the bot
- **Severity:** medium  
- **Score:** 4  
- **Failure scenario:** Double-tap create. Both transactions deactivate then insert; partial unique index `idx_alert_rules_unique_active` on `(user_id, symbol, type, COALESCE(threshold,-1)) WHERE active` rejects the loser. Bot has no handler → generic error handler / user sees nothing useful.  
- **Where:** `db/migrations/001_initial.sql:79–81`, `chime/storage.py:271–289`, `chime/bot.py:175`  
- **Fix:** Catch unique violation → fetch existing active rule and return it; or `INSERT … ON CONFLICT …`.  
- **Acceptance:** Parallel create of same rule → one active row, bot replies success both times.  
- **Effort:** S  

### 15. `both` mode: weak shutdown; health thread not joined
- **Severity:** medium  
- **Score:** 4  
- **Failure scenario:** `_run_both` spins `while True` with **no** SIGTERM handler (unlike `run_poller_forever`). Health `ThreadingHTTPServer` daemon thread: `shutdown()` without `server_close()` / join — noisy under reload. Default bind `127.0.0.1` is fine for local; in Docker without `HEALTH_HOST=0.0.0.0`, orchestrator probes fail.  
- **Where:** `chime/__main__.py:50–79`, `chime/health.py:49–52`, `chime/config.py:46–47`  
- **Fix:** Shared stop event + signal handlers; `server_close()`; document `HEALTH_HOST` for containers.  
- **Acceptance:** SIGTERM to `both` stops bot+poller and exits 0 within few seconds.  
- **Effort:** S  

### 16. `tick` always forces market hours ignore
- **Severity:** minor  
- **Score:** 2  
- **Failure scenario:** `force=args.force or True` is **always True** — `--force` is dead. Easy to think `tick` alone respects hours.  
- **Where:** `chime/__main__.py:170`  
- **Fix:** `force=args.force` (README: tick respects hours unless `--force`).  
- **Acceptance:** Without `--force` outside hours → no snapshots; with `--force` → runs.  
- **Effort:** S  

### 17. Unsent alert retry has no backoff / poison-pill limit
- **Severity:** medium  
- **Score:** 3  
- **Failure scenario:** User blocks bot → every cycle retries up to 50 unsent forever; burns Telegram API, logs noise; real new alerts share the send path.  
- **Where:** `chime/poller.py:186–192`, `chime/storage.py:378–394`  
- **Fix:** `attempts` / `next_retry_at` columns; drop or dead-letter after N failures.  
- **Acceptance:** Permanent send failure → stops retrying after N; new alerts still send.  
- **Effort:** M  

### 18. Bare tickers accepted by regex but not normalized to CSE form
- **Severity:** minor  
- **Score:** 2  
- **Failure scenario:** `normalize_symbol("JKH")` returns `JKH`; live CSE ids are `JKH.N0000`. Lookup fails with “Couldn't find” — recoverable but unhelpful. Hyphenated junk correctly rejected. Regex not dangerously loose for CSE.  
- **Where:** `chime/bot.py:22–49`  
- **Fix:** If no `.`, try `f"{s}.N0000"` before failing; mention form in error.  
- **Acceptance:** `/watch JKH` resolves to `JKH.N0000` when that exists.  
- **Effort:** S  

### 19. `move_fired_keys` loads unbounded history every snapshot
- **Severity:** minor  
- **Score:** 1  
- **Failure scenario:** Years of `move:*` keys for a hot symbol loaded on every price evaluate (`LIKE 'move:%%'`). Correctness OK; latency/memory grows.  
- **Where:** `chime/storage.py:142–154`  
- **Fix:** Filter `fired_at::date = current_date` (SLT) or key prefix for today.  
- **Acceptance:** Query plan / row count bounded to one session day.  
- **Effort:** S  

---

## Refuted concerns

| Concern | Verdict |
|---|---|
| Overnight gap incorrectly uses `previous_close` for crossings | **Refuted.** Crossings use prior **snapshot price** (`get_previous_state` → `previous.price`). `prev is None` never fires (`rules.py:21–22`, tests in `test_crossing.py`). Gap-open across threshold **intentionally** fires (`TestGapOpen`) — correct crossing semantics, not a previous_close bug. |
| `UNIQUE … COALESCE(threshold,-1)` invalid in Postgres | **Refuted.** Expression unique indexes are valid; `001_initial.sql:79–81` is fine. Residual issue is unhandled concurrent insert (#14), not syntax. |
| Armed state not reloaded mid-cycle for other rules | **Refuted for current design.** Rules loaded once; one snapshot per symbol per cycle; all rules for that symbol evaluated in one pure call. No same-cycle cross-rule armed dependency. |
| `open` column reserved-word SQL breakage | **Refuted.** Unquoted `open` is legal as a Postgres column; inserts/selects use it successfully in schema + `storage.py`. |
| `/alert SYMBOL disclosure` missing from bot | **Refuted.** Wired in `HELP_HINT`, usage text, and `cmd_alert` (`kind in ("disclosure","announcement")`). CLAUDE.md command list is incomplete, not the bot. |
| `/watch` must auto-create disclosure rules | **Ambiguous spec, not an implementation defect by itself.** Bot requires explicit disclosure rule (reasonable). Product gap is START copy / CLAUDE wording (#10), not missing code path for `/alert … disclosure`. |
| Health server catastrophic thread leak | **Overstated.** Daemon thread + `shutdown()` is acceptable for v1; residual is incomplete close/join and `both` signal handling (#15), not an unbounded leak under normal process exit. |

---

## Quality bar scorecard

| Bar | Stage A status |
|---|---|
| 1. Alert correctness (crossing) | **Mostly pass** for above/below unit semantics; **fail** on disarm-before-claim loss, dual-poller dupes, disclosure backfill, daily_move level fire. |
| 2. Zero dupes / zero losses | **Fail** (#1 flood, #2 loss, #5 dupes). Claim/retry path for same `event_key` is good in isolation. |
| 3. Latency p95 &lt; 5s | **Fail / unmeasurable** (#7). No instrumentation; 60s poll cannot meet bar. |
| 4. Resilience to cse.lk failures | **Partial.** Circuit + retries exist; all-or-nothing tradeSummary (#8); health lies (#6); `symbol_exists` UX (#11). |
| 5. Ops | **Partial.** Structured logs + migrate + one-command `both` exist; health inaccurate; shutdown/`tick` bugs; secrets via env OK. |
| 6. Code quality | **Pass-ish.** Types/pydantic present; no TODOs; dead `if not disclosure_rules: pass`; pytest cov gated only on `chime.rules`. |
| 7. Bot UX | **Fail** (#3 no cancel, #4 unwatch, #10 start copy, #12 links). |

---

## Stage A “done” refutation (summary)

Claims that Stage A completes “alert → Telegram end-to-end” are overstated: disclosure alerts can spam a year of history; a crash between disarm and claim silently kills price alerts; two poller processes can double-notify; `/health` can be green while CSE is dark; p95&lt;5s is not designed in; users cannot cancel alerts; unwatch does not mean “stop alerting me.” Crossing math for a single in-process poller with a warm previous snapshot is the strongest part of the build — not sufficient to call Stage A done.
