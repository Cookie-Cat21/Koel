# Separate project: better unofficial CSE API docs

**Question:** Can we reverse-engineer cse.lk better than [GH0STH4CKER’s docs](https://github.com/GH0STH4CKER/Colombo-Stock-Exchange-CSE-API-Documentation) (~8 months stale; last push 2025-11) and publish our own?

**Answer: Yes — we already are ahead inside Chime, and a dedicated docs repo can beat that README by a wide margin.**  
This is **not** a Chime feature. Chime stays the Telegram alert product; the docs/kit is a **sibling node** (portfolio factory eligible later).

**Authority / ethics:** Public `https://www.cse.lk/api/*` only · polite rate limits · no competitor scrape · no auth-abuse tooling · unofficial + NFA framing.

---

## 1. Why “better” is already true

| Dimension | GH0STH4CKER (2025) | Chime probe + 2026-07-12 live RE |
|---|---|---|
| Form factor | README table + 1 Python snippet + URL list | Full probe report, samples, failure matrix |
| Request shapes | Partial (`companyInfoSummery` form) | POST-only, form vs JSON, 400/405/204 notes |
| Watchlist disclosures | Missing `getAnnouncementByCompany` | Documented + wired in Chime |
| Day tape | Missing `daysTrade` | Sampled |
| Charts | Lists `chartData` as if symbol-scoped | Corrected: form works but **symbol ignored**; use `companyChartDataByStock` |
| Freshness | Last push ~Nov 2025 | Live re-probed Jul 2026 |
| Stars | ~125 (distribution) | Depth without packaging yet |

So: **depth we win; packaging/distribution they win.** A sibling docs site closes that gap.

---

## 2. New surface from official site JS (Jul 2026)

Pulled Next.js chunks from `cse.lk` and live-probed. Beyond GH0STH4CKER’s checklist:

### A. STOMP WebSocket (big gap in his docs)

| | |
|---|---|
| Broker | `https://www.cse.lk/api/ws` (SockJS/STOMP; site uses stomp.js) |
| Subscribe topics | `/topic/aspi`, `/topic/snp`, `/topic/status`, `/topic/summary`, `/topic/today-sharePrice`, `/topic/top-gainers`, `/topic/top-looses`, `/topic/most-active-trades`, `/topic/daytrade` |
| Request apps | `/app/request-aspi`, `…-snp`, `…-status`, `…-summary`, `…-today-sharePrice`, `…-top-gainers`, `…-top-looses`, `…-most-active-trades`, `…-daytrade` |
| Also | `/user/topic/…` mirrors |

**Docs value:** Real-time market board without inventing polling. **Chime note:** still prefer polite HTTP `tradeSummary` for v1 alerts; WS is for the docs kit / optional future.

### B. Rich HTTP endpoints he doesn’t cover (verified live)

| Endpoint | Method | Status | Notes |
|---|---|---|---|
| `POST /companyProfile` | form `symbol=` | **200** | Directors, business summary, logo, article PDFs, contact — company page gold |
| `GET /news/web` | query `top`, `type`, `year`, … | **200** | Press / market reviews (`CN`, `MR`, `BN`, …) |
| `GET /events`, `GET /events/top` | query `eventType`, `year` | **200** | Calendar / top events |
| `GET /notifications` | — | **200** | Halt/notice banners |
| `GET /corporateAnnouncementCategory` | — | **200** | 53 categories |
| `GET /smd/categories` | — | **200** | 57 SMD categories |
| `POST /marketSummery` | `{}` | **200** | Session aggregates |
| `POST /getGeneralAnnouncementById` | form `announcementId=` | **200** (empty `{}` for bad id) | Detail path used by site |
| `POST /marketStatus` | `{}` | **200** | Open/closed string |

Auth/account endpoints appear in JS (`signInNew`, `verifyOtp`, …) — **document existence only; do not ship login crackers or credential flows** in the public kit.

### C. Still prefer our existing winners

- Bulk prices: `tradeSummary`  
- Per-symbol quote: `companyInfoSummery`  
- Per-symbol disclosures: `getAnnouncementByCompany`  
- Per-stock intraday: `companyChartDataByStock`  

---

## 3. What “release our own API documentation” means

### Product (sibling repo — suggested name)

**Working title:** `cse-api-docs` / `cse-lk-unofficial`  
**Not** inside Chime’s app code. Optional later enrollment as factory **node 2**.

| Deliverable | Description |
|---|---|
| **Docs site** | Static (Next/VitePress/GitHub Pages): endpoint catalog, curl + Python examples |
| **Probe harness** | Script that hits each endpoint, records status/schema fingerprint, fails CI if drift |
| **Sample vault** | Truncated JSON fixtures (like Chime `docs/sample_responses/`) |
| **Field maps** | Tables: response key → meaning → gotchas |
| **WS guide** | STOMP connect, subscribe, request-app, example frames |
| **Ethics page** | Unofficial, rate limits, NFA, no scraping competitors, no auth abuse |
| **Changelog** | Re-probe dates (fixes the “8 months stale” problem) |

### Quality bar vs GH0STH4CKER

Ship only if each endpoint page has:

1. Method + path  
2. Working body / content-type  
3. Example 200 (truncated)  
4. Known failure modes (405/400/204)  
5. Last verified date  
6. “Used by cse.lk UI for …” when known from JS  

That alone is already **strictly better** than a name-only table.

---

## 4. Build order (sibling project)

1. **Scaffold** repo + MIT/docs license + disclaimer.  
2. **Import** Chime’s probe report + samples as v0.1 baseline (attribution: derived from public RE + Chime research).  
3. **Add** pages for: `companyProfile`, `news/web`, `events`, `notifications*`, categories, `marketStatus`, STOMP `/api/ws`.  
4. **Automate** `scripts/probe.py` → refresh samples weekly.  
5. **Publish** GitHub Pages; link from Chime `RESOURCES.md` as external.  
6. **Optional:** tiny Python client package (`pip install cse-lk`?) — thin wrappers only, same ethics.

Chime consumes improvements by copying verified notes back into `endpoint_probe_report.md` / adapter — one-way sync, not a monorepo merge.

---

## 5. What we will not claim

- Official partnership with CSE  
- Stability / SLA  
- Right to hammer or resell raw exchange feeds  
- That WebSocket beats polite HTTP for every use case  
- That shipping auth endpoint details = permission to automate accounts  

---

## 6. Verdict for the operator

| Ask | Answer |
|---|---|
| Can we RE better than him? | **Yes — already deeper; site JS adds WS + companyProfile + news/events.** |
| Is there more stuff? | **Yes** — especially STOMP topics and company profile aggregate. |
| Can we release our own docs? | **Yes, as a separate repo/site**, with probe CI so it doesn’t go stale in 8 months. |
| Does Chime need that repo to work? | **No** — Chime already runs on the subset it needs. Docs are community + portfolio upside. |

**Next unlock:** This kit now lives at [`cse-api-docs/`](../cse-api-docs/) inside the Chime monorepo (agent cannot `gh repo create`). See [`cse-api-docs/EXTRACT.md`](../cse-api-docs/EXTRACT.md) to split into `Cookie-Cat21/cse-api-docs`. Browse generated docs under `cse-api-docs/site/` after `python3 scripts/build_site.py`.
