# International stock products — deep research → koel opportunities

**Status:** Research synthesis (2026-07-21)  
**Audience:** product decisions for koel’s CSE alert layer  
**Authority:** [CLAUDE.md](../../CLAUDE.md) · [KOEL_MASTER_PLAN_V2.md](KOEL_MASTER_PLAN_V2.md) · [DASH_CAKE_CHERRY.md](DASH_CAKE_CHERRY.md)  
**Local map:** [REDDIT_CSE_COMPETITIVE_INTEL.md](REDDIT_CSE_COMPETITIVE_INTEL.md) · [activity_alerts.md](../activity_alerts.md) · [TIJORI_CSE_PLAN.md](TIJORI_CSE_PLAN.md)

This doc answers: **what do serious international stock apps / alert layers actually ship**, and **which of those patterns koel should copy, adapt, or refuse** — given CSE data limits and the cake+cherry fence.

---

## 0. Verdict (read this first)

International retail stacks cluster into five jobs. koel should **own job 1–2 for CSE**, borrow UX from 3, and **not** chase 4–5 yet:

| Job | Examples | koel posture |
|---|---|---|
| **1. Attention / push** — ping when *my* symbols move or file | Tijori Alerts, Stock Alarm, Aktai, Robinhood alerts | **Primary wedge.** Double down. |
| **2. Filing intelligence** — AI / category filter on exchange PDFs | Tijori, Aktai, MoveAlerts, Groww filing news | **Built / gated.** Turn on + category toggles. |
| **3. Daily habit surface** — watchlist, movers, calendar, digest | Groww events, Yahoo, Kite stock pages | **Thin dash + digest.** Already the cake. |
| **4. Broker / portfolio OS** — holdings, orders, tax, P&L | Kite, Groww, Fidelity, Tracker Pro locally | **Deferred (P2+).** Reference-price alerts cover 80% without positions. |
| **5. TA terminal** — Pine, multi-pane, broker from chart | TradingView, Kite+TV | **Layer B embed only.** No Pine rebuild. |

**Strategic read:** the global winners koel most resembles are **Tijori Alerts + Stock Alarm**, not TradingView and not a full broker. CSE’s gap is still “user-defined rules + filings → real push.” Global tools either skip CSE, delay CSE, or charge for TA the local retail user does not need first.

---

## 1. Product families surveyed

### 1.1 Messaging-first filing / catalyst alerts

| Product | Delivery | What they do well | Transfer to koel |
|---|---|---|---|
| **Tijori Alerts** (Zerodha-backed) | WhatsApp | Category filters on filings (results, board, insider, corp actions, shareholding, ratings, M&A); AI summary + filing link in **20–60s**; portfolio sync *or* manual watchlist; trial capped by companies tracked | **Closest playbook.** koel already has disclosure poll + brief pipeline. Add **category toggles** + publish latency. WhatsApp = fallback if Telegram ever weakens. |
| **Aktai** | WhatsApp / Telegram / Discord / email / push | Impact score 1–10 before send; multi-channel fan-out; free tier with daily cap; channel/topic routing | **Noise control** (impact / quiet hours already partial); optional public channel topics later |
| **MoveAlerts.ai** | Telegram | News + filings + social distilled to watchlist; sentiment tag; earnings heads-up | Social/X is **out** for CSE fence (noise + misconduct risk). Earnings heads-up = **W10 results-day** |
| **Stock Monitor** | Telegram | Aggressive AI filter (~80% news dropped); 15-min scan cadence | Validate “fewer better alerts”; koel should prefer **rules + verified briefs**, not tip-y sentiment |

**Lesson:** speed + category filters + “check the filing” honesty beat eloquence. Tijori’s own disclaimer matches koel’s verification-gate design.

### 1.2 Alert-specialist apps (US / multi-asset)

| Product | Delivery | Alert surface | Transfer to koel |
|---|---|---|---|
| **Stock Alarm / Stock Alarm Pro** | Push, email, SMS, **phone call** | Price, % move, volume spike, gap, RSI, MA / golden-death cross, 52w, earnings reminder; alerts-first UI (no feed competing for attention) | koel already has most **CSE-honest** subsets (price/move/volume/gap/52w/MA). **Do not** chase RSI-fire spam as default. Phone-call = out of scope. |
| **Yahoo Finance** | Push / email | Mostly **price targets**; weak on volume / TA / extended hours | Proof that “portal with weak alerts” loses to specialists — koel must stay alerts-strong |
| **Robinhood** | App push | Holdings/watchlist % move (5%/10%), custom price, **52w high/low (max 1/week)**, investor updates | **Caps + watchlist defaults** pattern already in V2 §6. Investor updates ≈ disclosure digests |
| **Fidelity** | Push / SMS / email | Price, % since close, **EMA 20/50/200 cross**, 52w, plus account/corp-action alerts | koel `ma_cross` (20/50/200) is the Fidelity set. Account alerts = broker job (out) |

### 1.3 Chart / automation giants

| Product | What they own | Transfer to koel |
|---|---|---|
| **TradingView** | Price / indicator / drawing / Pine alerts; popup, email, push, SMS, **webhooks**; CSE often delayed for non-pro | Layer A workbench (shipped) for *seeing*; Layer B embed for power users. koel wins on **CSE poller truth + disclosure + Telegram zero-setup**. Optional later: **inbound webhook → Telegram** for power users who author TV conditions — not a data spine. |
| **Kite + TradingView** | Trade-from-chart, broker-native | Out — koel is broker-agnostic |

### 1.4 Full retail investing OS (India / US)

| Product | Habit features worth noting | Fence ruling |
|---|---|---|
| **Groww** | Auto 5% move on watchlist/holdings; events calendar (XD, results, splits); DMA / 52w / circuit notifies; short news + exchange filings | **Calendar + auto-% on watchlist** are high-value and fence-legal. Circuit / DMA already near koel types. |
| **Zerodha Kite / Console** | Built-in price+volume alerts; Stock Pages (Tijori research); portfolio timeline of filings + moves | Timeline-for-watchlist = natural dash “Activity” feed from Postgres facts koel already stores |
| **Fidelity / Schwab / E*TRADE** | Account + research + basic price alerts; weak after-hours alert depth | Confirms brokers under-serve pure watchers — koel’s job |

### 1.5 What international products do that **does not** map to CSE public data

Refuse or defer honestly:

| Pattern | Why it fails on CSE (today) |
|---|---|
| Options flow / IV / dark-pool | No public options tape |
| True buy vs sell volume attribution | CSE JSON has no aggressor tag (`volup`/`voldown` stay proxies) |
| Full Level-2 / iceberg detection | Public book ≈ aggregates + thin ladder |
| Extended-hours tape alerts | CSE cash session 09:30–14:30 SLT — different problem (poll when open) |
| Broker portfolio sync | Deferred; ToS / custody complexity |
| Social sentiment / tip aggregation | Misconduct risk; opposite of koel trust brand |
| Native “call me at 5am” phone alerts | Ops cost; Telegram is enough locally |

---

## 2. Feature matrix — them vs koel

Legend: ✅ shipped · 🟡 partial / gated · ❌ absent · ⛔ fence / data block

| Capability | Tijori | Stock Alarm | Robinhood | Groww | TradingView | **koel** |
|---|---|---|---|---|---|---|
| User price above/below | ✅ | ✅ | ✅ | 🟡 | ✅ | ✅ |
| Daily % move | 🟡 | ✅ | ✅ (5/10%) | ✅ auto 5% | ✅ | ✅ |
| Volume spike | ✅ | ✅ | ❌ | 🟡 | 🟡 | ✅ |
| Gap open | ❌ | ✅ | ❌ | ❌ | 🟡 | ✅ |
| 52-week high/low | ❌ | ✅ | ✅ + weekly cap | ✅ | ✅ | ✅ |
| MA / EMA cross | ❌ | ✅ | ❌ | ✅ DMA | ✅ | ✅ `ma_cross` |
| RSI / MACD fires | ❌ | ✅ | ❌ | ❌ | ✅ | ⛔ (chart only; no tip-y RSI spam) |
| Drawing / trendline alerts | ❌ | ❌ | ❌ | ❌ | ✅ | ⛔ Layer B |
| Disclosure / filing push | ✅ core | ❌ | 🟡 updates | ✅ news+filings | ❌ | ✅ + 🟡 AI brief |
| Filing **category** filters | ✅ | ❌ | ❌ | 🟡 | ❌ | 🟡 titles; **gap** |
| AI summary of filing | ✅ | ❌ | ❌ | 🟡 | ❌ | 🟡 gated (`AI_BRIEFS`) |
| Earnings / results day push | ✅ category | ✅ reminder | ❌ | ✅ calendar | 🟡 | 🟡 metrics types; **W10** |
| Dividend / XD calendar alerts | ✅ corp action | ❌ | ❌ | ✅ | ❌ | ✅ `xd_soon` / digest |
| Watchlist timeline (filings+moves) | ✅ Tijori | ❌ | 🟡 | 🟡 | ❌ | 🟡 history; **gap** |
| Messaging delivery (WA/TG) | ✅ WA | push/SMS | app | app | app/email | ✅ **Telegram** |
| Quiet hours / digest | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | ✅ |
| Multi-channel fan-out | Aktai-class | ✅ | ❌ | ❌ | webhook | 🟡 TG; WA later |
| Public market channel | ❌ | ❌ | ❌ | ❌ | social | 🟡 scaffolded W7 |
| Sinhala / local language | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ / shipping |
| Portfolio / tax / orders | via Kite | ❌ | ✅ | ✅ | paper/broker | ⛔ deferred |
| Screener / terminal | Tijori research | light | light | medium | heavy | ⛔ thin browse only |

---

## 3. What koel can do — ranked opportunities

Priorities assume [KOEL_MASTER_PLAN_V2.md](KOEL_MASTER_PLAN_V2.md) Horizon 1–2. Items marked **NEW** are not yet named as waves there.

### P0 — Turn on / finish (highest leverage, mostly built)

1. **Verified AI disclosure briefs live** (Tijori core) — `AI_BRIEFS_ENABLED` + verification gate; publish p80 latency.
2. **Filing category preferences** **NEW** — user toggles: results / board / corp action / shareholding / other (map CSE announcement titles + heuristics). Tijori’s #1 UX; koel currently is mostly “any disclosure.”
3. **Results-day ownership (W10)** — EPS/rev YoY types exist; package as one “results filed” experience with brief + link.
4. **Public channel + close digest (W7/W8)** — Groww/Rovana habit without email; Telegram-native.

### P1 — International patterns that fit the fence cleanly

5. **Watchlist auto-% band** (Robinhood/Groww) **NEW** — one toggle: “ping me if any watched symbol moves ≥5% today” without creating N rules by hand. Still deterministic rules under the hood.
6. **Watchlist Activity timeline** (Tijori Timeline / Kite Console) **NEW** — dash + bot: merged feed of fires, disclosures, XD for *my* symbols from Postgres. Cake that sells the cherry.
7. **Events calendar surface** (Groww) **NEW** — thin `/events` or Overview strip: upcoming XD + known results windows from `dividend_events` / announcement heuristics. Not a portfolio product.
8. **Alert accountability (W12)** — “would have fired N times last quarter” + post-fire price path. Stock Alarm trust; koel’s snapshot archive is the moat.
9. **Inbound TradingView webhook → Telegram** **NEW (power-user)** — optional: user pastes koel webhook URL into TV alert; koel fans out to their Telegram. Does **not** make TV the data spine; CSE rules stay poller-truth.

### P2 — Nice, only after P0–P1 prove retention

10. **Impact / priority score on disclosure fires** (Aktai-style) — heuristic first (results > routine AGM notice), LLM second; suppress low-impact under digest.
11. **Multi-channel fan-out** — WhatsApp Business as Telegram fallback (Tijori path); email digest secondary.
12. **Telegram Mini App slice** — watchlist + alert manager when inline keyboards saturate (V2 W11 follow-on).
13. **RSI / BB *alerts*** — only if users explicitly demand; chart overlays already cover “see.” Prefer not to spam.

### Explicit non-goals (international FOMO)

- Portfolio qty / cost / P&L / tax (Tracker Pro / Groww / Fidelity job)
- Heavy multi-filter screener / options / social sentiment
- Vendoring TradingView Charting Library / Pine
- Native iOS/Android app before Mini App / PWA demand
- Scraping competitor sites or tip channels
- Phone-call alert delivery

---

## 4. Design patterns to steal (UX, not features)

| Pattern | Who | koel application |
|---|---|---|
| **Caps per event class** | Robinhood 52w ≤1/week | Already in V2 §6 — keep expanding (one fire per filing id, etc.) |
| **Holdings vs watchlist alert defaults** | Robinhood | Watchlist alerts opt-in density; don’t spam new users |
| **Category chips on filings** | Tijori | Bot `/alertcategories` + dash Settings |
| **Alerts-first empty states** | Stock Alarm | Bot `/start` and Alerts page: create rule in <15s |
| **“Check the filing” disclaimer** | Tijori | Keep on every AI brief |
| **Events calendar as retention** | Groww | XD + results strip on Overview |
| **Webhook as power escape hatch** | TradingView | Optional inbound → Telegram; never required |
| **Local language as moat** | (gap globally) | Sinhala/Tamil alerts — no US/EU app will do this for CSE |

---

## 5. Suggested sequencing (does not replace V2)

```
Ship / soak now (V2 H1 leftovers)
  ├─ AI briefs ON + category filters (Tijori parity)
  ├─ Results-day packaging (W10)
  └─ Channel + digest habit (W7/W8)

Next product slices (international → CSE)
  ├─ Watchlist auto-5% band
  ├─ Activity timeline (dash + bot)
  ├─ Events calendar strip
  └─ Optional TV→koel webhook

Earn later
  ├─ Impact scoring / WA fan-out
  └─ Mini App
```

Engine trust (freshness SLOs, circuit breakers, honest degradation) remains always-on — international alert apps that lie about latency lose users; koel’s unofficial CSE feed makes honesty a feature.

---

## 6. Sources (primary / product pages)

- Tijori Alerts (Zerodha Z-Connect): https://zerodha.com/z-connect/general/tijori-alerts-stock-exchange-filings-on-whatsapp  
- Tijori / Kite stock pages: https://zerodha.com/z-connect/updates/introducing-the-stock-research-platform-powered-by-tijori  
- Robinhood price alerts: https://robinhood.com/us/en/support/articles/price-alerts/  
- Fidelity alert types: https://www.fidelity.com/viewpoints/active-investor/4-ways-to-use-alerts  
- Groww notifications + events: https://groww.in/updates/updates-from-groww-group-more-watchlists-f-and-o-pause-sell-without-tpin-and-lots-more · https://groww.in/stocks/calendar  
- TradingView alerts / webhooks: https://www.tradingview.com/support/solutions/43000595315-how-to-set-up-alerts/ · https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/  
- Stock Alarm feature set: https://stockalarm.io/ · https://pro.stockalarm.io/stock-price-alerts  
- Aktai (TG/WA multi-channel): https://www.aktai.app/telegram · https://www.aktai.app/in  
- MoveAlerts: https://www.movealerts.ai/  
- Local CSE competitive context: [REDDIT_CSE_COMPETITIVE_INTEL.md](REDDIT_CSE_COMPETITIVE_INTEL.md) · [KOEL_MASTER_PLAN_V2.md](KOEL_MASTER_PLAN_V2.md) §1

---

## 7. Implementation status (2026-07-21)

Shipped on branch (see [passes/HABIT_FEATURES_SHIP_2026-07-21.md](passes/HABIT_FEATURES_SHIP_2026-07-21.md)):

- Filing category prefs + results-day trigger packaging  
- Watchlist auto-5% · Activity timeline · Events calendar  
- Channel preview + digest settings · TV webhook → Telegram (`dry_run=1` for tests)  
- AI briefs remain ops-gated (`AI_BRIEFS_ENABLE.md`); local-fill path exists  

Verify loop: `scripts/habit_features_loop.py` → 50/50.

## 8. One-line product north star (unchanged, internationally validated)

> When something you care about happens on the CSE, koel tells you first, tells you why, and is never wrong about the facts — on Telegram, without another app install.

That sentence is exactly what Tijori proved for India filings and what Stock Alarm proved for US price vigilance. koel’s job is to be **that layer for Colombo**, with a thin dash as the daily surface — not to become Kite, Fidelity, or TradingView.
