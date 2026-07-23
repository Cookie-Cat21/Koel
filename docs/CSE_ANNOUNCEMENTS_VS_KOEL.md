# CSE announcements page vs koel disclosures

**Date:** 2026-07-23  
**Official board:** [https://www.cse.lk/announcements](https://www.cse.lk/announcements)  
**External API catalog:** [Cookie-Cat21/cse-api-docs](https://github.com/Cookie-Cat21/cse-api-docs) · [hosted docs](https://cookie-cat21.github.io/cse-api-docs/)  
**koel probe notes:** [`endpoint_probe_report.md`](endpoint_probe_report.md) · samples under [`sample_responses/`](sample_responses/)

This is a **coverage inventory**, not a build ticket. Fence stays: thin dash over Postgres, public CSE JSON only, NFA — koel is not a full mirror of the exchange announcements site.

---

## Short answer

**No — koel does not show everything on `/announcements`.**

CSE’s page is the **market-wide corporate disclosure board**. koel stores filings for **symbols someone watches** (plus tickers with active disclosure / share-split rules), then surfaces those rows on company pages, Context, Activity, and Telegram when a disclosure rule fires.

Unwatched issuers never land in Postgres → they never appear in the dash.

---

## Side-by-side

| Surface | What you see |
|---|---|
| **CSE `/announcements`** | Market-wide approved corporate announcements (all issuers CSE publishes on that board), browsable by category / search on the exchange site |
| **koel** | Stored `disclosures` for watched (+ rule) symbols · timeline on `/symbols/{symbol}` · disclosure-first strip on `/context` · watchlist mix on `/activity` · Telegram only with an explicit disclosure (or related) alert |

koel’s wedge stays **watch → store → alert**. CSE’s page is the **full exchange filing board**.

---

## Endpoint map (cse-api-docs → koel)

Catalog source of truth for shapes/samples: [`catalog/endpoints.yaml`](https://github.com/Cookie-Cat21/cse-api-docs/blob/main/catalog/endpoints.yaml) in cse-api-docs. koel’s adapter: `koel/adapters/cse.py`.

### Corporate filings → `disclosures`

| CSE endpoint (POST unless noted) | Role on CSE / docs | koel today |
|---|---|---|
| `/getAnnouncementByCompany` form `symbol=` (+ optional `fromDate`/`toDate`) | Preferred per-company feed | **Primary discovery** for watchlist / disclosure-rule symbols (~1y window in live poll) |
| `/approvedAnnouncement` body `{}` | Market-wide board behind `/announcements` | **Optional bulk** when `DISCLOSURE_BULK_FEED=1` or watchlist size ≥ 3; name→symbol map (`symbol` often null); uncovered names fall back per-symbol |
| `/announcements` (legacy) form `symbol=` | Older PDF archive | **PDF enrich only** (`filePath` → CDN `pdf_url`) — not primary discovery |
| `/getAnnouncementById` / `/getGeneralAnnouncementById` | Detail by id | **Unused** — probes often **204**; dash/Telegram use list fields + `#announcementId` fragment or PDF |

### Related boards — not the main `disclosures` timeline

| CSE endpoint | koel today |
|---|---|
| `/getBuyInBoardAnnouncements` | → `market_notices` (buy-in), not disclosure timeline |
| `/getNonComplianceAnnouncements` | → `market_notices` (non-compliance) |
| Halt / banner notices (`/notifications` and related) | → `market_notices` (halt / notice path) |
| `/getFinancialAnnouncement` | Adapter helper exists; **not wired** into the disclosure poller |
| `/circularAnnouncement` | **Not ingested** |
| `/directiveAnnouncement` | **Not ingested** |
| `/getCOVIDAnnouncements` | **Not ingested** |
| `/getNewListingsRelatedNoticesAnnouncements` | **Not ingested** into `disclosures` |
| `GET /corporateAnnouncementCategory`, `GET /smd/categories` | **Not used** for koel category chips (chips filter stored `disclosure.category` strings) |

---

## Scope rules (what actually gets stored)

| Rule | Behavior |
|---|---|
| Watchlist | Any symbol on **any** user’s watchlist is eligible for disclosure poll |
| Alert rules | Symbols with active `disclosure` / share-split-from-filing rules are included even if not watched |
| Date window (per-symbol) | Live poll uses roughly **today−365 → today** (Asia/Colombo) |
| Bulk feed | Whatever CSE returns on `approvedAnnouncement` that maps cleanly to a known `stocks.name` → symbol |
| Dedup | `UNIQUE (external_id, symbol)` |
| Telegram fire | Only if an active disclosure rule exists **and** `published_at` is after rule create; watching alone does **not** ping |
| Dash list caps | Company page / API default **20**, max **100** — view filter via `?category=` |

---

## Where koel shows stored filings

| Place | What |
|---|---|
| `/symbols/[symbol]` | Disclosure timeline + category chips + chart pins |
| `GET /api/v1/symbols/{symbol}/disclosures` | JSON for that symbol |
| `/context` | Disclosure-first news strip (`queryContextNews`) |
| `/activity` | Watchlist disclosures mixed with fires / XD |
| `/events` | Calendar can include recent results-style filings |
| `/alerts` + history | Disclosure rules and fires |
| Telegram | `/alert SYMBOL disclosure [CATEGORY]` → push with title + CSE/PDF link + NFA |

---

## Honest gaps vs the CSE announcements page

1. **Not market-wide storage** — unwatched names never appear in koel.  
2. **Specialty boards skipped** — circulars, directives, COVID, new-listing notice feeds are not mirrored into `disclosures`.  
3. **Bulk name match can drop rows** — when `approvedAnnouncement.symbol` is null and company name is ambiguous or missing from `stocks`.  
4. **Deep links are best-effort** — `https://www.cse.lk/announcements#{id}`; detail-by-id often empty; PDF when enriched is clearer.  
5. **UI is not a board clone** — no exchange-style full-market announcements browser; research/alert surfaces only.  
6. **Financial PDF market feed** (`getFinancialAnnouncement`) is documented upstream but not on koel’s live disclosure path.

---

## Writing / maintaining this map

| Artifact | Use |
|---|---|
| [cse-api-docs](https://github.com/Cookie-Cat21/cse-api-docs) | Live-probed endpoint catalog, samples, ethics, WebSocket map — **prefer for request shapes** |
| This file | **Product coverage**: what koel stores/shows vs CSE `/announcements` |
| [`endpoint_probe_report.md`](endpoint_probe_report.md) | koel’s historical probe + sample pointers |
| In-app Help → **Disclosures & briefs** | User-facing short version of the same truth |

When CSE adds or renames announcement endpoints, update cse-api-docs (or re-probe), then adjust this matrix and the adapter — do not scrape the HTML announcements page.

---

## Verdict

CSE `/announcements` = **full exchange corporate board**.  
koel = **watchlist-scoped filing store + dash surfaces + optional Telegram disclosure alerts**.

If a filing is not for a watched (or disclosure-ruled) symbol, or only lives on a specialty board koel does not poll, **it will not show up in koel** — verify on cse.lk.
