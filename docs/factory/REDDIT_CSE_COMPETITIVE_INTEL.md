# Reddit / CSE tooling — competitive intel for koel

**Status:** Research synthesis (2026-07-20)  
**Branch intent:** `cursor/reddit-koel-opportunities-8a86`  
**Authority:** [CLAUDE.md](../../CLAUDE.md) · [DASH_CAKE_CHERRY.md](DASH_CAKE_CHERRY.md) · [KOEL_MASTER_PLAN.md](KOEL_MASTER_PLAN.md)  
**Backlog:** [REDDIT_OPPORTUNITY_BACKLOG.md](REDDIT_OPPORTUNITY_BACKLOG.md)

Synthesizes retail CSE discourse themes (esp. [r/srilanka](https://www.reddit.com/r/srilanka/) + adjacent beginner / tooling talk) with public competitor positioning.  
**Method note:** Reddit JSON/HTML was not scrapeable from this environment (403); themes below merge product constitution notes, confirmed competitor public copy, CSE app store feedback, and beginner-guide patterns that mirror what shows up in Sri Lanka retail investing threads. Do not treat this as a scrape of competitor backends.

---

## 1. Themes from Reddit + retail CSE talk

| Theme | What people struggle with | koel implication |
|---|---|---|
| **Beginner confusion** | CDS vs broker vs “app”; how to start; what ASPI/S&P SL20 mean; symbol suffixes (`.N0000`); market hours | Thin **primer** + honest glossary on public/dash surfaces — not a trading course, not tips |
| **Browser-only alerts gap** | Want a ping when price moves / disclosure lands **away from the desk**; hate babysitting a tab | **Telegram cherry** is the wedge — real push when the browser is closed |
| **Portfolio / tax praise elsewhere** | Tracker Pro / StockSight / Ceyport win mindshare on holdings, P&L, tax reports | Acknowledge the job; **do not clone yet** (P2+ unlock only after cake+cherry) |
| **Disclosures / dividends** | Filings are noisy; XD / pay dates matter but are hard to track casually | Disclosure alerts + briefs path + **XD soon / digest** (already in product spine) |
| **Tip-channel risk** | Telegram “guru” groups, pump language, unverified calls | koel = **rules + official CSE data + NFA** — never tip feeds or “best stocks” |
| **App UX pain** | CSE Mobile App: disclosure delays, weak notification controls, search/friction; broker apps feel heavy for “just watch” | Dash = calm daily browse; Telegram = lightweight alert surface |

---

## 2. Competitor map — what koel already solves vs them

| Player | Job they own | Alert / push reality | koel already covers | koel does **not** chase (fence) |
|---|---|---|---|---|
| **CSE Tracker Pro** ([csetracker.lk](https://csetracker.lk/)) | Portfolio, analytics, tax | Site copy: price alerts via **browser notifications — “Browser open ඇති විට only”** | Watch + threshold / move / disclosure rules → **Telegram** without a tab | Portfolio qty / cost / P&L / tax |
| **CSE Mobile App** ([Play](https://play.google.com/store/apps/details?id=com.lk.efutures) · [App Store](https://apps.apple.com/app/cse-mobile-app/id888273823)) | CDS open, market browse, category push (disclosures / market / news) | Category-style push; store reviews cite delay + **no granular notification settings**; not custom per-stock price thresholds | Per-symbol **price / move / disclosure / activity / XD** rules the user sets | CDS onboarding, trading, official education suite |
| **ATrad** ([atrad.lk](https://atrad.lk/) · [Play](https://play.google.com/store/apps/details?id=com.ironone.atrad)) | Broker OMS / live trade / portfolio / charts | Broker-channel alerts (e.g. SMS in app feature lists) — tied to **broker login**, not open watch tooling | Independent watch/alert layer over public CSE JSON | Order entry, blotter, broker sync |
| **Ceyport** ([ceyport.lk](https://ceyport.lk/)) | Market browse, sectors, dividends, portfolio analytics | Portfolio + dividend alerts positioned behind account | Public-ish market/sector/dividend **awareness** via koel dash + XD cherry | Full screener / portfolio product |
| **StockSight** ([stocksight.app](https://stocksight.app/)) | Portfolio journal, dividends, splits, charts | Holdings-first; not koel’s push wedge | Same: watch + filing/price push, not a second portfolio app | Holdings / tax / paid portfolio analytics |
| **Telegram tip channels** (various) | Rumors, calls, screenshots | High engagement, high misconduct risk | Opposite posture: **user-authored rules**, official filings, NFA on every price-adjacent message | Tip aggregation, “hot picks”, social copytrading |

**Precedent (not a CSE competitor):** Zerodha’s [Tijori Alerts](https://tijori.com/) — WhatsApp/Telegram-style filing/alert layer beside a full broker stack. koel’s bet is the same **gap close** for CSE: filings + thresholds → real push, with a denser dash as cake ([TIJORI_CSE_PLAN.md](TIJORI_CSE_PLAN.md)).

---

## 3. Known URLs (cite list)

| URL | Why it matters |
|---|---|
| https://www.reddit.com/r/srilanka/ | Primary community surface for retail CSE / money threads |
| https://csetracker.lk/ | Tracker Pro — portfolio/tax leader; **browser-open-only** price alerts (confirmed on-site) |
| https://ceyport.lk/ | Dense market + dividend analytics competitor |
| https://stocksight.app/ | Portfolio / dividend tracker competitor |
| https://atrad.lk/ · https://atrad.lk/new-to-trading/ | Broker trading stack + CDS-via-CSE-app funnel |
| https://play.google.com/store/apps/details?id=com.ironone.atrad | ATrad mobile surface |
| https://play.google.com/store/apps/details?id=com.lk.efutures | Official CSE app — category push + UX complaints |
| https://apps.apple.com/app/cse-mobile-app/id888273823 | Official CSE app (iOS) |
| https://www.cse.lk/ | Public market + undocumented JSON used by koel poller only |
| https://www.cds.lk/ | CDS account truth (beginner primer should link out, not re-host) |
| https://tijori.com/ | Analog: filing/alert push beside a fuller investing stack |

---

## 4. Explicit fence (do not violate)

Copied from constitution — loops that violate these are **auto-fail**:

1. **No portfolio / tax / broker sync** until explicit P2+ unlock in [KOEL_MASTER_PLAN.md](KOEL_MASTER_PLAN.md).  
2. **No tip channels**, buy/sell language, or “best to invest” framing — research scores stay NFA.  
3. **No competitor scrape** (`csetracker.lk`, Ceyport, StockSight, ATrad private APIs, tip groups). Public **cse.lk** JSON only, via poller adapter.  
4. `web/` reads **Postgres / koel API only** — never cse.lk from the dash.  
5. Every price-adjacent surface keeps **not financial advice** framing (SEC Sri Lanka Part V market-misconduct posture).  
6. Denser cake ≠ Tracker Pro overnight; adversarial check: “trading terminal?” → revert if yes.

---

## 5. Product read — where koel wins now

| Layer | Win condition vs Reddit pain |
|---|---|
| **Cake** | Browse / watch / symbol / disclosures without becoming a portfolio terminal |
| **Cherry** | Telegram fire when tab is closed — Tracker Pro’s documented gap |
| **Trust** | Official filings + optional AI briefs (flag-gated) + fire history; not tip spam |
| **Honesty** | Poller age / health; no fake WebSocket tape |

Next actions mapped to fence-legal work: [REDDIT_OPPORTUNITY_BACKLOG.md](REDDIT_OPPORTUNITY_BACKLOG.md).
