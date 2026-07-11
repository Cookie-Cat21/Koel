# R1 — Compliance / constitution review (factory plan)

**Scope:** `CLAUDE.md`, `COMMIT_FACTORY.md`, `DASH_IA.md`, `WAVE1_DASH.md`, skim `WAVE1_CORE.md` (+ INDEX for WS-041…100 titles). Docs only.  
**Role:** Fence / non-goal / NFA / rate-limit / secret-handling reviewer for starting the implementation epoch.

---

## 1. Non-goal violations (portfolio, screener, TA, payments, competitor scrape)

**Finding: none of the planned WS-001…WS-100 implement a hard non-goal.** Catalog titles and DASH/CORE fences stay inside the thin-alert product.

| Concern | Planned surface | Verdict |
|---|---|---|
| Portfolio / P&L | Explicitly banned in WAVE1_DASH §non-goals, COMMIT_FACTORY §7, DASH_IA §5 | No WS builds it |
| Tax reports | Same | No WS |
| Screener | WS-033 caps filters; global ban listed | No WS |
| TA charts | WS-035 sparkline from `price_snapshots` only; rejects RSI/MACD/TradingView | **In fence** (COMMIT_FACTORY §7 already allows sparkline) |
| Payments / native app | Banned | No WS |
| Competitor scrape | WAVE1_DASH forbids non–cse.lk/Postgres; OPS seed avoids live CSE; adversarial holiday probe says public calendar only | No WS |

**Soft creep watch (not violations yet):**

- DASH_IA `/symbols` sparkline + “short poll optional later” — keep poll against **Postgres/API**, never cse.lk browser polling (WS-031 already forbids).
- Health page must stay facts-only (WS-037 risk note is correct).
- Empty-state / brand chrome must not invent portfolio onboarding (WS-029).

**CORE skim:** WS-001…020 are alert correctness, disclosure fidelity, adapter resilience, bot UX, and CSE-budget *reduction* (WS-003, WS-020) — all on-mission.

---

## 2. NFA disclaimer coverage gaps (dash plan)

Constitution today: *“Every **bot** response involving a price or recommendation-adjacent phrasing should carry … NFA.”* Dashboard is greenlit but compliance text is bot-only.

| Surface | DASH_IA §2 wireframe | WAVE1_DASH WS-028 | Gap |
|---|---|---|---|
| `/login` | Footer NFA | Sitewide footer | OK if footer ships with layout |
| `/watchlist` | **No** NFA called out next to price rows | NfaNotice required | **IA gap** — wireframe silent; rely on WS-028 |
| `/alerts` | NFA under price-adjacent copy | NfaNotice | OK |
| `/alerts/history` (fires) | **No** NFA (history shows triggers/prices) | NfaNotice on fires | **IA gap** |
| `/symbols/[symbol]` | **No** NFA under last price / sparkline | NFA under price | **IA gap** |
| `/health` | Ops facts | Not in NfaNotice list | Acceptable (no price UX) |
| API JSON | “may include `disclaimer`” | “NFA is **UI-only**; API returns raw facts” | **Doc conflict** |

Additional gaps:

1. **Post-mutation toasts / confirmations** (alert created, watch added) — not listed; bot always appends `disclaimer()` on those paths.
2. **Disclosure-only rows** — filing titles can be recommendation-adjacent; page-level NFA on symbol/fires covers most cases; keep copy ban on buy/sell language (WS-028).
3. **Login primary line** (“manage watchlist & alerts”) is fine; ensure hero does not imply trading advice.
4. WS-014 shrinks bot `/start` to ≤3 lines; dash `/login` must **not** drop NFA to match that budget — footer + explainer stay.

**Required before DASH Pass 1 UI claim:** reconcile DASH_IA §2 with WS-028 (every price-bearing page), and pick API policy (recommend: UI mandatory; optional `disclaimer` field on price payloads for clients — do not leave IA vs WAVE contradictory).

---

## 3. CSE rate-limit risks (dash + poller together)

**Good:** WAVE1_DASH locked decision — *Dashboard does **not** call cse.lk; Postgres only.* That is the correct compliance posture for thin dash + continuous poller.

**Bad / conflicting:**

| Source | Statement | Risk |
|---|---|---|
| DASH_IA §3 `POST /watchlist` | “validates via CSE adapter; upserts `stocks`” | User-driven dash adds hit cse.lk **outside** poller tick budget, concurrent with market-hours poller |
| DASH_IA §6 parity | “validate symbol via CSE” | Same — doubles unofficial load; looks like a second scraper from one IP |
| DASH_IA §3 conventions | “short poll optional later” | Safe if polling Chime API; unsafe if anyone “refreshes quotes” from CSE |
| CORE WS-003/020 | Bulk + disclosure-rule-only polls | Reduces load — do not undo with dash CSE calls |
| CORE/adversarial WS-096 | Circuit half-open stampede | Dash-triggered CSE on recovery worsens herd |

**Policy to lock (constitution + DASH_API):**

- Dash **read** paths: Postgres snapshots/disclosures only.
- Dash **symbol validate** on watch/alert create: prefer `stocks` table / last `tradeSummary` ingest; if live CSE probe is unavoidable, reuse poller’s adapter with the **same** global rate limiter / circuit and a hard per-minute cap (e.g. ≤1 validate call/sec shared), never a browser→cse.lk path.
- No client-side cse.lk; no HTML scrape; link-out only for disclosure URLs already stored.

Until DASH_IA is amended, treat “validates via CSE adapter” as a **compliance defect in the plan**, not an accepted design.

---

## 4. Secret handling risks (dash auth plan)

Two auth stories disagree; both have holes.

| Doc | Model | Main risks |
|---|---|---|
| **WAVE1_DASH** | Shared `DASH_API_SECRET` Bearer + client `telegram_id` / `X-Telegram-Id` | Secret holders can **impersonate any user** (IDOR by design). Cookie that stores the raw shared secret = master key in every browser. WS-085/WS-100 already name bypass/CSRF. |
| **DASH_IA** | `POST /auth/demo` + `DASH_DEMO_AUTH=1` → signed session; optional `ensure_user` | Demo gate forgotten in prod; auto-`ensure_user` creates identities without Telegram proof; `/health` “demo open” may leak ops metadata. |

Shared risks:

1. **No binding of session → `users.id` without forgeable scope** until Telegram Login verify (hash + bot token server-side). Client-supplied `telegram_id` must not be trusted alone even with a shared secret if more than one real user exists.
2. **Bot token** for future Login Widget must never ship to the browser; verify only in Route Handlers.
3. **`DATABASE_URL` in Next** — server-only env; never `NEXT_PUBLIC_*`.
4. **Cookie flags** — HttpOnly / Secure / SameSite; rotate on login; do not put master secret in localStorage (WS-023 notes this — keep).
5. **CSRF on mutations** — WS-100 must gate **before** first watchlist/alert write API ships, not after.
6. **Health** — DASH_IA allows “ops / demo open”; WAVE1_DASH requires Bearer on all `/api/*`. Pick one; prefer secret-gated health in any networked deploy (align with adversarial WS-095).

**Minimum auth ADR (WS-023) must resolve before DASH write routes:** one model; session bound to `user_id`; demo/shared-secret mode env-gated and documented as single-operator only; CSRF checklist from WS-100 as acceptance for WS-032/031 mutations.

---

## 5. Required constitution tweaks (precise paragraphs)

Apply via WS-021 (or this planning PR). Replace/append as follows.

### 5.1 CLAUDE.md — MVP §3 bot wording (conflict with thin dash)

**Current:** “Telegram bot — the only user-facing surface for v1.”

**Replace with:**

> 3. **Telegram bot** — primary user-facing surface for v1 (register, watch/alert commands, push delivery).  
> 4. **Thin web dashboard** (secondary) — watchlist, alerts, fire history, symbol detail (last price + disclosures + snapshot sparkline), poller health. Not a trading terminal; must not replace Telegram push.  
> 5. **Storage** — Postgres. …

(Renumber current storage bullet accordingly.)

### 5.2 CLAUDE.md — Compliance notes (extend beyond bot)

**After** the sentence beginning “Every bot response involving a price…”, **append:**

> The same NFA framing applies to every dashboard view and API-driven UI string that shows prices, % moves, alert thresholds, or fire history. Prefer a short sitewide footer plus a notice adjacent to price blocks. Do not use buy/sell/recommend language. Dashboards read market data from Chime Postgres (poller-written); they must not call cse.lk from the browser and must not open a second unbounded CSE client alongside the poller. Symbol validation for dash mutations uses stored `stocks` / poller data, or the poller’s rate-limited adapter under one shared budget — never a parallel scraper.

### 5.3 CLAUDE.md — Thin dashboard bullet (sparkline ≠ TA)

**Append to the existing “Thin web dashboard (greenlit…)” block:**

> Snapshot sparklines (price vs time from `price_snapshots`) are allowed. Indicator overlays, candle/OHLC charting libraries, TradingView embeds, and screener-style multi-symbol discovery are not. Auth for v1 may be a staging/demo gate; production identity must bind to the Telegram user row without trusting a bare client-supplied `telegram_id` alone.

### 5.4 COMMIT_FACTORY.md — Dashboard fence (CSE + auth one-liners)

**Append under §7 “Allowed in DASH lane”:**

> Data plane: Postgres only for reads. No browser→cse.lk. Any server-side CSE use for symbol validate shares the poller rate limiter.  
> Auth: document one ADR (`DASH_AUTH.md`); mutating routes require CSRF-safe session bound to `users.id`; `DASH_DEMO_AUTH` / shared-secret modes are single-operator and must not be default in production.

### 5.5 DASH_IA.md (plan fix, not CLAUDE — still required)

- §2: add NFA lines to `/watchlist`, `/alerts/history`, `/symbols/[symbol]` matching WS-028.  
- §3 `POST /watchlist`: remove “validates via CSE adapter”; point at Postgres/`stocks` or shared rate-limited path.  
- §3 API disclaimer: align with WAVE1_DASH (UI mandatory; API optional).  
- §4 vs WAVE1_DASH auth: pick **one** v1 scheme in WS-023 and make the other doc defer to it.

---

## 6. Go / no-go for starting implementation epoch

| Gate | Status |
|---|---|
| Non-goals vs WS catalog | **Pass** — no portfolio/screener/TA/payments/competitor-scrape WS |
| NFA on dash | **Conditional** — WS-028 intent good; DASH_IA incomplete; CLAUDE bot-only wording |
| CSE rate limits dash+poller | **Fail until doc fix** — DASH_IA CSE validate conflicts with WAVE1_DASH Postgres-only |
| Dash secrets / auth | **Fail until ADR** — dual auth stories + forgeable `telegram_id` scope |
| Constitution internal consistency | **Fail until §5.1–5.3** — “only user-facing surface” vs greenlit dash |

### Verdict: **CONDITIONAL GO**

- **GO** to start the implementation epoch for **CORE** (WS-001+), **OPS** (CI/compose), and **DASH scaffold / read-only** (WS-021…030 style) **after** landing the §5 constitution + DASH_IA CSE/NFA doc fixes (can be the first commits of the epoch / WS-021).  
- **NO-GO** on **DASH mutating APIs and login that stores a master secret as the session** until WS-023 ADR reconciles auth and WS-100 CSRF checklist is in the acceptance criteria for write routes.  
- **NO-GO** on any dash or bot path that adds a **second unbounded cse.lk client**.

Clear line: **do not treat the factory plan as fully compliance-cleared for full DASH CRUD; clear it for CORE/OPS + DASH docs/scaffold once §5 edits merge.**
