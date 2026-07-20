# Reddit-driven opportunity backlog (fence-mapped)

**Status:** Prioritized backlog (2026-07-20)  
**Branch intent:** `cursor/reddit-koel-opportunities-8a86`  
**Intel:** [REDDIT_CSE_COMPETITIVE_INTEL.md](REDDIT_CSE_COMPETITIVE_INTEL.md)  
**Fence:** [KOEL_MASTER_PLAN.md](KOEL_MASTER_PLAN.md) · [DASH_CAKE_CHERRY.md](DASH_CAKE_CHERRY.md) · [CLAUDE.md](../../CLAUDE.md)

Items below answer Reddit/retail pain **only** when they stay inside cake+cherry. Portfolio / tax / tip feeds stay deferred.

---

## P0 — this PR / immediate wave

Ship or harden these now. Each maps to an existing master-plan ID where noted.

### P0-1 — Wedge copy (landing + dash banner)

**Pain:** People do not know koel ≠ Tracker Pro / tip channel.  
**Map:** Marketing copy principles · `DASH_CAKE_CHERRY` one-liner · D10 banner.

**Acceptance**
- [ ] Signed-out `/` leads with Telegram push job + dash as daily surface (not portfolio).
- [ ] Explicit differentiator: Tracker Pro-style browser-open alerts vs koel Telegram (NFA nearby).
- [ ] FAQ or non-goals: no portfolio / tax / tips / heavy screener.
- [ ] Adversarial: remove nav → brand still obvious; no tip language.

### P0-2 — Public market + sector strip

**Pain:** Beginners want a glance at “what’s moving” without a broker login.  
**Map:** D11 Index strip · D12 Sector heat strip · TIJORI browse.

**Acceptance**
- [ ] Public (or session-light) surface shows ASPI / S&P SL20 + sector change strip from **poller-persisted** data only.
- [ ] No cse.lk calls from `web/`; empty state honest if poller cold.
- [ ] Links into symbol/browse discovery — not a multi-filter screener.
- [ ] NFA under price-adjacent strip.

### P0-3 — Beginner primer

**Pain:** CDS / broker / hours / symbol confusion in r/srilanka-style threads.  
**Map:** Marketing W3-ish education · primer route or FAQ block (thin).

**Acceptance**
- [ ] Short primer (one page or FAQ section): CDS account (link out to [cds.lk](https://www.cds.lk/) / CSE app), market hours (SLT), symbol form, how koel alerts work.
- [ ] Zero buy/sell tips; “how to use koel” not “what to buy”.
- [ ] CTA → Telegram bot + dash login only.
- [ ] Mobile-readable; no card wall of stats.

### P0-4 — XD Telegram polish

**Pain:** Dividends / XD dates are high-interest; tip channels shout about them.  
**Map:** Cherry `xd_soon` / `xd_digest` · [API_CONTRACT_V1](API_CONTRACT_V1.md) dividend section · [BROKER_PUBLIC_FEEDS_PLAN](../experiments/BROKER_PUBLIC_FEEDS_PLAN.md) Phase 2.

**Acceptance**
- [ ] Bot help shows `/alert SYMBOL xd DAYS` and `/alert MARKET xd_digest DAYS` with examples.
- [ ] Fire copy: symbol · D_XD · DPS if known · dash/deep link · **NFA**.
- [ ] Dedupe proven: one fire per `(rule, d_xd)` / digest week key (existing tests stay green).
- [ ] No LOLC/ToS scrape; calendar from koel-persisted `dividend_events` only.

### P0-5 — EOD digest job

**Pain:** Quiet hours / “summarize my day” without tip spam.  
**Map:** Master plan **C5** · `users.digest_enabled` already stored ([BOT_DASH_PARITY.md](BOT_DASH_PARITY.md)).

**Acceptance**
- [ ] Scheduled job (Colombo EOD) sends one Telegram digest when `digest_enabled` and there were fires that day (or explicit empty-skip).
- [ ] Quiet hours still suppress intraday sends; digest does not burn retry counters incorrectly.
- [ ] Flag default respects existing prefs; ops can disable globally.
- [ ] Message capped + NFA; lists symbol + rule type + price/context.

### P0-6 — Ardeno Wave B1 / B2

**Pain:** Trust / “is data stale?” — Reddit users distrust opaque apps.  
**Map:** [ARDENO_UI_MASTER_PLAN.md](ARDENO_UI_MASTER_PLAN.md) Wave B · master plan E6 / D5.

| ID | Deliverable | Route |
|---|---|---|
| **B1** | Health circuit tracker dots | `/health` |
| **B2** | Stale poller Alert on overview | `/overview` |

**Acceptance**
- [x] B1: circuit / CSE error budget visible as tracker dots (kit pattern); no Magic Beam required.
- [x] B2: Overview shows stale Alert when poller age exceeds threshold during session expectations.
- [x] Tokens match Quiverly (no purple-glow); logged in `THIRD_PARTY.md` if new pattern.
- [x] Adversarial: not a trading terminal KPI wall.

### P0-7 — Briefs enable runbook pointer

**Pain:** Filings are dense; AI brief is the Tijori cherry but still flag-gated.  
**Map:** [docs/runbooks/TIJORI.md](../runbooks/TIJORI.md) § Briefs-on soak · `AI_BRIEFS_ENABLED=0` default.

**Acceptance**
- [ ] This backlog (and/or HANDOFF) links the controlled soak checklist — do not flip prod blindly.
- [ ] No code path that enables briefs without key + daily cap honesty.
- [ ] Ops can follow: one replica → watch ledger → keep sleep ≥ 0.5s.

---

## P1 — next (fence-legal, after P0 green)

| ID | Item | Master-plan map | Acceptance (summary) |
|---|---|---|---|
| P1-1 | Bot ↔ dash alert parity gaps closed | C1 | Matrix in BOT_DASH_PARITY 100% for shipped types; tests |
| P1-2 | Richer Telegram cards (symbol · trigger · dash link) | C3 | Length caps + NFA; no tip tone |
| P1-3 | Quiet hours / mute polish | C4 | Prefs honored; dash + bot documented |
| P1-4 | Cmd+K symbol search | D4 | Hits `/api/v1/symbols?q=`; keyboard a11y |
| P1-5 | Disclosure timeline densify + brief when ready | D6 | Symbol page only; PDF/brief fail-soft |
| P1-6 | Light Browse filters (sector + % move) | Wave 6 / **P1 screener** | Constitution amend first; still not quant board |
| P1-7 | Signal Board read-path harden (NFA scores) | Master **P1b** | Explainable reasons; never “invest tips” |
| P1-8 | Controlled `AI_BRIEFS_ENABLED=1` soak | TIJORI Phase 2 | Runbook checklist green; rate-cap honesty |

**Still banned in P1:** portfolio quantities, tax, tip feeds, competitor scrape, full TA terminal.

---

## P2 — deferred (explicit)

| ID | Item | Why deferred | Unlock gate |
|---|---|---|---|
| P2-1 | Positions table (qty + avg cost) | Tracker Pro job; Reddit praises it elsewhere | Master **P2** after cake+cherry excellent |
| P2-2 | Simple P&L on positions | Depends on P2-1 | Master **P3** |
| P2-3 | Tax reports | High praise on Tracker Pro; compliance-heavy | After P3; constitution amend |
| P2-4 | Native mobile / PWA shell | App UX pain is real; not the wedge | Master **P4** |
| P2-5 | Payments / Pro tier | Premature | Master **P5** |
| P2-6 | Tip-channel aggregation / social signals | Misconduct risk | **Never** under current fence |
| P2-7 | Scrape csetracker / Ceyport / StockSight | ToS + constitution | **Never** |
| P2-8 | Heavy multi-filter screener / OHLC board | CSEPal/Tracker gravity | Reject unless fence rewrite |
| P2-9 | Phase 3 scenario AI | TIJORI stub (`AI_SCENARIOS_ENABLED=0`) | After briefs soak proven |

---

## Priority rule of thumb

```
Reddit pain → does it help “see the market in the dash”
             or “get pinged on Telegram when a rule fires”?
  yes + fence-legal → P0/P1
  portfolio/tax/tips/scrape → P2 never-or-later
```

Research and backlog text are **not financial advice**.
