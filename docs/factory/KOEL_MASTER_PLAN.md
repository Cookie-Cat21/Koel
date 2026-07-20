# Quiverly Master Plan — Maximum inside the fence

**Status:** Active — Waves 1–5 implemented on `cursor/wire-koel-brand-assets-0a71` (2026-07-14). Phased P1–P5 still gated.  
**Authority:** [CLAUDE.md](../../CLAUDE.md) · [DASH_CAKE_CHERRY.md](DASH_CAKE_CHERRY.md) · [FINANCE_DASH_INSPIRATION.md](../brand/FINANCE_DASH_INSPIRATION.md) · [COMMIT_FACTORY.md](COMMIT_FACTORY.md)  
**Competitive edge program (vs CSEPal):** [KOEL_EDGE_VS_CSEPal_MASTER_PLAN.md](KOEL_EDGE_VS_CSEPal_MASTER_PLAN.md) — 30-loop agentic catch-up without becoming a screener.  
**Supersedes operating one-liner in** [KOEL_HORIZON.md](KOEL_HORIZON.md) §1 (horizon score targets still apply)

---

## 0. North star

**Quiverly = the CSE dash you open every day + Telegram push when you’re away.**

| Layer | Job |
|---|---|
| **Cake** | Browse, watch, inspect disclosures, manage rules — denser than today’s lists, still not Bloomberg |
| **Cherry** | Real Telegram push on price / move / disclosure / activity / filing metrics — Tracker Pro’s gap |
| **Engine** | Honest CSE data via poller → Postgres; dash never hits cse.lk |

**Maximum ≠ clone CSE Tracker Pro overnight.** Maximum = every fence-legal capability that makes the cake dense and the cherry reliable, then **phased unlocks** of deferred Tracker-Pro features only after cake+cherry are excellent.

---

## 1. Hard constraints (cannot wish away)

| Constraint | Implication |
|---|---|
| No public CSE WebSocket | Near-realtime = poller interval (min 5s) + dash `PriceRefresh` |
| Undocumented cse.lk JSON | Adapter layer only; polite rate limits; log failures |
| `web/` = Postgres only | No second scraper; no Finnhub/TradingView as data spine |
| License fence | MIT/Apache patterns; **no** AGPL fork (OpenStock), React Bits Commons Clause, Pro packs |
| Factory concurrency | ≤8 preferred / 16 hard — catalog waves, don’t spawn 50 scrapers |
| Compliance | NFA on price surfaces; no competitor scrape |

---

## 2. Capability map — “maximum we can do”

### A. Already shipped (keep / harden)

- Poller + rule engine (price, move, disclosure, activity, filing metrics flags)
- Telegram bot CRUD + fire delivery (leases, dead-letter, NFA)
- Dash: Overview, Browse, Watchlist, Alerts, History, Symbol, Health, Scenarios stub
- Brand assets, kit ports, Badge/Select, PriceRefresh, demo auth
- Near-realtime path documented

### B. Cake max — dashboard density (Wave D1–D4)

Do **all** of these; they are fence-legal and high leverage.

| ID | Deliverable | Inspiration | Acceptance |
|---|---|---|---|
| D1 | **ChangeBadge** on overview/market/watchlist | Tremor badge-03 | ↑↓ % chips; tone tokens; regressions |
| D2 | **Market desktop table** + stacked mobile | HyperUI striped | 4 cols; sort stays change_pct default |
| D3 | **Movers bar-list** | Tremor bar-list-01 | Proportional bars; link to symbol |
| D4 | **Cmd+K symbol search** | CryptoTraderPro / OpenStock UX | Hits `/api/v1/symbols?q=`; keyboard a11y |
| D5 | **shadcn Alert + AlertDialog** | ui.shadcn | Stale notices; confirm unwatch/cancel |
| D6 | **Disclosure timeline** on symbol | HyperUI timeline | Time-ordered filings + brief when ready |
| D7 | **Symbol spark header** | Tremor spark-01 layout | Price + change + existing SVG spark |
| D8 | **History page X/Y + denser rows** | HyperUI pagination | Keep GET limit/offset; DeliveryBadge |
| D9 | **Alert create form sections** | Tremor form-layout | Grouped fields; existing Select |
| D10 | **Dismissible cake/cherry banner** | Tremor banner-04 | Once per session; localStorage |
| D11 | **Index strip** (ASPI / S&P SL20) | Zero Sum | From poller-persisted index snaps only |
| D12 | **Sector heat strip** | Zero Sum / market sectors API | Color by change_pct; no heatmap terminal |
| D13 | **Watchlist multi-column desktop** | admin dash tables | Price, %, vol, spark mini optional |
| D14 | **Overview layout densify** | shadcn admin | 2×2 → richer grid; no KPI chart wall |
| D15 | **Global NFA + last-updated chip** | LiveIndicator | Every price surface |

### C. Cherry max — Telegram + rules (Wave C1–C3)

| ID | Deliverable | Acceptance |
|---|---|---|
| C1 | Bot ↔ dash parity matrix (every alert type creatable both places) | Doc + tests |
| C2 | In-dash “test fire” dry-run (no Telegram send) for ops | Session + CSRF; audit log |
| C3 | Richer Telegram message cards (symbol · trigger · link to dash symbol) | NFA kept; length caps |
| C4 | Quiet hours / mute per rule (optional) | Postgres column; bot + dash |
| C5 | Digest mode (EOD summary of fires) | Flag default off |
| C6 | Delivery reliability dashboard slice on `/health` | Retrying / DL counts |

### D. Engine max — data & freshness (Wave E1–E3)

| ID | Deliverable | Acceptance |
|---|---|---|
| E1 | Market-hours poll default **15s** (configurable; floor 5) | Settings + runbook |
| E2 | Persist index series (ASPI/S&P) for Overview strip | Adapter + table or reuse snaps |
| E3 | Disclosure backfill for watchlist symbols | Prefer `getAnnouncementByCompany` |
| E4 | Snapshot retention policy UI note on Health | Ops clarity |
| E5 | Optional **SSE** “last_snapshot_at” channel | Push age chip without full RSC refresh |
| E6 | Circuit + CSE error budget on Health | tracker-03 short strip |

### E. Symbol depth max — still not TA terminal (Wave S1–S2)

| ID | Deliverable | Acceptance |
|---|---|---|
| S1 | Days-trade / chart points via poller → Postgres → LWC **optional** | Apache LWC; feature flag |
| S2 | Company profile fields from `companyInfoSummery` (name, sector, mcap display) | No OHLC board |
| S3 | Related disclosures filter by category | Existing sanitize |
| S4 | “Watch + alert” sticky action bar | Mobile-first |

### F. Auth & multi-user (Wave A1)

| ID | Deliverable | Acceptance |
|---|---|---|
| A1 | Telegram Login Widget (prod) | ADR 001; drop open demo on public URL |
| A2 | Session device list / logout all | Security |
| A3 | Per-user alert quotas | Anti-abuse |

### G. Phased unlock — Tracker-Pro adjacent (only after D+C+E green)

Order matters. Unlock one fence at a time with constitution amend.

| Phase | Unlock | Still banned until later |
|---|---|---|
| **P1** | Light screener (sector + % move filters on Browse) | Full multi-sort quant board |
| **P1b** | **Signal Board** — research scores + reasons + optional forecast overlay (NFA; never “invest tips”); CSE path ≤1y daily | Commercial data spine / buy-sell language |
| **P2** | Positions table (qty + avg cost) **without** tax | Tax reports, broker sync |
| **P3** | Simple P&L on positions | Options, margin, blotter |
| **P4** | Native PWA / mobile shell | App Store trading app |
| **P5** | Payments / Pro tier | — |

Do **not** start P2+ until Overview/Browse/Symbol feel “daily driver” dense and Telegram cherry is boringly reliable.

---

## 3. Explicit never / reject (even at “maximum”)

- Fork AGPL OpenStock into Quiverly  
- Dump Tremor Planner / 21st Financial Dashboard / Cult Pro / React Bits  
- DaisyUI plugin beside shadcn  
- Live order book / OMS / “buy now”  
- Scrape csetracker.lk or any competitor  
- WebSocket pretending to be CSE when data is poller-delayed  
- Investment advice / tip spam  

---

## 4. Execution waves (build order)

```
Wave 0  Docs + fences aligned (this plan, CLAUDE, DASH_IA)          [now]
Wave 1  D1–D5 + D10 + D15     (badges, alert, table, confirm, banner)
Wave 2  D3, D6–D9, D11–D14    (movers bars, timeline, indexes, densify)
Wave 3  C1–C6 + E1–E6         (cherry reliability + freshness)
Wave 4  D4 Cmd+K + S1–S4      (search + symbol depth / optional LWC)
Wave 5  A1–A3                 (real Telegram auth)
Wave 6  P1 light screener     (constitution amend)
Wave 7+ P2–P5                 (portfolio → P&L → PWA → pay) only if wanted
```

**Agentic loop gate (every wave):**

1. `cd web && npm run typecheck && npm run lint`  
2. `pytest tests/test_web_route_regressions.py -q --tb=short` (+ wave-specific)  
3. `make factory-verify` when Python touched  
4. Adversarial: “Does this look like a trading terminal?” → revert if yes  
5. Log new deps/patterns in `THIRD_PARTY.md`

**Concurrency:** ≤8 implementers; disjoint files; one concern per commit.

---

## 5. Success metrics (product, not commit farming)

| Metric | Target |
|---|---|
| Time-to-watch + set alert from Browse | ≤ 30s of user action |
| Price age chip during market hours | ≤ poll interval + refresh interval |
| Telegram fire latency after cross | ≤ 2 poll cycles |
| Overview “empty cake” | Never blank if poller has board data |
| License incidents | 0 (no AGPL/Pro/Clause slips) |
| Factory `repo_score` | Still climb via [KOEL_HORIZON.md](KOEL_HORIZON.md) — quality commits only |

---

## 6. How this relates to older plans

| Doc | Role after this master plan |
|---|---|
| `DASH_CAKE_CHERRY.md` | Product slogan + layer split |
| `FINANCE_DASH_INSPIRATION.md` | Pattern mine + ranked ports |
| `DASH_IA.md` / `DASH_COMPONENT_FILTER.md` | Route + license gates |
| `KOEL_HORIZON.md` | Score band 2K–3K; update §1 one-liner to cake+cherry |
| `COMMIT_FACTORY.md` | Process constitution; unlock denser dash language |
| `PORTFOLIO_PLAN.md` | Multi-repo score — unchanged |

---

## 7. Immediate next action

Waves 1–5 are implemented on the brand/dash branch. Next:

1. Soak near-realtime (15s poll + PriceRefresh + SSE) during a market session  
2. Turn on `DASH_TELEGRAM_LOGIN=1` only with bot domain allowlisted  
3. Optionally amend constitution for **Wave 6 / P1** light screener  
4. Keep adversarial check: denser cake ≠ trading terminal  

Do **not** start P2+ until Overview/Browse/Symbol feel “daily driver” dense and Telegram cherry is boringly reliable.
