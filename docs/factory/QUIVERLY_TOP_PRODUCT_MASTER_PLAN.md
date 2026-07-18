# Quiverly — Top Product Master Plan

**Status:** Approved for execution (2026-07-18) — Phase A/B scaffolding in flight on `cursor/phase-a-top-product-cccb`  
**Authority:** [CLAUDE.md](../../CLAUDE.md) · competitive deep-dives · 20-loop GTM research  
**Supersedes sequencing of** [CHIME_MASTER_PLAN.md](CHIME_MASTER_PLAN.md) §G **only where this doc conflicts** (payments before portfolio; Signal Board after paid alerts)

---

## 0. Ambition

**Be the #1 way Sri Lankan CSE users hear the market when they’re away — then become the daily CSE home.**

Not “#1 portfolio tracker” first (Tracker Pro / BullStock / Ceyport already fight there).  
Not “#1 tip shop” (Rovana / InvestNow).  

**#1 at:** user-defined rules → reliable Telegram → thin dash to manage → later optional holdings.

**Then expand:** light portfolio → corp actions → P&L → tax → second market.

---

## 1. Why this path wins

| Lane | Who owns it today | Quiverly move |
|---|---|---|
| Holdings / tax / TA | Tracker, StockSight, BullStock, Ceyport, Lanka | **Later** — after alerts habit + paid |
| BUY/SELL AI | Rovana, InvestNow | **Never** as product |
| Broker alerts + trade | ATrad / CAL / Softlogic | Beat on **portability** + Telegram |
| Official CDS / category push | CSE App | Complement; watch if they add custom rules |
| **Custom rules → off-browser push** | Almost empty (Tracker = browser-only) | **Own now** |
| **Disclosure → push** | Weak / category-only | **Own now** |

Portfolio/tax/research breadth are **not forbidden forever** — they are sequenced so we don’t become a mediocre Tracker clone before we own the gap.

---

## 2. North-star metrics (product, not vanity)

| Metric | Target |
|---|---|
| Time-to-first-armed-rule (TTFAS) | Median &lt; 3 min from `/start` |
| Users with ≥1 real fire in 7 days | Rising weekly |
| Fire delivery success (market hours) | &gt; 99% claimed→sent |
| Mute / block rate | Stable or falling |
| Free → Pro conversion (post paywall) | Track; kill if &lt; 4% of fired users |
| Dash weekly actives among rule-setters | Habit, not tourist |

---

## 3. Phased roadmap

### Phase A — Own the cherry (ship next)

**Goal:** Boringly reliable Telegram CSE alerts. Dash is the control plane.

1. **Activation** — Guided `/start`: symbol (bare ticker / chips) → 3 rule types only (above/below, move %, disclosure) → arm → receipt + NFA  
2. **Reliability UX** — Delivered / retrying / failed; freshness badge; market closed vs stale (keep current honesty)  
3. **Anti-spam** — Quiet hours (SLT); tap-to-mute on fire cards; debounce thin illiquid prints; batch noisy movers  
4. **Disclosure path** — New filing on watched symbol + title + source link; optional NFA brief when flagged  
5. **Auth** — Telegram Login Widget for prod; drop open demo on public URL  
6. **Mobile dash** — Alerts in primary chrome; create sheet with 4 v1 types; prefilled last price; ≥44px actions  
7. **Overview / Browse** — Poller banner; row → Watch / New alert; sector → filter; StatCards click through  
8. **Nav trim** — Research (Appetite/Signals/People/Graph) in secondary menu so alert core stays obvious  

**Exit gate:** Retention among users who got ≥1 fire; support not dominated by “missed/dupe” noise.

**Do not in Phase A:** Portfolio, tax, PayHere (yet), Signal Board hero, WhatsApp, LinkedIn autopost spam.

---

### Phase B — Monetize attention (payments before portfolio)

**Goal:** Paid = more capacity + reliability — never “better tips.”

| Tier | LKR | Includes |
|---|---|---|
| **Free** | 0 | ~5 watches · ~2–3 active rules · standard delivery · short fire history |
| **Pro** | **Rs 490/mo** or **Rs 4,900/yr** | Higher caps · priority queue · quiet hours/digest · 90d history |
| **Brief** (optional) | **Rs 1,490/mo** | Metered AI disclosure briefs |

**Payments path**
1. Manual bank transfer + admin activate (ship fast; Tracker-style)  
2. PayHere recurring when volume justifies gateway fee  

**Walls OK:** capacity, history, convenience.  
**Walls ban:** “upgrade to receive this fire,” tip scores, shame FOMO.

**Pricing page + Settings plan** live. Marketing CTA: Telegram bot primary, dash secondary.

**Exit gate:** Paying cohort exists; unit economics on Telegram + poller positive; Pro churn understood.

---

### Phase C — Density without becoming a tip shop

1. Light Browse filters (sector + % move) — P1  
2. Closing-bell digest (watched facts only)  
3. Corp-action **keyword** alerts (div/rights/AGM) — facts, not tips  
4. History timeline + pagination polish  
5. Optional Apache LWC on symbol (flagged)  
6. **Signal Board** only with guardrails (no hero “Top 10,” no score push, NFA adjacent to scores) — **after** Pro identity is “notify my rules”  

**Still out:** BUY/SELL, heavy TA suite, full quant screener.

---

### Phase D — Tracker-adjacent unlock (earn the right)

Only after Phase B converts and Phase A metrics hold.

| Step | Unlock | Still later |
|---|---|---|
| D1 | Positions: qty + avg cost (manual entry) | Tax, broker sync |
| D2 | Corp-action adjustments on holdings | — |
| D3 | Simple P&L | Options / blotter |
| D4 | Tax summary export | “File my taxes for me” advisor posture |
| D5 | PWA / installable shell | Native trading app |

**Partner-shape meanwhile:** “Use BullStock/StockSight for the ledger; Quiverly for pings” until D1 ships.

---

### Phase E — Distribution & brand (parallel, light)

| Channel | Rule |
|---|---|
| **Telegram** | Product #1 — never starve this for marketing |
| **LinkedIn** | 2–4×/week: product notes, how alerts work, NFA education — human approve first |
| **X** | Optional; lower LK retail density |
| **WhatsApp** | **Gated** — only after Telegram healthy + demand + utility cost model for market-hours bursts |
| **SI/TA locale** | Glossary + `/start` language after EN path is solid; never Google-Translate finance |

**Never autopost:** single-stock cheers, ranked “movers to buy,” Signal Board leaderboards.

**Brand line:** *CSE alerts on Telegram. Dash when you need to manage.*  
Own that search intent before trying to steal “CSE portfolio tracker.”

---

### Phase F — Global (privilege, not default)

1. Abstract `market_id` + market calendar + venue adapters (start now in schema thinking)  
2. Hard gate: SL Pro retention + fire reliability boring  
3. Spike **one** next market (PSX or DSE) for data rights — not India/US first  
4. Local currency pricing; same product DNA  

---

## 4. Competitive defense

| Threat | Response |
|---|---|
| Tracker ships real web-push / Telegram | Stay ahead on disclosure rules + bot UX + reliability audit |
| Ceyport finishes email/SMS/Telegram alerts | Win on speed-to-arm + Telegram-native + NFA trust |
| ATrad SMS for broker clients | Stay broker-agnostic; multi-broker users are ours |
| CSE App adds custom thresholds | Differentiate disclosure intelligence + cross-broker + dash audit |
| Rovana owns “CSE AI” mindshare | Never compete on tips; be the anti-tip notify layer |

---

## 5. Explicit never (even at “top”)

- BUY/SELL/HOLD productization  
- Scrape competitors  
- Fake WebSocket “realtime” over poller data  
- React Bits / DaisyUI plugin / Cult Pro / AGPL forks  
- Shame “missed move” push pings  
- Portfolio/tax **before** Phase B payments + Phase A reliability  

---

## 6. Build order (next 90 days if approved)

```
Week 1–2   Phase A activation + anti-spam + reliability UX
Week 3–4   Phase A mobile dash + overview/browse CTAs + Telegram Login
Week 5–6   Phase B bank-transfer Pro + quotas + pricing page
Week 7–8   Phase B PayHere spike + digest + disclosure brief polish
Week 9–12  Phase C light density; decide Signal Board go/no-go
```

Portfolio (Phase D) only if Phase B green.

---

## 7. How this relates to older docs

| Doc | Role |
|---|---|
| `CLAUDE.md` | Product fence — amend when Phase D unlocks |
| `CHIME_MASTER_PLAN.md` | Cake/cherry max UI waves still useful; **payments before P2 portfolio** per this plan |
| `TIJORI_CSE_PLAN.md` | Disclosure → brief → push remains the filing bet |
| `ARDENO_UI_MASTER_PLAN.md` | UI patterns for Phase A dash polish |
| `MARKETING_SITE_MASTER_PLAN.md` | Public site; bot-primary CTAs |

---

## 8. Approval checklist

Approve or amend:

1. [ ] Alerts-first → pay → portfolio (not portfolio-first)  
2. [ ] Pro at **Rs 490/mo / Rs 4,900/yr** (not Rs 299 Tracker-twin)  
3. [ ] Bank transfer then PayHere  
4. [ ] WhatsApp gated; LinkedIn light + approved  
5. [ ] Signal Board after paid alerts only  
6. [ ] Phase A list is the next engineering queue  

**No implementation of Phase A+ until this checklist is signed off.**
