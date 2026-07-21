# CSE company page vs koel symbol page

**Date:** 2026-07-21  
**Example symbol:** `COMB.N0000` (Commercial Bank of Ceylon PLC)  
**Official URL:** `https://www.cse.lk/company-profile?symbol=COMB.N0000`  
**koel surface:** `/symbols/COMB.N0000`  
**Stills:** `/opt/cursor/artifacts/ui-stills/cse-vs-koel/`

This is a **UI + data inventory**, not a build ticket. Fence stays: thin dash over Postgres, public CSE JSON only, NFA — no Tracker Pro clone, no CDS/MyCSE, no scraping competitor sites.

---

## Side-by-side (first viewport)

| Surface | What you see |
|---|---|
| **CSE** | Logo + name + ISIN · last / close / prev close · turnover, share vol, trade count, day range · market cap + % of market · beta vs ASPI / S&P SL20 · tab strip (Profile, Charts, Financials, Videos, Announcement, Quotes, Articles, AGM/EGM, IR) |
| **koel** | Symbol + truncated name · market session chips · Watch / New alert / Dividends / Ownership / People · data-quality notices · last price + day change · expandable daily chart · prev close / volume / market cap · period returns + tech labels · price compare · filings / disclosures |

koel’s wedge stays **alerts + research overlays**. CSE’s page is the **exchange registry + full quote board**.

---

## Matrix — CSE has · koel has · gap

### Quote / session board

| Field | CSE | koel today | Notes |
|---|---|---|---|
| Last / change % | ✓ | ✓ | |
| Close / previous close | ✓ | ✓ (prev derived or stored) | |
| Day high / low | ✓ | **stored, not shown** | `price_snapshots.high/low` already filled for COMB |
| Open | ✓ (Quotes / session) | **stored, not shown** | `price_snapshots.open` |
| Turnover | ✓ | **stored, not shown** | `price_snapshots.turnover` |
| Trade count | ✓ | **stored, not shown** | `price_snapshots.trade_count` |
| Share volume | ✓ | ✓ | |
| Market cap | ✓ | ✓ | |
| Market cap % of total | ✓ | ✗ | `companyInfoSummery.marketCapPercentage` |
| Beta vs ASPI | ✓ | ✗ | `reqSymbolBetaInfo.triASIBetaValue` |
| Beta vs S&P SL20 | ✓ | ✗ | `reqSymbolBetaInfo.betaValueSPSL` |
| WTD / MTD / YTD / 12m hi–lo & volumes | ✓ (Quotes / summary) | ✗ (koel has **period returns %** instead) | from `companyInfoSummery` `wtd*`/`mtd*`/`ytd*`/`p12*` |
| Intraday chart + day’s trades / order book | ✓ (Quotes tab) | Partial (daily chart; order book elsewhere if seeded) | fence: don’t rebuild CSE trading terminal |

### Identity / listing

| Field | CSE | koel today | Source |
|---|---|---|---|
| Company logo | ✓ | ✗ | `reqLogo.path` |
| ISIN | ✓ | ✗ | `reqSymbolInfo.isin` |
| Shares issued / par value | ✓ | ✗ | `quantityIssued`, `parValue` |
| Issue / quoted date | ✓ | ✗ | `issueDate` / profile `quarterDate` |
| Board type (Main / Diri Savi) | ✓ | ✗ | `reqComSumInfo.boardType` (FACTOR F-088) |
| Founded / FY end | ✓ | ✗ | `established`, `finYearEnd` |
| Sector / GICS label | ✓ | ✓ (sector on stock) | |
| Foreign holdings % | ✓ (often null) | ✗ | F-086 |

### Company profile / people / docs

| Field | CSE | koel today | Notes |
|---|---|---|---|
| Business summary | ✓ | ✗ | `infoCompanyBusinessSummary` |
| Address / phone / fax / email / website | ✓ | ✗ | `reqComSumInfo` |
| Secretaries / auditors | ✓ | ✗ | same |
| Directors + top posts (Chair, MD/CEO) | ✓ | Partial | koel People graph from filings/`companyProfile` extracts — not the live CSE board strip |
| Articles of association PDF | ✓ | ✗ | `reqArticlePDF.filePath` on CSE CDN |
| Annual / quarterly report cards | ✓ (Financials tab) | Partial | koel disclosures + PDF enrich; not the CSE report grid UX |
| AGM/EGM calendar | ✓ | Partial | koel `/events` is watchlist/results oriented, not full CSE AGM tab |
| IR connect / Videos / Articles | ✓ | ✗ | low priority for koel wedge |
| TAGS / awards badge | ✓ | ✗ | skip |

### koel-only (CSE company page does **not** match)

- Telegram-linked Watch / New alert / fire history
- Period returns strip (1W–1Y) + tech labels (SMA/ATR/MACD/BB/52W)
- Filing metrics / AI brief strip (ops-gated)
- Ownership map + People dossier (PDF-graph research)
- Dividend calculator / XD events from parsed disclosures
- Price compare (multi-symbol indexed)
- Data-quality notices (stale / thin history / missing PDFs)
- Chart workbench (ranges, forecast overlay when enabled)

---

## Ranked backlog (fence-legal, public JSON)

Highest leverage for “feels as informative as CSE” without becoming CSE:

1. **Quote stats strip** — surface already-stored day H/L, open, turnover, trade count next to prev/volume/mcap. *UI-only; no new poller.*
2. **Identity row** — ISIN, board type, shares issued, par value, market-cap % (persist from `companyInfoSummery` into `stocks` or a thin `company_quotes`/`issuer_profile` table).
3. **Beta chips** — ASPI + SL20 from `reqSymbolBetaInfo` (same endpoint as quote).
4. **Issuer profile block** — business summary, contact, auditors, secretaries, founded, FY end, website (`companyProfile` / `reqComSumInfo`). Cache politely; not every tick.
5. **Directors / top posts strip** — thin list from `infoCompanyDirector` + `topPosts`, deep-link into koel People when matched.
6. **Range context** — WTD/MTD/YTD/12m hi–lo (research labels, not a second trading board).
7. **Logo** — optional `reqLogo` on symbol header (CDN URL allowlist).
8. **Articles of association / report deep-links** — when CSE paths are stable and allowlisted.
9. **AGM/EGM** — only if mapped cleanly onto koel Events without a second calendar product.

**Do not chase on company page:** CDS onboarding, MyCSE login, broker order entry, scraping HTML, cloning Financials/Videos/IR tabs wholesale, foreign-holdings when CSE returns null.

---

## API mapping (for a future thin slice)

| CSE endpoint | Useful payload | koel today |
|---|---|---|
| `POST /companyInfoSummery` form `symbol=` | `reqSymbolInfo` + `reqSymbolBetaInfo` | Poller uses related quote fields into `price_snapshots`; **does not persist** ISIN/beta/range stats / mcap% |
| `POST /companyProfile` form `symbol=` | `reqComSumInfo`, directors, topPosts, logo, article PDF | Used in people/sector backfill paths; **no first-class issuer profile on dash** |
| `POST /companyChartDataByStock` | daily path | ✓ path / daily bars |
| Announcements APIs | filings | ✓ disclosures |

---

## Verdict

CSE company UI = **registry + rich quote + corporate filings library**.  
koel symbol UI = **watch/alert cockpit + path/tech/filings research**.

Biggest honest gaps vs CSE for the same symbol: **session quote depth already in Postgres but hidden**, then **ISIN / beta / listing identity**, then a **cached issuer profile** (contact + board + auditors). Everything else on CSE’s tab strip is either already covered differently (announcements → disclosures) or outside koel’s wedge (Videos, IR, trading terminal).
