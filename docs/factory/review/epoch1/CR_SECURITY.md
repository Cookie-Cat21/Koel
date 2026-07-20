# Epoch 1 — Security code review (`CR_SECURITY`)

| Field | Value |
|---|---|
| **Reviewer role** | Security (scoped surfaces only) |
| **Branch** | `cursor/epoch1-execute-cb19` |
| **Reviewed HEAD** | `2751414125c300eb2d8e431430202026a10e7ff1` |
| **Scope** | Health exposure · env secrets · advisory lock · bot input validation · dash auth ADR · SQL via psycopg · log PII |
| **Method** | Read implementation + ADR/contract; no invented endpoints. Rank by real exploitability / blast radius. |

## Verdict

**No critical confidentiality or injection defects in Stage A code.** Secrets stay in env; SQL is parameterized; cancel/unwatch are user-scoped; advisory lock sticky-hold is integrity-correct; dash auth ADR bans the impersonation pattern.

**Do not treat Epoch 1 as security-clean for a networked deploy.** Three medium issues are live today (anonymous health detail on bind, Telegram→CSE abuse surface, telegram_id/update text in logs). Dash auth is design-only — WAVE1_DASH still documents the banned model. Advisory lock residuals are availability/integrity under load, not auth bypass.

---

## Ranking key

| Rank | Meaning |
|---|---|
| **HIGH** | Practical exploit or credential/PII leak path with meaningful blast radius |
| **MEDIUM** | Real defect or missing control; needs a networked or multi-user condition |
| **LOW** | Footgun / hygiene / doc drift; limited blast radius |
| **PASS** | Scoped surface checked; no finding worth a ticket |

---

## Ranked findings

### 1. MEDIUM — Process `/health` is anonymous ops recon (bind-dependent)

**Where:** `koel/health.py`, `koel/__main__.py`, `koel/poller.py` (`run_poller_forever` health loop), `koel/config.py` (`HEALTH_HOST` default `127.0.0.1`)

**What is true:** Defaults bind loopback. Body does **not** include `TELEGRAM_BOT_TOKEN` or `DATABASE_URL`. Status flips to `503` when `ok` is false.

**What is wrong:** Any client that can reach the port gets the full detail payload on `/health`, `/healthz`, **and `/`**:

- `db_ok`, `last_tick_at`, `last_tick_ok`, `price_poll_ok`, `disclosure_poll_ok`, `lock_held_skip`, `last_error`

`HEALTH_HOST` is unrestricted. README documents the override but **does not warn** against `0.0.0.0`. No boot-time refuse / warn when bind is non-loopback. On poll-cycle exceptions, `poller.last_error = str(exc)` — OperationalError strings often include DB host/user — and that string is copied into the health JSON.

ADR 001 / API_CONTRACT correctly **ops-gate** future `GET /api/v1/health`. That does not protect the existing process HTTP server.

**Not theater:** Loopback-only local runs are fine. The finding is accidental public bind + rich payload + exception text. Aligns with WAVE1_ADVERSARIAL WS-095 (still checklist-shaped; residual is real).

**Fix direction:** Warn or refuse non-loopback unless `HEALTH_PUBLIC=1`; split liveness (`status`/`db_ok`) vs readiness detail; never put raw `str(exc)` in the public body (stable codes only).

---

### 2. MEDIUM — Public bot has no abuse budget (CSE + DB write amplification)

**Where:** `koel/bot.py` (`cmd_start`, `cmd_watch`, `cmd_alert`, `_lookup_symbol`)

**What is true:** Symbols must match `SYMBOL_RE`; unknown tickers are rejected after CSE lookup; thresholds must parse as floats and be `> 0`; `/cancel` is scoped `user_id + rule_id`.

**What is wrong:** Anyone who can message the bot can:

1. `/start` → `ensure_user(telegram_id)` (unbounded user-row growth)
2. `/watch` / `/alert` → live `cse.fetch_company_info` per attempt
3. Create arbitrary numbers of active rules (no per-user cap)

There is no command rate limit, no allowlist, no max watchlist/alert count. For a bot whose username is public, this is a polite CSE DoS and a cheap DB fill — compliance already requires not hammering cse.lk.

**Not theater:** Input *format* validation is solid. Abuse *volume* is not. Severity is medium because Telegram identity is weakly expensive to mint, not because parsers are missing.

**Fix direction:** Per-telegram_id rate limit on CSE-touching commands; hard caps on watchlist/rules; optional `BOT_ALLOWED_TELEGRAM_IDS` for staging.

---

### 3. MEDIUM — Structured logs emit Telegram identifiers and update snippets

**Where:** `koel/notify.py` (`chat_id=` on retry/transient/error); `koel/bot.py` `on_error` (`update=str(update)[:200]`); `koel/logging_setup.py` (JSON to stdout, no redaction processor)

**What is true:** No call site logs `TELEGRAM_BOT_TOKEN` or `DATABASE_URL`. High-traffic CSE logs use path/endpoint/error, not user ids.

**What is wrong:**

- Failed sends log `chat_id` (= Telegram user id). That is persistent PII in any log drain.
- Handler errors log a 200-char `Update` string — typically includes `id`, username, and message text.

Under GDPR-style handling, telegram_id in always-on JSON logs is a retention/processing concern, not a theoretical one.

**Fix direction:** Log internal `user_id` / `rule_id` instead of `chat_id` by default; drop or hash update dumps; document forbidden fields (token, DSN, raw Update) when OPS ships `LOG_FIELDS` (WS-050).

---

### 4. LOW — Compose Postgres is world-reachable with a trivial password

**Where:** `docker-compose.yml` (`ports: "5432:5432"`, `POSTGRES_PASSWORD=koel`); `.env.example` mirrors that DSN

**Failure:** On a shared LAN / cloud VM with compose up, Postgres accepts `koel:koel` on `0.0.0.0:5432`. Local-dev convenience, not a production story — but nothing in compose or README says “bind localhost only.”

**Fix direction:** `127.0.0.1:5432:5432` or no host publish; document that compose creds are lab-only.

---

### 5. LOW — Dash auth ADR is sound; WAVE1_DASH still teaches the banned model

**Where:** `docs/adr/001-dash-auth.md` (Accepted); `docs/factory/API_CONTRACT_V1.md`; stale `docs/factory/workstreams/WAVE1_DASH.md` WS-023 sketch

**PASS (ADR):** Server session bound to `users.id`; bans shared-secret + client `telegram_id`; bans secret-in-cookie / localStorage; demo requires `DASH_DEMO_AUTH=1` + allowlist + non-empty `DASH_SESSION_SECRET`; CSRF on mutations; health ops-gated; no cse.lk from `web/`.

**LOW residual:** `web/` does not exist — no runtime probe. WAVE1_DASH acceptance text still says Bearer + `X-Telegram-Id` and cookie-holding secret. An implementer reading the workstream file instead of the ADR will reintroduce universal impersonation. Epoch 1 closed WS-023 as “ADR done”; doc supersession is incomplete.

**Not in scope to invent:** Session fixation / CSRF bypass probes (WS-085/100) — correctly deferred until routes exist.

**Fix direction:** Mark WAVE1_DASH auth rows superseded by ADR 001 in-file; add acceptance tests that refuse client-supplied `telegram_id` as sole auth when Pass 1 API lands.

---

### 6. LOW — Advisory lock: integrity OK; long hold remains an availability risk

**Where:** `koel/storage.py` `try_advisory_lock` / `advisory_unlock`; `koel/poller.py` `run_once`; `koel/notify.py` RetryAfter cap

**PASS (integrity):** Session lock is held on one pooled connection (`_lock_cm` / `_lock_conn`) until unlock; `run_once` unlocks in `finally`; `close()` unlocks; dual-holder proof in `tests/test_advisory_lock.py`. Pass 2 sticky-lock defect is closed. Lock-skip degrades health (`poll_lock_held`). This is **not** an auth bypass.

**LOW residual:** Lock is held for the whole tick including sends. RetryAfter sleep is capped at 30s per call (Epoch 1 fix), but a burst of N failing sends still holds the lock ≈ N×30.5s → standby pollers skip (`lock_held_skip`) and alerts delay. Separate footgun: `Storage(max_size=1)` deadlocks other queries while the lock connection is checked out (documented; default `max_size=4`).

Hard-coded `POLL_LOCK_ID = 4_201_337` is fine on a dedicated DB; irrelevant as a secret.

**Do not inflate:** Calling the sticky lock a “security vulnerability” after Pass 2 is theater. Rank it as availability/integrity under Telegram pressure only.

---

### 7. LOW — Threshold parser accepts non-finite floats

**Where:** `koel/bot.py` `cmd_alert` (`float(...)` then `threshold <= 0`)

**Failure:** `inf` and `nan` pass the positive check (`nan <= 0` is false). Creates useless or confusing rules; not RCE / SQLi.

**Fix direction:** `math.isfinite(threshold)` and optional upper bound.

---

## Surfaces checked — PASS

| Surface | Result |
|---|---|
| **SQL injection (psycopg)** | **PASS.** All runtime `conn.execute` calls in `storage.py` / `migrate.py` metadata use `%s` bound parameters (including `ANY(%s)`). No f-string / format SQL from Telegram or CSE fields. Migration body is read from local `db/migrations/*.sql` only (filesystem write ⇒ already owned). |
| **Env secret loading** | **PASS for Stage A.** `_require("TELEGRAM_BOT_TOKEN")` / `DATABASE_URL`; `.env` gitignored with `!.env.example`; empty placeholders in example; no token/DSN log sites found. |
| **Bot authz on mutate** | **PASS.** `deactivate_alert(user_id, rule_id)` and `deactivate_rules_for_symbol(user_id, symbol)` cannot cancel another user’s rules via id guessing alone. |
| **Symbol validation** | **PASS for format.** `SYMBOL_RE` rejects junk/overlong; normalize uppercases. |
| **Dash ADR decision quality** | **PASS as design.** See finding #5 for doc-drift residual only. |

---

## Out of scope / not claimed

- No `web/` binary to review — dash findings are ADR + doc consistency only.
- No live penetration of Telegram or cse.lk.
- WS-083 storm / dual-eval correctness belong to adversarial/reliability reviews; only the lock-hold side-effect is noted here.
- Compose “password koel” is ranked LOW as a **dev** exposure, not as production credential management (production DSN is still env-only).

---

## Suggested fix order (security lane)

1. Health: loopback guard + stable error codes (finding 1)  
2. Bot abuse caps / rate limits (finding 2)  
3. Log redaction: drop `chat_id` / raw `Update` (finding 3)  
4. Compose bind localhost (finding 4)  
5. Supersede WAVE1_DASH auth text → ADR 001 (finding 5)  
6. `isfinite` thresholds; lock-hold send queue (findings 6–7) when CORE touches those files  

---

## Scorecard (scoped)

| Topic | Grade | Note |
|---|---|---|
| Health exposure | Needs work | Safe default; unsafe override + rich anonymous body |
| Env secrets | OK | Stage A; compose/dev password is separate LOW |
| Advisory lock | OK (integrity) | Sticky hold correct; long hold = availability |
| Bot input validation | Format OK / abuse open | Regex + scoping good; no rate/cap |
| Dash auth ADR | Design OK | Implement against ADR, not WAVE1_DASH |
| SQL / psycopg params | OK | No injection path found |
| Log PII | Needs work | `chat_id` + Update snippets |
