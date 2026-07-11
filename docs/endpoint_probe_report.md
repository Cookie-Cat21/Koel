# CSE.lk API endpoint probe report

Probed: 2026-07-11 against `https://www.cse.lk/api/`  
Test symbol: `JKH.N0000` (John Keells Holdings PLC)  
Source: live HTTP probes + strings from the current Next.js frontend (`/_next/static/chunks/`).

**Convention:** Most endpoints are **POST-only** (GET → 405). Prefer `Content-Type: application/x-www-form-urlencoded` for symbol-scoped calls; empty JSON `{}` works for many market-wide POSTs. Browser-like `User-Agent`, `Origin: https://www.cse.lk`, and `Referer: https://www.cse.lk/` are recommended.

CDN for logos/PDFs: `https://cdn.cse.lk/` (CMT docs often under `https://cdn.cse.lk/cmt/`).

---

## Working endpoints (known list + discoveries)

### `POST /api/companyInfoSummery` — **works** (primary per-symbol quote)

| | |
|---|---|
| Status | `200` |
| Content-Type | `application/json` |
| Method that works | POST form-urlencoded |
| Body | `symbol=JKH.N0000` |

Fails: GET → 405; POST JSON `{"symbol":"..."}` → 400.

Key fields under `reqSymbolInfo`:

- `symbol`, `name`, `id` (numeric stock/company id — use for chart endpoints)
- `lastTradedPrice`, `previousClose`, `closingPrice`
- `change`, `changePercentage`
- `hiTrade`, `lowTrade`
- `tdyShareVolume`, `tdyTradeVolume`, `tdyTurnover`
- `marketCap`, `isin`

Also returns `reqSymbolBetaInfo.securityId` (different id space — do **not** confuse with `reqSymbolInfo.id`).

Sample: [`sample_responses/companyInfoSummery.json`](sample_responses/companyInfoSummery.json)

---

### `POST /api/tradeSummary` — **works** (best bulk price poll)

| | |
|---|---|
| Status | `200` |
| Body | `{}` (JSON) or empty form |

Returns `{ "reqTradeSummery": [ ... one row per symbol ... ] }` with `symbol`, `price`, `previousClose`, `change`, `percentageChange`, `high`, `low`, `open`, `sharevolume`, `tradevolume`, `turnover`, `lastTradedTime`, `marketCap`.

Recommended for Chime poller: one call → filter to watchlist symbols.

Sample: [`sample_responses/tradeSummary.json`](sample_responses/tradeSummary.json)

---

### `POST /api/dailyMarketSummery` — **works**

| | |
|---|---|
| Status | `200` |
| Body | `{}` or empty form |

Nested array of end-of-day market aggregates (`tradeDate` epoch ms, turnover, trades, market cap, etc.). GET → 405.

Sample: [`sample_responses/dailyMarketSummery.json`](sample_responses/dailyMarketSummery.json)

---

### `POST /api/allSectors` — **works**

| | |
|---|---|
| Status | `200` |
| Body | `{}` or empty form |

Array of sector index rows: `symbol`, `name`, `indexValue`, `change`, `percentage`, `sectorVolumeToday`, `sectorTurnoverToday`, `transactionTime`. GET → 405.

Sample: [`sample_responses/allSectors.json`](sample_responses/allSectors.json)

---

### `POST /api/snpData` — **works** (S&P Sri Lanka 20)

| | |
|---|---|
| Status | `200` |
| Body | `{}` or empty form |

Object: `value`, `lowValue`, `highValue`, `change`, `percentage`, `timestamp`. GET → 405.

Sample: [`sample_responses/snpData.json`](sample_responses/snpData.json)

Related bonus: `POST /api/aspiData` — same shape for ASPI. Sample: [`sample_responses/aspiData.json`](sample_responses/aspiData.json)

---

### `POST /api/detailedTrades` — **works** (market-wide, not symbol-filtered)

| | |
|---|---|
| Status | `200` |
| Body | empty form (optional; `symbol=` does not filter in practice) |

Returns `{ "reqDetailTrades": [ { symbol, name, price, qty, trades, change, changePercentage, logoUrl }, ... ] }`. GET → 405.

Sample: [`sample_responses/detailedTrades.json`](sample_responses/detailedTrades.json)

---

### `POST /api/chartData` — **fails**

| | |
|---|---|
| Status | `400` (empty body) for all probed JSON/form payloads |
| GET | `405` |

Frontend still references `chartData`, but live probes never returned 200. Use alternatives below.

Sample note: [`sample_responses/chartData.json`](sample_responses/chartData.json)

**Working alternatives:**

| Endpoint | Body | Notes |
|---|---|---|
| `POST /api/companyChartDataByStock` | `stockId=297&period=1` | `stockId` = `companyInfoSummery.reqSymbolInfo.id` (**not** `securityId`). Returns intraday `{chartData:[{p,c,pc,h,l,q,t,...}]}`. |
| `POST /api/daysTrade` | `symbol=JKH.N0000` | Day trade tape for one symbol. |
| `POST /api/charts` | various | Referenced by frontend with `fromDate=1y&toDate=1d&period=daily` — **also 400** in this probe (may need cookies/session). |

Samples: [`companyChartDataByStock.json`](sample_responses/companyChartDataByStock.json), [`daysTrade.json`](sample_responses/daysTrade.json)

---

## Announcements / disclosures (found)

### Primary market-wide feed: `POST /api/approvedAnnouncement`

| | |
|---|---|
| Status | `200` |
| Body | `{}` (JSON) or empty/ignored form fields |
| Page | `https://www.cse.lk/announcements` |

Response: `{ "approvedAnnouncements": [ ... ] }`

Useful fields: `announcementId`, `id`, `createdDate` (epoch ms), `dateOfAnnouncement`, `announcementCategory`, `company`, `remarks`, `logoUrl`.

**Caveat:** `symbol` is usually `null` — match watchlist via `company` name (from `reqSymbolInfo.name`) or prefer the per-symbol endpoint below.

Sample: [`sample_responses/announcements.json`](sample_responses/announcements.json)

### Per-symbol (recommended for Chime watchlists): `POST /api/getAnnouncementByCompany`

| | |
|---|---|
| Status | `200` |
| Content-Type | form-urlencoded |
| Body | `symbol=JKH.N0000` |
| Optional dates | `fromDate=2025-01-01&toDate=2026-07-11` (ISO `YYYY-MM-DD` or `YYYY/MM/DD`) |

Response: `{ "reqCompanyAnnouncement": [ ... ] }` — same field shape as approved list, scoped to the company.

Bad date formats (`DD/MM/YYYY`, relative `1y`) → HTTP 500.

Sample: [`sample_responses/getAnnouncementByCompany.json`](sample_responses/getAnnouncementByCompany.json)

### Legacy per-symbol archive: `POST /api/announcements`

| | |
|---|---|
| Status | `200` with `symbol=JKH.N0000` |
| Body | form `symbol=JKH.N0000` |

Response: `{ "infoAnnouncement": [ { announcementId, securityId, title, filePath, manualDate, addedDate, ... } ] }`

Older PDF paths like `uploadAnnounceFiles/...pdf` → `https://cdn.cse.lk/<filePath>` (or `/pdf/` prefix per frontend logic). Prefer `getAnnouncementByCompany` for current structured categories.

Sample: [`sample_responses/announcements_legacy.json`](sample_responses/announcements_legacy.json)

### Related announcement endpoints (also live)

| Endpoint | Method / body | Response key |
|---|---|---|
| `/api/getFinancialAnnouncement` | POST form (empty ok) | `reqFinancialAnnouncemnets` (typo in API) |
| `/api/getNonComplianceAnnouncements` | POST `{}` | `nonComplianceAnnouncements` |
| `/api/getNewListingsRelatedNoticesAnnouncements` | POST `{}` | `newListingRelatedAnnouncements` |
| `/api/getBuyInBoardAnnouncements` | POST `{}` | `buyInBoardAnnouncements` |
| `/api/circularAnnouncement` | POST `{}` | `reqCircularAnnouncement` |
| `/api/directiveAnnouncement` | POST `{}` | `reqDirectiveAnnouncement` |
| `/api/getCOVIDAnnouncements` | POST `{}` | `covidAnnouncements` |
| `/api/corporateAnnouncementCategory` | GET | category metadata array |
| `/api/smd/categories` | GET | string list of SMD categories |
| `/api/notifications` | GET | market halt / notice banners |
| `/api/getAnnouncementById` | POST form `announcementId=` | **204 No Content** in this probe |

---

## Failed / not useful paths tried

| Path | Result |
|---|---|
| `/api/announcementList`, `getAnnouncements`, `marketAnnouncements`, `companyAnnouncements`, `disclosures`, … | mostly **404** |
| GET on POST-only endpoints | **405** |
| POST JSON for `companyInfoSummery` / `chartData` | **400** |
| `POST /api/charts`, `POST /api/chartData` | **400** |
| `GET /api/notifications/corporate` (and `/financial`, `/directors`) | **404** (referenced in older JS service wrappers) |

Old Angular HTML paths (`/pages/market-announcements/...`) 404; site is Next.js. Announcements UI: `/announcements`.

---

## Exact request formats (copy-paste)

```bash
# Per-symbol quote
curl -X POST 'https://www.cse.lk/api/companyInfoSummery' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Origin: https://www.cse.lk' -H 'Referer: https://www.cse.lk/' \
  -d 'symbol=JKH.N0000'

# Bulk board (poller-friendly)
curl -X POST 'https://www.cse.lk/api/tradeSummary' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://www.cse.lk' -H 'Referer: https://www.cse.lk/' \
  -d '{}'

# Market-wide disclosures
curl -X POST 'https://www.cse.lk/api/approvedAnnouncement' \
  -H 'Content-Type: application/json' \
  -d '{}'

# Per-symbol disclosures
curl -X POST 'https://www.cse.lk/api/getAnnouncementByCompany' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'symbol=JKH.N0000&fromDate=2025-01-01&toDate=2026-07-11'
```

---

## Recommended Chime `PriceSnapshot` fields

Map primarily from `tradeSummary.reqTradeSummery[]` (bulk) or `companyInfoSummery.reqSymbolInfo` (per symbol):

| Internal field | Source (`tradeSummary`) | Alt (`companyInfoSummery.reqSymbolInfo`) |
|---|---|---|
| `symbol` | `symbol` | `symbol` |
| `price` | `price` | `lastTradedPrice` |
| `previous_close` | `previousClose` | `previousClose` |
| `change` | `change` | `change` |
| `change_pct` | `percentageChange` | `changePercentage` |
| `volume` | `sharevolume` | `tdyShareVolume` |
| `trade_count` | `tradevolume` | `tdyTradeVolume` |
| `turnover` | `turnover` | `tdyTurnover` |
| `high` | `high` | `hiTrade` |
| `low` | `low` | `lowTrade` |
| `open` | `open` | — |
| `market_cap` | `marketCap` | `marketCap` |
| `ts` | `lastTradedTime` (epoch ms) | poller clock / `lastTradedTime` if present |

Store every snapshot; do not discard history.

### Recommended Chime `Disclosure` fields

From `getAnnouncementByCompany` / `approvedAnnouncement`:

| Internal field | Source |
|---|---|
| `external_id` | `announcementId` (stable) |
| `symbol` | request symbol (API often null) |
| `company_name` | `company` |
| `title` | `announcementCategory` (+ `remarks` when present) |
| `category` | `announcementCategory` |
| `published_at` | `createdDate` (epoch ms) or parse `dateOfAnnouncement` |
| `url` | for v1: `https://www.cse.lk/announcements` or company page; legacy `filePath` → `https://cdn.cse.lk/<path>` |
| `seen_at` | poller ingest time |

**Poller strategy suggestion:** `tradeSummary` every N minutes in market hours for prices; `getAnnouncementByCompany` per watched symbol (or `approvedAnnouncement` + name match) for disclosures. Rate-limit politely.

---

## Sample files

All under [`docs/sample_responses/`](sample_responses/) — truncated where large but structure preserved.
