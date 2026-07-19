# CSE history deep dive — can we get more than ~1y?

**Date:** 2026-07-16  
**Goal:** Find any public (or documented) way to pull **multi-year per-stock OHLC** beyond `companyChartDataByStock period=5`.

## TL;DR

| Source | Multi-year stock OHLC? | Notes |
|---|---|---|
| `companyChartDataByStock` `period=5` | **No — ~1y max** | Official UI labels period `5` = “oneYear” |
| Extra date params on that endpoint | **Ignored** | `fromDate`/`toDate` do not extend series |
| `POST /charts` | **Blocked / broken for us** | SPA calls it with `withCredentials`; unauth → 400 |
| `POST /charts/52week` | **404 unauth** | Same credentials pattern |
| **`POST /historicalTrades`** | **Likely yes — login-gated** | SPA maps Daily→`D` … Yearly→`Y`; dates `DD-MM-YYYY`; returns `reqDaysOhlc` / `reqOhlcHistory` |
| `POST /financials` | PDFs only | Annual/quarterly report files — not daily prices |
| `POST /aspi/year` | Scalars only | YTD % for ASPI/SNP, not a series |
| Index `POST /chartData` | **~1y max** (`period=5`) | Same period enum as equities |
| Alternate path names (`historicalData`, `priceHistory`, …) | **404** | Dead ends |

**Conclusion:** For **unauthenticated** public JSON, **~1 year daily remains the ceiling**. The CSE company-profile UI itself only offers periods up to one year for the free chart helper, and a separate **Historical values** widget calls `historicalTrades` that **requires a logged-in session** (`localStorage` token / roles including `ROLE_PLATINUM`, `ROLE_CLASSIC`, `ROLE_SMS`, `ROLE_FREE`). We do **not** bypass that auth.

---

## 1. Confirmed free chart ceiling

From CSE Next.js chunk (`7e0d0ad7…js`):

```text
period.oneDay → 1
period.oneWeek → 2
period.oneMonth → 3
period.quarterly → 4
period.oneYear → 5
```

Live probe (JKH stockId 297): `period=5` → **242** daily points, **2025-07-16 → 2026-07-15**.  
Adding `fromDate=2015-01-01` etc. still returns the same 242 points.

## 2. New endpoints found in company-profile JS

Chunk `1c4a38cd3ad44210.js` `postFormUrlencoded` targets:

| Endpoint | Auth hint | Result unauthenticated |
|---|---|---|
| `companyChartDataByStock` | none | Works — 1y max |
| `charts` | `withCredentials: true` | **400** |
| `charts/52week` | `withCredentials: true` | **404** `[]` |
| **`historicalTrades`** | `withCredentials: true` | **404** empty with correct form; **400** with wrong form |
| `financials` | none | **200** — PDF metadata (`infoAnnualData`, `infoQuarterlyData`) |
| `daysTrade` | none | Intraday tape |
| `orderBook` | credentials | (existing) |
| `agmEgmCalender` / `corporateCompanyCalender` | — | Event calendars |

### `historicalTrades` contract (from SPA)

```text
POST /api/historicalTrades
form: symbol, fromDate, toDate, period
fromDate/toDate format: DD-MM-YYYY  (e.g. 01-01-2015)
period map: Daily→D, Weekly→W, Monthly→M, Quarterly→Q, Yearly→Y
response: period=="D" ? reqDaysOhlc : reqOhlcHistory
```

UI default date window is **last ~3 months**; role flags gate download UX (`ROLE_PLATINUM` / `CLASSIC` / `SMS` / `FREE`).

**Without a CSE account token we cannot validate multi-year depth.** With a legitimate account this is the prime candidate for longer OHLC.

## 3. Other probes (no multi-year stock path)

- Dead 404s: `historicalData`, `historicalPrices`, `sharePriceHistory`, `priceHistory`, `stockHistory`, `companyChartData`, …
- `aspi/year`: YTD performance **scalars** only  
- WebSocket (`/api/ws`, `/app/request-aspi`, …): live market push, not history dump  
- `financials`: useful for **fundamental PDF history**, not daily prices (Quiverly already extracts some via disclosure pipeline)

## 4. What this means for ML

| Option | Realistic? |
|---|---|
| Pull 5–10y daily OHLC anonymously from cse.lk JSON | **No** (not found) |
| Use `historicalTrades` with **user-provided CSE login** (ToS-compliant) | **Maybe** — needs legal/product OK + auth adapter |
| Keep accumulating via poller / `path-backfill` | **Yes** — grows forward from ~1y base |
| Use `financials` PDFs for longer fundamental panels | **Yes** — already partial |

## 5. Recommended next steps (product)

1. **Document** this deep dive (this file) — done.  
2. **Do not** scrape behind login without explicit user credentials + ToS review.  
3. Optional follow-up (separate plan): design `historicalTrades` adapter gated on `CSE_SESSION_*` secrets, probe max range **once** with a real free/platinum account, measure years returned.  
4. Continue **purged ML / panel ranker** on the 1y corpus we have.

## Probe commands (repro)

```bash
# Free 1y ceiling
curl -sS -X POST 'https://www.cse.lk/api/companyChartDataByStock' \
  -H 'Origin: https://www.cse.lk' -H 'Referer: https://www.cse.lk/' \
  -d 'stockId=297&period=5' | jq '.chartData | length'

# Login-gated OHLC (expects 404 without token)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST 'https://www.cse.lk/api/historicalTrades' \
  -H 'Origin: https://www.cse.lk' \
  -d 'symbol=JKH.N0000&fromDate=01-01-2015&toDate=16-07-2026&period=D'
```
