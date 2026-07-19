# Security audit — Quiverly (2026-07-16)

**Auditor stance:** senior application security review; assume bugs until disproven.  
**Stack:** Next.js App Router (`web/`), Neon Postgres, Python poller/bot (`chime/`), Vercel dash, Telegram Bot API, CSE unofficial JSON, Groq AI.  
**Auth:** HMAC-signed HttpOnly `chime_session` + CSRF double-submit; demo allowlist login and optional Telegram Login Widget.  
**Not in scope today:** PayHere / payments (not implemented). No Supabase RLS (app-layer Postgres).

---

## Remediation status (updated)

| ID | Status | Notes |
|----|--------|-------|
| **S-01** | **Fixed (code)** | `requireSession` / `requireSessionAndCsrf` async + `isDashSessionRevoked` |
| **S-02** | **Ops pending** | Set `DASH_DEMO_AUTH=0` on Vercel Production — see `docs/runbooks/SECURITY_ROTATION.md` |
| **S-03** | **Ops pending** | Rotate bot / Neon / Groq / `DASH_SESSION_SECRET` — human only |
| **S-04** | **Fixed (partial)** | In-memory rate limit on `/auth/demo` + `/auth/telegram` (best-effort) |
| **S-05** | **Fixed (code)** | Full health detail only for `DASH_OPS_TELEGRAM_IDS` |
| **S-06** | Ongoing | CSRF design unchanged; CSP hygiene |
| **S-07** | **Fixed (code)** | Announce bar: removed `dangerouslySetInnerHTML`; useEffect dismiss |
| **S-08–10, S-12–15** | Deferred | Process / longer-term |
| **S-09** | Deferred | Brief product gating |
| **S-11** | **Fixed (code)** | Uniform `demo_auth_denied`; allowlist select gated by `DASH_DEMO_SHOW_ALLOWLIST` |
| **S-14** | **Ops pending** | Rotate bot token with S-03 |

---

## Findings

### S-01 — Session revocation not enforced on API routes
| | |
|---|---|
| **Severity** | **High** |
| **Location** | `web/src/lib/auth/guard.ts` (`requireSession`); contrast `web/src/lib/auth/page-session.ts:29` |
| **Issue** | Pages call `isDashSessionRevoked(sid)` after HMAC verify. **API** `requireSession` only verifies HMAC + expiry — it never checks `dash_sessions.revoked_at`. |
| **Impact** | After `POST /auth/logout-all`, a stolen/copied session cookie can still call `/api/v1/*` mutations and reads until the 12h JWT-like cookie `exp`. SSR UI may redirect to login while API remains usable (e.g. via curl/script). |
| **Fix** | Make `requireSession` async (or add `requireSessionAsync`) and reject when `isDashSessionRevoked(session.sid)`. Fail closed on DB errors for mutations; document availability tradeoff for GETs. |
| **Effort** | Medium (touch all call sites / Next route handlers). |

### S-02 — Production demo auth is a shared backdoor if allowlist leaks
| | |
|---|---|
| **Severity** | **High** (Critical if allowlist = “anyone who knows an ID”) |
| **Location** | `web/src/app/api/v1/auth/demo/route.ts`; live Vercel currently accepts at least one allowlisted Telegram ID |
| **Issue** | Demo login proves only “ID ∈ env allowlist”, not possession of that Telegram account. No password/OTP. |
| **Impact** | Anyone who learns an allowlisted `telegram_id` (screenshot, support chat, repo issue) can mint a full dash session for that user and mutate watchlists/alerts. |
| **Fix** | `DASH_DEMO_AUTH=0` on public Vercel; use Telegram Login Widget only. Keep demo for Cloud Agent / staging. Rate-limit demo endpoint. |
| **Effort** | Quick (env) + Medium (Telegram login prod wiring). |

### S-03 — Secrets exposed in chat / ops channels (operational)
| | |
|---|---|
| **Severity** | **Critical** (operational / credential compromise) |
| **Location** | Conversation history / operator paste (not committed to git at audit time) |
| **Issue** | Telegram bot token, Neon password, Groq API keys, and session secrets were pasted into agent chat. `.env` is gitignored (good), but chat logs are a leak channel. |
| **Impact** | Bot takeover (spam/phishing as Quiverly), Neon data exfil/destruction, AI quota theft, session forgery if `DASH_SESSION_SECRET` reused. |
| **Fix** | **Rotate all pasted credentials immediately** (BotFather, Neon, Groq, new `DASH_SESSION_SECRET`). Store only in Vercel/GitHub/Cloud Agent secrets. Add incident note in runbook. |
| **Effort** | Quick (rotation) — do now. |

### S-04 — No rate limiting on Next.js API (esp. auth)
| | |
|---|---|
| **Severity** | **Medium** |
| **Location** | `web/src/app/api/v1/**` (no rate-limit middleware found) |
| **Issue** | Bot has `BOT_CMD_RATE_PER_MINUTE`; dash API has none. Demo auth / Telegram login / heavy GETs (movers, stream) can be hammered. |
| **Impact** | Credential stuffing against allowlist, DB load DoS, SSE connection exhaustion (`stream/snapshots` holds ~60s). |
| **Fix** | Edge middleware or Upstash/Vercel KV rate limits: stricter on `/auth/*`, per-IP + per-user on mutations; cap concurrent SSE. |
| **Effort** | Medium. |

### S-05 — Health endpoint leaks ops telemetry to any logged-in user
| | |
|---|---|
| **Severity** | **Medium** |
| **Location** | `web/src/app/api/v1/health/route.ts` |
| **Issue** | Session-gated but not admin-gated. Returns delivery counters, retention, optional poller proxy fields. |
| **Impact** | Recon for attackers with any allowlisted demo session (retry queues, dead letters, infra hints). |
| **Fix** | Split public “ok/degraded” from admin detail; gate detail behind ops role or separate secret. |
| **Effort** | Medium. |

### S-06 — CSRF cookie is readable JS; XSS becomes account takeover
| | |
|---|---|
| **Severity** | **Medium** (depends on XSS) |
| **Location** | `web/src/lib/auth/session.ts` CSRF cookie options (non-HttpOnly by design) |
| **Issue** | Double-submit CSRF requires JS-readable cookie. Combined with any XSS, attacker reads CSRF + triggers mutations with session cookie. |
| **Impact** | Watchlist/alert manipulation, logout-all harassment, preference changes. |
| **Fix** | Keep CSP tight; audit `dangerouslySetInnerHTML` (announce bar uses static JSON.stringify — currently OK); prefer Telegram Login + short TTL; consider Origin checks. |
| **Effort** | Ongoing / Medium for CSP. |

### S-07 — `dangerouslySetInnerHTML` in marketing chrome
| | |
|---|---|
| **Severity** | **Low** |
| **Location** | `web/src/components/marketing/announcement-bar.tsx` ~93 |
| **Issue** | Inline script via `dangerouslySetInnerHTML`. Payload is built from `JSON.stringify(STORAGE_KEY)` (static), not user HTML — low risk today. |
| **Impact** | If STORAGE_KEY or script template ever interpolates user input, XSS. |
| **Fix** | Prefer `useEffect` client dismiss; avoid inline scripts. |
| **Effort** | Quick. |

### S-08 — Unofficial CSE API dependency / ToS & availability
| | |
|---|---|
| **Severity** | **Medium** (legal/ops) / **Low** (direct appsec) |
| **Location** | `chime/adapters/cse.py`, poller, `load_real_filing_metrics.py` |
| **Issue** | Relies on undocumented cse.lk JSON; no contractual SLA; IP ban / shape change risk. Scraped/fetched data is trusted into DB then shown as “metrics.” |
| **Impact** | Service outage; wrong numbers if PDF extract fails open (mitigated by `extract_ok`); possible ToS conflict. |
| **Fix** | Keep adapter isolation; never claim official CSE affiliation; validate extracts; rate-limit; document risk in terms. |
| **Effort** | Process + ongoing. |

### S-09 — AI brief prompt injection from filing text
| | |
|---|---|
| **Severity** | **Medium** |
| **Location** | `chime/briefs/` (`BRIEF_SYSTEM_INSTRUCTION`, delimiter neutralization) |
| **Issue** | PDF text is untrusted. Delimiters are neutralized and system prompt instructs ignore — good — but model can still emit misleading “facts” or attempt instruction escape. Dash renders brief as text (React escapes — good). |
| **Impact** | Phishing-like brief content in Telegram/dash; reputational/compliance harm (“AI said buy”). |
| **Fix** | Keep NFA suffix; length caps; optional allowlist of numeric claims vs extract; don’t auto-push briefs to Telegram until reviewed for high-risk users. |
| **Effort** | Medium. |

### S-10 — Neon has no Postgres RLS; authorization is app-only
| | |
|---|---|
| **Severity** | **Informational** / **Medium** if connection string leaks |
| **Location** | Neon project; `web/src/lib/db.ts` uses service connection |
| **Issue** | Unlike Supabase-with-RLS, a leaked `DATABASE_URL` is full DB access. App correctly scopes watchlist/alerts by `session.user_id` in reviewed mutation routes. |
| **Impact** | Credential leak = total data breach. |
| **Fix** | Rotate on leak; least-privilege DB role (read-only for dash if split); network allowlists; never commit URL. |
| **Effort** | Medium (roles) / Quick (rotation discipline). |

### S-11 — Demo allowlist enumeration
| | |
|---|---|
| **Severity** | **Low** |
| **Location** | `POST /api/v1/auth/demo` distinct error codes; `/login` may list allowlisted IDs via `publicDemoAllowlist` |
| **Issue** | Different errors / UI select can reveal which IDs are valid. |
| **Impact** | Helps attacker target S-02. |
| **Fix** | Uniform error messages; don’t render full allowlist in production UI. |
| **Effort** | Quick. |

### S-12 — No payment flows
| | |
|---|---|
| **Severity** | **Informational** |
| **Issue** | PayHere not present — payment category N/A. |
| **Fix** | When added: server-side signature verify, idempotency keys, never trust client amount. |

### S-13 — npm audit moderate findings
| | |
|---|---|
| **Severity** | **Low** |
| **Location** | `web/` npm audit: 2 moderate, 0 high/critical (point-in-time) |
| **Fix** | `npm audit` / Dependabot; patch regularly. |
| **Effort** | Quick–ongoing. |

### S-14 — Telegram bot token in server env; polling trust model
| | |
|---|---|
| **Severity** | **Medium** if token leaks; **Informational** design |
| **Location** | `TELEGRAM_BOT_TOKEN`; bot uses PTB polling |
| **Issue** | Token is crown jewel for outbound messaging. Incoming updates via long-poll are from Telegram API with token — not an open webhook without secret. |
| **Impact** | Leaked token → message users as Quiverly. |
| **Fix** | Rotate after any paste; restrict who can read Vercel/GitHub secrets; monitor. |
| **Effort** | Quick. |

### S-15 — SSE stream authenticated but unbounded fan-out
| | |
|---|---|
| **Severity** | **Low–Medium** |
| **Location** | `web/src/app/api/v1/stream/snapshots/route.ts` |
| **Issue** | Session required; loops 60s querying `MAX(ts)`. Many parallel EventSources per user/IP can load DB. |
| **Fix** | Per-user connection limits; longer poll interval; shared cache. |
| **Effort** | Medium. |

---

## Prioritized summary

### Fix first
1. **S-03** Rotate all credentials that appeared in chat (bot, Neon, Groq, session secret).  
2. **S-02** Disable demo auth on public Vercel; Telegram Login only.  
3. **S-01** Enforce `isDashSessionRevoked` inside API `requireSession`.  

### Next
4. **S-04** Rate-limit `/auth/*` and mutations.  
5. **S-05** Admin-gate health details.  
6. **S-09** Tighten brief publishing / NFA (product).  

### Systemic patterns
- **Auth design is strong for cookie+CSRF+allowlist**, but **revocation is inconsistent** (pages vs API).  
- **Demo auth is inherently weak** — treat as staging-only.  
- **Hardening culture is visible** (fail-closed typeof guards, body caps, loopback HEALTH_URL, SSRF redirects) — above average for a young codebase.  
- **No RLS** → DB URL is the kingdom.  
- **Mutations generally bind `user_id` from session** (watchlist/alerts) — good IDOR posture on reviewed paths.

### Quick wins
- Env: `DASH_DEMO_AUTH=0` on prod  
- Rotate secrets  
- Uniform demo auth errors  
- Replace announce-bar inline script with `useEffect`  

### Longer-term
- Async session revoke on all API guards  
- Edge rate limits  
- DB role split (dash vs poller)  
- CSP + dependency automation  
- Formal incident runbook (kill bot token, revoke sessions, rotate Neon)

---

## Attacker scenarios checked

| Scenario | Result |
|---|---|
| Spoof `telegram_id` header without session | Rejected (session is trust anchor) |
| Mutate another user’s alert by id | Blocked by `user_id` in SQL (reviewed) |
| CSRF from evil site with cookie | Needs CSRF header match (SameSite=Lax + header) |
| SSRF via HEALTH_URL | Loopback allowlist + redirect:error |
| SSRF via serverApiGet Host | Loopback / DASH_INTERNAL_ORIGIN / Vercel trusted env only |
| SQL injection via symbol query | Parameterized `$1` / `%s` in reviewed paths |
| XSS via brief text | React text nodes escape; brief sanitized server-side |

---

*This audit is point-in-time. Re-run after auth/revoke changes and before any payment integration.*
