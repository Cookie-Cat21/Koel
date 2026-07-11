# R1_DASH — Adversarial plan review (thin dashboard)

**Reviewer role:** Adversarial (docs only)  
**Inputs:** `COMMIT_FACTORY.md`, `DASH_IA.md`, `WAVE1_DASH.md`, `CLAUDE.md`, `RESOURCES.md`  
**Date:** 2026-07-11  
**Verdict target:** Ruthless, accurate, fence-preserving

---

## 1. Verdict

**CONDITIONAL REJECT — do not implement product code until contracts converge.**

Direction is right: Telegram remains push; dash is CRUD + inspection; Postgres-only; explicit non-goals. That is salvageable.

The plan is **not** implementation-ready. `DASH_IA.md` and `WAVE1_DASH.md` disagree on auth, routes, cancel semantics, API prefix, health exposure, and error envelopes — agents will fork. Auth as specified (`Bearer` secret + client-supplied `telegram_id`) is an impersonation model, not identity. Constitution is half-amended: CLAUDE thin-dash fence exists, but MVP still says Telegram is the only surface, and `RESOURCES.md` still brands web as **OUT OF SCOPE**. Pass 1 in `COMMIT_FACTORY` §9 (scaffold + read-only watchlist) is drowned by a 20-WS wave that ships full CRUD, sparkline, health UI, and smoke E2E before a single locked API ADR.

**Ship gate:** Resolve IA↔WAVE conflicts in one canonical contract (`DASH_API.md` + `DASH_AUTH.md`), finish constitution trilogy (CLAUDE MVP leftover + RESOURCES), then run Pass 1 as the five WS in §6 — nothing else.

---

## 2. Ranked plan improvements (max 15)

1. **Freeze one auth model.** Kill the split between IA’s `POST /auth/demo {telegram_id}` and WAVE’s `Authorization: Bearer DASH_API_SECRET` + `X-Telegram-Id`. Pick one story, write `DASH_AUTH.md`, delete the other from the sitemap.
2. **Never treat client-supplied `telegram_id` as proof of identity** when the only gate is a shared operator secret. That is “operator can act as any user,” which is fine for single-tenant staging **only if documented**; it is catastrophic if framed as multi-user auth. Bind scope server-side after login (session → `user_id`), not per-request header spoofing.
3. **Do not store `DASH_API_SECRET` in the session cookie.** WAVE WS-023 acceptance says the cookie may hold the secret. That couples XSS/CSRF blast radius to the long-lived ops credential. Issue an opaque server session (or signed short-lived token) derived after secret check; keep the secret env-only.
4. **Unify API surface before WS-025.** One prefix (`/api/v1` *or* `/api`), one fires route (`/alerts/history` *or* `/alerts/fires`), one cancel verb (`DELETE` soft-cancel *or* `PATCH {active:false}`), one error envelope. Today IA and WAVE contradict on all four.
5. **Mandate Storage parity, not “inspired by” SQL in Route Handlers.** Bot `create_alert_rule` auto-watches; `unwatch` deletes watch + `deactivate_rules_for_symbol`; cancel is soft `active=false`; duplicate active rules are deactivated-then-insert, not always 409. WAVE’s DELETE watchlist → 204 with no deactivate count, and WS-032’s “recommend auto-watch” are still undecided — that is a fence-level bot/UI split.
6. **Finish the constitution trilogy in WS-021.** CLAUDE thin-dash paragraph is greenlit, but MVP §3 still says Telegram is the *only* user-facing surface; `RESOURCES.md` “Web phase (OUT OF SCOPE)” contradicts COMMIT_FACTORY §7. Amend both or agents will cite the wrong doc.
7. **Absorb adversarial WS-085 / WS-100 into DASH_AUTH before any write API.** CSRF, `Secure`/`HttpOnly`/`SameSite`, session rotation on login, no forged Telegram widget hashes. WAVE barely nods at XSS; CSRF is absent from DASH WS text.
8. **Cut Pass 1 to COMMIT_FACTORY §9.** Scaffold + auth stub + read-only watchlist. Defer alert CRUD, fires UI, sparkline, disclosures panel, health page polish, Playwright matrix (WS-032–039) to Pass 2+.
9. **Strip quote-board fields from the symbol contract for v1 UI.** IA’s `PriceSnapshotFields` includes `high`/`low`/`open`/`market_cap`. Allowed to exist in DB; **do not render** a mini Level-1 board. Surface: last, change, change_pct, volume, ts — then disclosures. Sparkline optional Pass 2.
10. **Lock health auth.** IA: “ops / demo open.” WAVE: Bearer on all `/api/*`. Open health leaks poller freshness and error strings; secret-gated health blocks anonymous uptime checks. Decide: public liveness subset vs authenticated ops detail — document both shapes.
11. **Forbid a second domain layer in `web/`.** Prefer calling shared Python semantics (subprocess/service) *or* a thin typed SQL module that mirrors `chime.storage` method-for-method. Ad-hoc Next SQL will drift on unique-active, armed, and unwatch side effects.
12. **NFA ownership.** WAVE: “NFA UI-only.” IA: optional `disclaimer` on price JSON. Pick UI chrome (WS-028) as source of truth; do not half-implement API disclaimers that clients ignore.
13. **Design-token anti-pattern list in WS-026.** Ban broker denseness: multi-column quote tables, purple-glow shadcn defaults, Tremor/Aceternity chart kits from RESOURCES, live tick animations, “Market” nav. Brand-readable ≠ marketing hero on every page.
14. **Explicit refresh policy.** IA says no WebSocket; WAVE is silent on client polling. Pass 1: navigation refresh only. Any `setInterval` quote poll invites “terminal that must stay open” — the product anti-goal.
15. **Resolve cancel/list filters.** IA `GET /alerts?active=true` + DELETE cancel; WAVE PATCH only. Bot `/myalerts` lists active only. Dash must default to active; showing armed badges is good — building a full rule archive browser is not Pass 1.

---

## 3. IA vs WAVE1_DASH inconsistencies

| Topic | `DASH_IA.md` | `WAVE1_DASH.md` | Risk |
|---|---|---|---|
| **Auth** | `POST /api/v1/auth/demo` with `telegram_id`; signed session; `DASH_DEMO_AUTH=1` | Shared secret Bearer + `X-Telegram-Id` / query; `/login` enters secret | Two implementations; wrong security story |
| **Telegram Login** | Future real widget verifying hash | Stub only (disabled button) | OK if deferred — but IA still sketches real endpoint; freeze stub |
| **API prefix** | `/api/v1/...` | `/api/...` | Client/codegen thrash |
| **Fire history route** | `/alerts/history` + `GET .../alerts/history` | `/alerts/fires` + `GET .../alerts/fires` | Nav + deep links diverge |
| **Nav label** | History | Fires | Copy inconsistency |
| **Cancel alert** | `DELETE /alerts/{id}` → soft cancel | `PATCH /alerts/[id]` `{active:false}` | Bot maps to `/cancel`; pick one HTTP shape |
| **Unwatch** | Response includes `deactivated_alerts` | `204` / `404` only; no deactivate mentioned in table | **Bot parity break** (bot deactivates on unwatch) |
| **Health auth** | “ops / demo open” | Bearer required unless noted | Accidental public ops leak or broken probes |
| **Error envelope** | `{ "error": string, "code"?: string }` | `{ error: { code, message } }` | Client error handling forks |
| **NFA** | May appear on API responses | Explicitly UI-only | Dual truth |
| **API host** | Prefer FastAPI/Starlette *or* Next handlers wrapping storage | **Locked:** Next Route Handlers + `DATABASE_URL` only | IA “non-binding” vs WAVE “locked” — agents will argue |
| **Ship order** | Read-only watchlist + auth → alerts → symbol → history → health | Parallel CRUD streams 031–037 after read API | Overbuilds Pass 1 |
| **Watchlist POST** | Validates via CSE adapter; upserts stocks | Postgres only; ensure stocks — **no cse.lk** | IA implies live CSE validate from dash path; WAVE forbids dash→CSE. Resolve: validate against `stocks` + poller data, or sync path via Python only |
| **Disclosure item id** | `id` | `external_id` | Fixture/contract mismatch |
| **Symbol `last` shape** | Full OHLC + market_cap | Slimmer last object | UI temptation from IA fields |

**Doc debt already true in tree:** CLAUDE thin-dash unlocked; `RESOURCES.md` still “OUT OF SCOPE for v1”; CLAUDE MVP §3 still “only user-facing surface” = Telegram. WS-021 acceptance criteria are correct and **not yet satisfied** by RESOURCES / MVP leftover.

---

## 4. Auth / security holes in the plan

1. **Shared secret + caller-chosen `telegram_id` = universal impersonation.** Anyone with the secret reads/writes every user’s watchlist, alerts, and fire messages. Fine for solo staging; **not** “auth.” Plan must say: single-operator tool; production requires Telegram Login (or equivalent) before multi-user deploy.
2. **Secret-in-cookie (WS-023).** httpOnly helps against XSS theft; CSRF still attaches the cookie. Mutating routes need SameSite + origin checks / CSRF token. WAVE has no CSRF acceptance criterion (WS-100 exists in ADVERSARIAL wave — not wired into DASH deps).
3. **No session rotation / fixation story** in DASH WS text (WS-100). Login must mint a new session id after secret check.
4. **Demo `ensure_user` on arbitrary telegram_id** (IA) creates users and alert namespaces without Telegram proof — account spam / confusion with real bot users.
5. **Telegram widget stub risk (WS-038).** Plan correctly warns against forged hashes; acceptance must state: stub **must not** call verify endpoints or accept `hash` params.
6. **`DATABASE_URL` inside Next** expands blast radius: XSS/RCE in the dash app = full DB. Mitigate later with least-privilege DB role (SELECT/INSERT/UPDATE on dash tables only; no DDL). Not mentioned.
7. **Health detail leakage.** Poller errors, symbol counts, timestamps help attackers map ops; “demo open” is careless.
8. **Bearer-from-browser CORS.** If a separate origin ever appears, preflight + credentialed requests need an explicit deny-by-default CORS policy. Unstated.
9. **No rate limits / audit** on alert create/cancel from web — malicious or buggy UI can thrash rules and Telegram noise.
10. **`.env.example` secret keys without “never deploy with demo auth” runbook** — WAVE rejects open-network verbally; needs a hard fail-closed default (`DASH_API_SECRET` required, empty secret = refuse to boot API).

---

## 5. UX / design-system risks vs CLAUDE thin-dash fence

CLAUDE fence: dash is **secondary**, not a place users are expected to live; not a trading terminal; Telegram remains the ping channel.

| Risk | Why it violates the fence |
|---|---|
| **Full app shell + bottom nav (WS-026/027)** | Reads as a primary product surface. Keep chrome minimal; avoid “daily driver” IA. |
| **Symbol page = quote + sparkline + disclosures + watch/alert CTAs (WS-035/036)** | Densest route; easiest to slide into CSE Tracker Pro lite. Cap content; no OHLC board. |
| **Sparkline (WS-035)** | Allowed as “not TA,” but agents grab chart libs. Hard-ban `ta`, TradingView, candle/volume profile; SVG polyline from snapshots only — or defer. |
| **Live refresh / short poll** | Turns dash into the thing that must stay open — exact competitor failure mode Chime exists to avoid. |
| **shadcn defaults + RESOURCES kits** | RESOURCES still lists Tremor, Aceternity, HyperUI, etc. under a stale “out of scope” header — magnet for glossy dashboard chrome and purple gradients. Retitle and **remove chart kits** from the active pointer list. |
| **WS-026 “brand-readable first viewport” on `/watchlist`** | Conflicts with utilitarian management UI; over-read as marketing hero. Brand belongs strongest on `/login`; app pages stay quiet. |
| **Armed/active badges + filters (WS-033)** | Fine at bot parity; “screener-like filters” already flagged — enforce symbol search only, no multi-sort market browser. |
| **Health as a page in primary nav** | Ops surface in user nav trains a monitoring habit. Consider de-emphasizing (footer link) or auth-gate separately from watchlist. |
| **Empty states that onboard into “portfolio” language (WS-029)** | Plan warns; keep CTAs to add symbol / open Telegram — never quantities or P&L. |

Quality bar #8 is necessary; it must not be satisfied by looking like a broker.

---

## 6. Top 5 DASH WS for Pass 1

Aligned with `COMMIT_FACTORY` §9 (“scaffold `web/` + read-only watchlist”) and security-first sequencing:

| Priority | WS | Why Pass 1 |
|---|---|---|
| 1 | **WS-021** | Constitution + RESOURCES must match fence before code; currently inconsistent. |
| 2 | **WS-023** | Auth ADR (opaque session, no secret-in-cookie, CSRF, fail-closed empty secret); blocks unsafe API. |
| 3 | **WS-024** | Single API contract resolving §3 conflicts; fixtures under `docs/sample_responses/dash/`. |
| 4 | **WS-025** | Runnable `web/` scaffold + THIRD_PARTY + gitignore. |
| 5 | **WS-030** | Read-only `health` / `me` / `watchlist` + tests; proves DB wiring without mutation blast radius. |

**Pass 1 adjuncts (optional, thin):** WS-038 login/cookie guard **only** as much as needed to call WS-030; WS-031 **read-only** list UI (no POST/DELETE until Pass 2).  

**Explicitly not Pass 1:** WS-032–037 (mutations, fires, sparkline, disclosures UI, health page), WS-039 full E2E matrix, WS-026/027 polish beyond a bare layout.

---

## 7. Kill list — WS / scopes that would accidentally build a trading terminal

Reject or surgically neuter if a commit drifts:

| Item | Kill condition |
|---|---|
| **WS-035 sparkline** | Any TA library, candle chart, volume profile, RSI/MACD, TradingView embed, multi-timeframe selector. Prefer defer to Pass 2; if kept: SVG from `price`/`ts` only. |
| **WS-035 / IA `PriceSnapshotFields` UI** | Rendering high/low/open/market_cap as a quote board or “market depth” block. |
| **WS-031 watchlist** | Browser calls to cse.lk; WebSocket; sub-second auto-refresh; portfolio columns (qty, avg cost, P&L). |
| **WS-033 alerts UI** | Strategy builder, boolean rule trees, trailing stops, backtest, quiet-hours suites, screener filters. |
| **WS-034 fires** | “Resend Telegram,” analytics funnels, export-to-tax, P&L impact. |
| **WS-026/027 shell** | Multi-pane terminal layout, watchlist+chart split view, ticker tape, densified broker tables. |
| **WS-037 health** | Deploy controls, log viewers, rate-limit knobs, metrics product / Grafana clone. |
| **WS-036 disclosures** | In-app PDF readers, scraped news beyond stored CSE rows, competitor embeds. |
| **RESOURCES web kits** | Tremor / Aceternity / chart-heavy blocks as implementation targets — kill from active stack pointers. |
| **Any new WS** | Order book, peer screener, sector heatmap, ASPI widget as primary nav, payments, teams. |

**Meta-kill:** Implementing WAVE WS-021–040 as one Pass 1 “wave” in parallel agents. That is a feature flood dressed as planning execution — violates COMMIT_FACTORY Pass 1 intent and concurrency discipline.

---

## Reviewer note

Fence-preserving path: **docs converge → Pass 1 read-only → mutations with Storage parity → symbol/fires later.** Anything that makes the browser the place you stare at during market hours is a product failure, even if the code is clean.
