# External CSE API doc vs Quiverly probe

**Compared:** [GH0STH4CKER/Colombo-Stock-Exchange-CSE-API-Documentation](https://github.com/GH0STH4CKER/Colombo-Stock-Exchange-CSE-API-Documentation) (community README + URL list)  
**Against:** Quiverly `docs/endpoint_probe_report.md` + live re-probe 2026-07-12  
**Rule:** Public cse.lk JSON only; do not scrape competitors.

## Verdict

**We cannot reverse-engineer “from that repo” much better than we already have — Quiverly’s probe is already deeper.**  
The GH0STH4CKER list is a useful **checklist of endpoint names**, but it lacks request shapes, failure modes, and several endpoints we already use. Live re-probe did surface **one high-value Quiverly gap** (`marketStatus`) and a **correction** to our `chartData` note.

| Area | GH0STH4CKER | Quiverly today | Action |
|---|---|---|---|
| Per-symbol quote | `companyInfoSummery` (form `symbol`) | Wired in bot | Keep |
| Bulk prices | `tradeSummary` | Poller primary | Keep — still best |
| Per-symbol disclosures | **Not listed** | `getAnnouncementByCompany` wired | Keep (our edge) |
| Market-wide disclosures | `approvedAnnouncement` + category feeds | Adapter has approved; poller uses per-symbol | Optional bulk path (WS-003) |
| Intraday stock chart | Lists `chartData` + `companyChartDataByStock` | Prefer `companyChartDataByStock` | Keep preference |
| Market open/close | Lists `marketStatus` | **Not used** — hardcoded 09:30–14:30 | **Adopt** |
| Leaderboards | `topGainers` / `topLooses` / `mostActiveTrades` | Unused | Skip (screener-adjacent) |
| `todaySharePrice` | Listed as “today’s share price” | Unused | Skip as poller source (top‑N only) |
| `daysTrade` | **Not listed** | Probed, sample saved | Keep as tape option |

---

## What GH0STH4CKER gets right

- Base `https://www.cse.lk/api/` and POST-heavy convention.
- Same core names we use: `companyInfoSummery`, `tradeSummary`, `approvedAnnouncement`, indices, sectors.
- Example for `companyInfoSummery` uses **form data** (correct — JSON body → 400).

## What it misses (Quiverly already ahead)

- **`getAnnouncementByCompany`** — best watchlist disclosure source (form `symbol` + optional dates).
- **`daysTrade`**, legacy **`announcements`**, **`notifications`**, category GETs.
- Content-type / 400 vs 405 failure matrix.
- Field maps into internal `PriceSnapshot` / `Disclosure`.
- Caveats: `approvedAnnouncement.symbol` often null; `chartData` vs `companyChartDataByStock` id spaces.

## Live re-probe deltas (2026-07-12)

### 1. `POST /marketStatus` — adopt for poller gating

```json
{"status":"Market Closed"}
```

Works with JSON `{}` or empty form. Quiverly currently uses static `MARKET_OPEN`/`MARKET_CLOSE` env clocks. Wiring this (with clock fallback) would handle early closes / holidays better without guessing.

**Suggested:** `CSEClient.fetch_market_status()` → poller `is_market_open` consults API when circuit closed, else falls back to clock.

### 2. `POST /chartData` — our “always 400” note was incomplete

| Body | Result |
|---|---|
| form `chartId=1&period=1` (± `symbol=…`) | **200** list of `{d,v,pc}` |
| JSON `{"symbol","chartId","period"}` | **400** |
| form without `chartId` | **400** |

**Important:** `symbol` appears **ignored** — JKH / COMB / SAMP returned identical series with values ~21700 (index-scale), not stock LTPs. Per-stock intraday remains **`companyChartDataByStock` (`stockId` + `period`)**. Do not switch the dash sparkline to `chartData`.

### 3. `todaySharePrice` — not a full board

Returns a **short list** (~10 rows), not all symbols. Unusable as a `tradeSummary` replacement (~282 rows in re-probe).

### 4. Leaderboards — live but out of product fence

`topGainers`, `topLooses`, `mostActiveTrades` return top‑10 style boards. Fine for curiosity; **not** alert-spine fuel (screener-shaped).

### 5. `marketSummery` — live aggregate

`{id, tradeVolume, shareVolume, tradeDate, trades}` — optional health/context only.

---

## Can we reverse-engineer better?

**Yes, slightly — by adopting their checklist + our live method, not by copying their README as truth.**

| Improvement | Impact on Quiverly | Priority |
|---|---|---|
| Wire `marketStatus` into poller open/close | Fewer false polls / missed half-sessions | **High** |
| Correct `chartData` docs + sample | Stops future agents trusting “always 400” or using it for symbols | **High** (docs) |
| Keep ignoring leaderboards / `todaySharePrice` as poll sources | Avoids fence creep + bad data | — |
| Optionally poll category announcement feeds | Broader disclosure coverage beyond company filings | Medium / product call |
| Re-probe `getAnnouncementById` with cookies | Deep links; previously 204 | Low |

**Do not** treat GH0STH4CKER as authoritative for request bodies — their `chartData` row implies symbol-scoped charts; live behavior disagrees.

---

## Follow-ups (factory fuel)

| ID | Item |
|---|---|
| CSE-RE-01 | Update `endpoint_probe_report.md` + `sample_responses/chartData.json` + add `marketStatus.json` |
| CSE-RE-02 | Adapter + poller: `marketStatus` with clock fallback + tests |
| CSE-RE-03 | Credit/link external checklist in probe report (attribution, not dependency) |

CSE-RE-02 is a proper CORE cluster toward the 2K–3K band.
