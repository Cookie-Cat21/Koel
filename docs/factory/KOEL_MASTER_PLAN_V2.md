# koel Master Plan V2 — Win the CSE alert layer (July 2026)

**Status:** Active — supersedes [KOEL_MASTER_PLAN.md](KOEL_MASTER_PLAN.md) (V1, which
still says "Wave 6 next" and brands the product "Quiverly"; V1's fence tables remain
valid history but this doc is the operating plan).
**Authority:** [CLAUDE.md](../../CLAUDE.md) · [DASH_CAKE_CHERRY.md](DASH_CAKE_CHERRY.md) ·
[TIJORI_CSE_PLAN.md](TIJORI_CSE_PLAN.md) · [COMMIT_FACTORY.md](COMMIT_FACTORY.md)
**Research basis:** competitive + product-practice research run 2026-07-21 (summarized
in §1–§2; sources inline).

---

## 0. Thesis

**koel = the alert layer for the Colombo Stock Exchange.**
The dash is where you *see* the market daily; Telegram is how the market *reaches you*
when you're away. Everything in this plan serves one sentence:

> *"When something you care about happens on the CSE, koel tells you first,
> tells you why, and is never wrong about the facts."*

Three pillars, in priority order:

1. **First** — fire latency from event to Telegram measured in seconds-to-a-minute,
   bounded by poll cadence, not by product design.
2. **Why** — every fire carries context: the disclosure brief, the sector move, the
   "as of HH:MM" provenance. Nobody local does "why it moved."
3. **Never wrong** — deterministic rule engine, verified AI summaries (fall back to
   title+link over a wrong number), honest staleness/degradation notices. Trust is
   the moat in a market whose official app has store reviews full of login/crash
   complaints and whose indie tools are single-founder trust risks.

---

## 1. Market reality (verified July 2026)

### 1.1 The wedge is validated and still open — but the window is narrowing

| Player | Alerts capability | Verdict |
|---|---|---|
| **CSE Tracker Pro** (Rs. 300/mo) | Price alerts **explicitly browser-open-only** (their own help text: "Browser open ඇති විට only"). No disclosure alerts at all — their news section says "visit cse.lk". Manual bank-transfer billing. | Feature-broad (portfolio, tax, screener, Sinhala UI) but the push gap is untouched. |
| **Official CSE app** (updated Jun 2026) | Category-level pushes only (disclosures/market/news buckets); **no user-defined per-stock thresholds**. Store reviews dominated by login/crash complaints. | Distrusted incumbent; validates demand for reliable notification. |
| **ATrad terminals** (24 brokers) | Popup/SMS/email alerts exist — but locked inside broker terminals, broker-config dependent, dated UX. | Broker-locked; koel is broker-agnostic. |
| **Pulse Radar / CSE Market Pulse** (launched Jun 2026, Rs. 2,490/mo) | Real-time **momentum** alerts "to your device". Onboarding = DM the founder. | **Closest direct competitor.** Momentum-only, not user-defined thresholds, 8x koel's likely price point. First mover pressure — ship the cherry loudly. |
| **Rovana AI** (Rs. 2,990/mo) | Daily intelligence **email** at 6:30 PM; quant scores; no real-time push. | Validates AI-brief demand and PayHere recurring billing locally. |
| **Ceyport** (free beta) | Dividend calendar + analytics; alerts on roadmap, not shipped as push. | Watch; overlaps calendar surfaces, not push. |
| **InvestNow / stocklk_bot / GrahamWise** | Pay-per-analysis AI, Telegram Q&A, value screener — none do threshold push. | Validate Sinhala + Telegram demand. |
| **TradingView** (embedded in MyCSE since 2023) | Server-side push alerts exist on delayed CSE data for paid TV users. | The savvy-user escape hatch; koel counters with disclosures, LKR pricing, zero-setup Telegram. |

**Nobody in Sri Lanka delivers user-defined price/move/disclosure alerts as real push.**
That was true when CLAUDE.md was written and it is still true — but June 2026 brought
Pulse Radar, so "still true" now has an expiry date.

### 1.2 Sizing honesty

CDS crossed **1M accounts (Mar 2026)** but accounts ≠ active investors: CSE's 2024
annual report shows ~718k investors, retail/institutional turnover split roughly even,
~19k new CDS accounts in 2024. The realistic alert-caring segment is **tens of
thousands**, not a million. Design for a niche prosumer product with excellent
retention, not mass-market growth curves.

### 1.3 Pricing anchors now exist locally

Rs. 300/mo (Tracker Pro) · Rs. 2,490/mo (Pulse Radar) · Rs. 2,990/mo (Rovana).
Regional: Tijori Finance $4/mo (free tier = 1 watchlist + 5 alerts); Tijori Alerts
$250/yr. koel's credible band when monetization unlocks: **Rs. 300–1,000/mo**,
undercutting Pulse Radar 3–8x while doing strictly more (user-defined rules +
disclosures + AI briefs vs momentum-only).

### 1.4 The Tijori playbook (the model to adapt)

Zerodha put $5M into Tijori Alerts (Nov 2025): AI-summarized filings on WhatsApp in
20–60s, ~4,000 filings/day, category-level customization, free trial capped at 25
stocks. Three transferable lessons:
1. **Filings, not just prices, are the alpha** — CSE announcements are PDFs nobody
   reads in time; koel already has the PDF-enrich pipeline built.
2. **Speed is the differentiator, not summary eloquence** — 80% of Tijori alerts land
   under 90s; for koel the bottleneck is announcement poll cadence, not the LLM.
3. **Messaging-app delivery beats another app install** — validated for this exact
   product shape; Telegram is Sri Lanka's equivalent surface.

### 1.5 Data-source risk check

No official CSE API or policy change announced through July 2026. Community repos
(updated Jan 2026) confirm the JSON endpoints still work with browser-like headers,
but some (`detailedTrades`, `mostActiveTrades`) are now session-guarded/rate-limited
and aggressive scrapers report IP bans. koel's polite bulk `tradeSummary` polling and
one-file-fix adapter layer remain exactly right; §6 hardens this further.

---

## 2. Where koel already stands (audit 2026-07-21)

Far ahead of what V1's "immediate next action" implies. Shipped and hardened:

- **Engine:** 15s market-hours poller, market-wide snapshot persist, advisory-lock
  safety, circuit breaker, delivery leases + dead-letter, EOD digest path, ~228 test
  files with a 70% coverage gate.
- **Rules:** 34 alert types across price/move/disclosure/activity/order-book/filing
  metrics/regime/dividends/corporate actions, **with rearm semantics already
  implemented** (`koel/rules.py`) — the self-spam bug that plagues naive alert
  engines is already solved.
- **Bot:** full CRUD + `/brief`, rate-limited, NFA framing.
- **Dash:** Overview/Browse/Watchlist/Alerts/History/Symbol/Signals/Appetite/Context/
  People/Graph/Dividends/Settings/Health, session auth + CSRF, Cmd+K, quiet hours +
  digest prefs, per-user alert quotas (monetization scaffolding already in schema).
- **Flag-gated, built but off:** AI briefs (`AI_BRIEFS_ENABLED=0` — full
  Gemini/Groq/OpenRouter pipeline exists), Telegram Login (`DASH_TELEGRAM_LOGIN`),
  macro ingests, ML forecast serve.

**The strategic read:** koel's remaining distance to "best product in the market" is
not more surface area. It is (a) **turning on and hardening the differentiators that
are already built**, (b) **closing a short list of high-value gaps** competitors
charge for, and (c) **distribution + trust**, where nothing has been done yet.

---

## 3. Horizon 1 — Cherry supremacy (make the alert layer undeniably best)

Goal: any comparison table a CSE investor could draw has koel winning the alert
column outright. Everything here is fence-legal today.

### W1. Turn on AI disclosure briefs — with a verification gate ⭐ highest leverage

The single feature no local player ships (Rovana = daily email; InvestNow =
pay-per-analysis; Tracker Pro = nothing) and koel's pipeline already exists behind
`AI_BRIEFS_ENABLED=0`.

- Enable per runbook `docs/runbooks/AI_BRIEFS_ENABLE.md` with Gemini Flash-Lite
  (Tijori itself uses Gemini; cost at CSE volume ≈ single-digit USD/month, batch 50% off).
- **Hard safety rule:** the LLM only ever sees fetched PDF text, never answers from
  memory; every number in the summary is regex-verified against source text;
  verification failure → ship "New disclosure: [title] (link)" with **no** summary.
  A degraded-but-true alert beats a wrong summary, especially under SEC Sri Lanka
  market-misconduct exposure.
- Every brief carries the filing link + "AI-generated summary — check the filing. NFA."
- **Measure the latency**: announcement-publish → Telegram delivery. Target p80
  ≤ 2 poll cycles + brief generation; publish the number (it's marketing).

### W2. Alert types that complete the set

Two universal alert types competitors offer that koel lacks — both computable from
data already in Postgres:

- **`high_52w` / `low_52w`** — new 52-week high/low (Robinhood/Fidelity standard),
  from `daily_bars`/snapshot history. Ship with the Robinhood-style built-in cap:
  max one high + one low per symbol per week.
- **`ma_cross`** — price crossing the 20/50/200-day MA (Fidelity's exact set;
  Sentinel-class). Daily closes only; no TA-terminal creep — it's one number crossing
  another, same shape as `price_above`.
- **Reference-price move** — `/alert SAMP move 5 from 82.50`: % move relative to a
  user-supplied reference (ports Tracker Pro's one clever browser-locked idea —
  "% from avg cost" — to push, without koel storing positions; the user brings the
  number, the P2 fence stays intact).

### W3. Natural-language alert creation (parser only)

Users already type sentences at a bot. "tell me if JKH drops 5%" → Gemini Flash-Lite
parses to a structured rule → bot echoes the exact rule back with ✅ Confirm /
❌ Cancel inline keyboard → existing deterministic engine does the watching.

- LLM is **never** the evaluator; zero hallucination risk in what fires.
- Unparseable → fall through to existing `/alert` syntax help.
- This also becomes the fallback for malformed `/alert` commands (parse errors turn
  into suggestions instead of usage text).

### W4. Button-first bot revamp

Highest UX return per line of code on the primary acquisition surface (every local
competitor requires web signup or DMing a founder; koel's `/start` → watching a
symbol should take 15 seconds):

- `/start` = short hero + inline keyboard (📈 Watch a symbol · 🔔 My alerts ·
  📋 Watchlist · ❓ How it works), not a command wall.
- Edit-in-place menus (`editMessageText`), immediate `answerCallbackQuery`,
  state-in-label toggles (`⏸ Paused` / `▶️ Active`), two-step confirm on deletes.
- Every fire message gets inline buttons: [View on dash] [Pause rule] [Watch more like this].
- Deep links both ways: `t.me/<bot>?start=sym_JKH` from dash symbol pages
  ("manage in Telegram"), and dash URLs in fire messages. Two surfaces, one product.

### W5. Fires that explain themselves ("why it moved")

Pulse Radar tells you *that* it moved; nobody tells you *why*. On every price/move
fire, attach one line of context assembled from koel's own Postgres facts:
latest disclosure for the symbol (if <48h old), sector move, index move,
volume vs 30-day average. No LLM needed for v1 of this — template from facts.

### W6. Trust chrome on every message and tile

- **Provenance:** "as of 13:42" freshness stamp in every Telegram fire and dash
  price tile, computed from last trusted snapshot (not connection state).
- **Gap-aware move alerts:** suppress or annotate %-move fires computed across a
  poll gap ("price moved 6% since our last reading 40 min ago").
- **Automated degradation notice:** the poller's health state machine drives a bot
  broadcast + dash banner ("⚠️ cse.lk data delayed since 10:15; next update 11:00")
  with investigating → identified → monitoring → resolved discipline. At koel's
  scale this *is* the status page, and honesty about the unofficial upstream
  converts a liability into a trust signal.

**Exit criteria for Horizon 1:** AI briefs live and soaked through ≥10 market
sessions with zero wrong-number incidents; fire latency p80 published on `/health`;
all four new alert types creatable in bot + dash (parity matrix updated); NL
creation confirmed-rule rate >80% on real usage.

---

## 4. Horizon 2 — Distribution, retention, and the daily habit

The product is ahead of its distribution. Nothing below adds engine complexity;
all of it compounds users.

### W7. Public koel Telegram channel (top of funnel)

Market-wide content with zero per-subscriber send cost: 09:35 open pulse, 14:45
close summary (ASPI/S&P SL20, top movers, disclosure headlines), big-print callouts.
Every post deep-links into the bot ("get this for *your* stocks → @koelbot").
This is free, compounding marketing that also demonstrates the product working
in public every trading day.

### W8. Daily close digest as the default hook (~14:45 SLT)

The digest path exists (`digest_enabled`, default off). Flip the framing: the
non-trader majority of CDS holders is over-served by real-time and under-served by
summary. Onboarding offers "Daily summary at market close?" as a one-tap yes.
Content = watchlist movers, disclosures filed, alerts fired, all from Postgres facts;
LLM writes prose only (Rovana proves the format; Telegram beats email in Sri Lanka).

### W9. Sinhala (then Tamil) alert language

Tracker Pro's Sinhala UI and stocklk_bot's Sinhala Q&A prove demand; no push product
offers alert messages in the user's language. Message templates are short and
enumerable — translate the template strings, add `/language සිංහල`, store per-user
locale. AI briefs can render Sinhala via the same Gemini call at negligible cost.
This single feature is a moat against any global tool (TradingView will never do it).

### W10. Results-day ownership

Quarterly results are the highest-attention recurring event on the CSE. Combine the
financial-announcement feed + filing-metrics extract (already built) into:
"📊 SAMP.N0000 Q1 results filed — EPS Rs 4.20 (▲ 18% YoY). Brief: … (link)".
Ceyport lists quarter reports passively; koel makes results day a push event it owns.
This is also the natural showcase for the `eps_yoy_*` alert types that already exist.

### W11. Telegram Login as the production dash auth

`DASH_TELEGRAM_LOGIN=1` path already exists (ADR 001). Making it production-default
collapses the identity story: one Telegram identity across bot and dash, no password,
and the dash becomes the natural upgrade surface from the bot. (Mini App slice of
the dash — watchlist + alert manager — is the follow-on once flows outgrow inline
keyboards; Bot API 2025–26 additions like Stars subscriptions and
`sendRichMessageDraft` streaming reward this later, not now.)

### W12. Alert accountability surfaces

- Fire history with outcome context: "fired at 102.50 → now 104.00 (+1.5%)" in
  `/myalerts` history and the dash History page.
- Backtest credibility line at rule creation: "this rule would have fired N times
  in the last quarter" — computed from koel's own snapshot history, which is
  quietly becoming **the only independent intraday CSE history outside the
  exchange**. No new entrant can copy that quickly; start spending it.

**Exit criteria for Horizon 2:** channel posting automatically every session;
digest opt-in rate >40% of new users; Sinhala templates live; results-day pushes
fired for one full earnings season; Telegram Login is the default prod auth.

---

## 5. Horizon 3 — Monetization (unlock P5 deliberately)

Do not gate Horizon 1–2 features retroactively on users who already have them;
grandfather generously. Local anchors make this credible for a small operator.

### W13. Tier design (Tijori-pattern, CSE-priced)

| | Free | Pro (Rs. 490/mo · Rs. 3,900/yr initial hypothesis) |
|---|---|---|
| Watchlist | 5 symbols | Unlimited |
| Price/move rules | 3 active | Unlimited |
| Disclosure alerts | title + link | **AI brief included** |
| New alert types (52w, MA-cross, reference-move) | — | ✓ |
| Daily digest | ✓ (retention hook stays free) | ✓ + AI prose |
| Rule evaluation cadence | every 2nd–3rd poll cycle | every poll |
| Sinhala alerts | ✓ | ✓ |

Latency tiering is honest to implement (koel owns the poller) and is the one lever
that maps directly to perceived value ("Pro hears it first"). Price beneath Rs. 1,000
to make Pulse Radar's Rs. 2,490 momentum-only offer look absurd.

### W14. Payment rails

1. **PayHere Lite first** (zero fixed cost, 3.90%, one-time payments): sell 6-month
   and annual passes exactly like Tracker Pro's periods but with a real checkout
   instead of manual bank transfer + WhatsApp slip. Wallets included (eZ Cash,
   FriMi, Genie).
2. **Upgrade to PayHere Plus + Recurring API** (Rs. 2,990/mo fixed + 2.99%) only when
   MRR clears the fixed cost comfortably.
3. **Telegram Stars as secondary in-bot rail** (impulse upgrades, diaspora users) —
   accept the ~30% mobile-path haircut and 21-day Fragment/TON withdrawal friction;
   never make it primary.

The quota scaffolding (`alert_quota_max`, per-user prefs) already exists in schema —
the paywall becomes a config change, which is exactly what V1 intended.

**Exit criteria:** first 50 paying users; churn <5%/mo; payment support burden
< a few messages/week.

---

## 6. Always-on workstream — Engine trust (never a "phase")

The unofficial upstream is koel's existential risk. These run continuously:

- **Per-endpoint circuit breakers** — `koel/circuit.py` exists; ensure independent
  breakers per adapter endpoint (`tradeSummary` failing must not stop
  `approvedAnnouncement` polling), jittered backoff, every failure logged. Backing
  off fast is both resilience and don't-get-blocked hygiene.
- **Feed state machine** per source: LIVE / STALE / FALLBACK / RECOVERING — drives
  W6 degradation notices, dash banners, and %-move suppression from one truth.
- **Four SLOs on `/health`:** snapshot freshness p50/p95 during market hours;
  per-endpoint error rate; rule-eval lag per snapshot; fire→Telegram-ack latency.
- **Fan-out headroom:** a market-wide event (ASPI circuit day) can fire hundreds of
  rules in one tick; the queue + `retry_after` handling must be load-tested to
  Telegram's ~30 msg/s global cap.
- **Adapter watchdogs:** endpoint-shape canaries (the probe suite) run weekly;
  cse.lk churn (e.g. `detailedTrades` session-guarding) is detected by koel before
  users notice.
- **Per-event-class caps** (Robinhood pattern): one 52w-high fire per symbol per
  week; one disclosure fire per filing; per-user daily cap with
  "N more suppressed — see /digest" overflow.

---

## 7. Fence review — what changes, what doesn't

| Fence item | Ruling |
|---|---|
| Portfolio qty/cost/P&L (P2/P3) | **Still deferred.** W2's reference-price move deliberately delivers 80% of the user value without positions. Revisit only after Horizon 3 revenue proves demand. |
| Tax reports | Still out. Tracker Pro owns it; low synergy with the alert wedge. |
| Heavy screener / TA terminal | Still out. MA-cross alerts ≠ TA terminal (one crossing, same shape as price_above). Signal Board stays research-scores-only, NFA. |
| Native mobile app | Still out. Telegram + dash (+ future Mini App / PWA at P4) cover it. |
| Payments | **Unlocks at Horizon 3** (this was always P5; the plan now specifies rails and tiers). |
| Compliance | Unchanged and non-negotiable: NFA everywhere, no buy/sell language, public data only, no competitor scraping, polite rate limits. The W1 verification gate is a compliance feature as much as a quality one. |

## 8. Doc/repo reconciliation (small, do early)

- Mark V1 `KOEL_MASTER_PLAN.md` superseded by this doc; fix the "Quiverly" naming
  drift in factory docs (product is koel).
- `GREED_METER_MASTER_PLAN.md` says "not started" while `/appetite` is shipped —
  update or archive.
- README still frames Telegram as the *only* v1 surface; the dash is clearly the
  primary cake — update the framing to match CLAUDE.md.
- Update `BOT_DASH_PARITY.md` as W2 alert types land.

## 9. Success metrics

| Metric | Target | Why |
|---|---|---|
| Fire latency (event → Telegram ack), p80 | ≤ 2 poll cycles (+ brief gen for disclosures) | The wedge, quantified — publish it |
| Disclosure brief factual-error incidents | 0 | Trust + SEC exposure |
| Snapshot freshness p95 (market hours) | ≤ poll interval + 10s | Engine honesty |
| Bot onboarding → first watch | ≤ 60s, ≥ 70% of `/start`s | Acquisition surface quality |
| Digest opt-in (new users) | ≥ 40% | Retention hook |
| Weekly retained alert users (4-week) | ≥ 50% | The number that matters most |
| Channel subscribers | growth curve, review monthly | Top of funnel |
| (H3) Paying users / churn | 50+ / <5%/mo | Business viability |

## 10. Risks and pre-planned responses

| Risk | Likelihood | Response |
|---|---|---|
| CSE blocks/rate-limits the endpoints | Medium (session-guarding already observed on some) | Adapter isolation (one-file fix), per-endpoint breakers, polite cadence, W6 honest degradation UX. Long-shot: as koel gains users, an official data-access conversation with CSE becomes possible — the historical snapshot archive is a bargaining chip. |
| Pulse Radar (or Tracker Pro) ships real push | Medium — Tracker Pro adding Telegram is the scarier version | Speed: Horizon 1 is mostly turning on what's built. Moats they can't quickly copy: verified AI briefs, Sinhala, snapshot history, results-day metrics, broker-agnostic Telegram-native UX. |
| LLM produces a wrong number in a brief | Certain eventually, without the gate | W1 verification gate + fallback-to-title is the design answer; log every verification failure. |
| Telegram loses favor / gets restricted locally | Low | The engine/rules/Postgres core is channel-agnostic; WhatsApp Business API is the documented fallback channel (Tijori's own choice). |
| Market too small to monetize | Real | Costs are near-zero (single VM + pennies of LLM); the product is viable as a compounding asset at hobby cost. H3 tests willingness-to-pay cheaply via PayHere Lite before any fixed spend. |
| Solo-operator trust ceiling (Tracker Pro's weakness too) | Real | Public health SLOs, honest incident comms, visible track record via the public channel — make reliability the brand. |

## 11. Sequencing at a glance

```
Now ──► H1  Cherry supremacy
         W1 AI briefs ON (verification gate)      ⭐ start immediately
         W2 52w / MA-cross / reference-move types
         W3 NL alert creation (parser-only)
         W4 Button-first bot + deep links
         W5 "Why it moved" context on fires
         W6 Provenance + degradation honesty
     ──► H2  Distribution & habit
         W7 Public channel   W8 Digest-by-default offer
         W9 Sinhala          W10 Results-day ownership
         W11 Telegram Login prod   W12 Accountability/backtest lines
     ──► H3  Monetization (P5 unlock)
         W13 Tiers + quotas→paywall   W14 PayHere Lite → Plus; Stars secondary
     ──► H4  Earned expansions (only on demand signals)
         P2 positions → P3 simple P&L → P4 PWA/Mini App → data products
Engine-trust workstream (§6) runs under all horizons, always.
```

Ordering logic: H1 items are mostly *activation* of built capability (briefs, parity,
bot polish) — maximum differentiation per unit work, before any competitor closes
the push gap. H2 is pure compounding (channel, digest, language) on a product that
is by then demonstrably best-in-market. H3 monetizes only after retention proves
value. H4 spends fences only when users pull them open.

## 12. Immediate next actions (first factory waves under this plan)

1. Enable `AI_BRIEFS_ENABLED=1` in a soak environment per the runbook; implement the
   number-verification gate + fallback if not already enforced; measure brief latency.
2. Implement `high_52w`/`low_52w` + `ma_cross` + reference-move rule types
   (engine → bot syntax → dash form → parity doc → tests).
3. Bot `/start` hero + inline-keyboard revamp; deep links `?start=sym_<SYMBOL>`;
   fire-message action buttons.
4. NL alert parser behind a flag (`AI_NL_ALERTS_ENABLED`), confirm-keyboard flow.
5. Feed state machine + provenance stamps + automated degradation broadcast.
6. Stand up the public channel + automate 09:35/14:45 posts from existing digest code.
7. Doc reconciliation (§8).
