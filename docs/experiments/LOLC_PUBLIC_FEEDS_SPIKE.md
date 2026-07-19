# LOLC / CDS public feeds spike (research-only)

**Ran:** `2026-07-18T03:30:31.815536+00:00` · **as-of:** `2026-07-18`  
**Machine report:** [`lolc_public_feeds_spike_20260718T033035Z.json`](./lolc_public_feeds_spike_20260718T033035Z.json)  
**Script:** `scripts/experiments/lolc_public_feeds_spike.py`

> Not financial advice. No prod ingest. Truncated samples only — do not republish full boards.

**Product decision (2026-07-18):** **Do not ship LOLC StockLens / `dividends_db` into Quiverly.**  
LOLC [Terms](https://www.lolcsecurities.lk/terms-and-conditions.html) Use License is individual/non-business only and forbids commercial use, public presentation, copying, and transfer to another server. See [`THIRD_PARTY_DATA.md`](../THIRD_PARTY_DATA.md) (Tier E).

## What we pulled

| Source | HTTP | Bytes | Notes |
|---|---|---|---|
| stocklens | 200 | 196388 | `https://www.lolcsecurities.lk/api/stock-screener/` |
| dividends | 200 | 233258 | `https://www.lolcsecurities.lk/dividend-calendar/dividends_db.csv` |
| cds_infoline_index | 200 | 149690 | `https://www.cds.lk/services/depository-operations/publications-downloads/cds-monthly-reports/` |

## StockLens

- Rows: **302** · unique tickers: **302** · sectors: **20**
- `last_modified`: `2026-07-17 11:24:13`
- Suffix mix: `{'N0000': 280, 'P0000': 1, 'X0000': 21}`
- Foreign holding coverage: **302** · median **0.97%** · p90 **36.65%**

### High foreign holding (sample)

```json
[
  {
    "symbol": "CTC.N0000",
    "fh_pct": 93.64,
    "name": "CEYLON TOBACCO COMPANY PLC"
  },
  {
    "symbol": "DIAL.N0000",
    "fh_pct": 90.59,
    "name": "DIALOG AXIATA PLC"
  },
  {
    "symbol": "HUNT.N0000",
    "fh_pct": 87.37,
    "name": "HUNTER & COMPANY PLC"
  },
  {
    "symbol": "TAJ.N0000",
    "fh_pct": 86.32,
    "name": "TAL LANKA HOTELS PLC"
  },
  {
    "symbol": "GHLL.N0000",
    "fh_pct": 85.93,
    "name": "GALADARI HOTELS (LANKA) PLC"
  },
  {
    "symbol": "OSEA.N0000",
    "fh_pct": 85.77,
    "name": "OVERSEAS REALTY (CEYLON) PLC"
  },
  {
    "symbol": "BOGA.N0000",
    "fh_pct": 83.15,
    "name": "BOGALA GRAPHITE LANKA PLC"
  },
  {
    "symbol": "ALHP.N0000",
    "fh_pct": 82.37,
    "name": "ANILANA HOTELS AND PROPERTIES PLC"
  }
]
```

### Normalized row shape (adapter sketch)

```json
{
  "symbol": "AAF.N0000",
  "name": "ASIA ASSET FINANCE PLC",
  "sector": "Diversified Financials",
  "price": 57.9,
  "mcap_mn": 7191.0,
  "foreign_holding_pct": 73.14,
  "pe": 9.23,
  "sector_pe": 7.13,
  "pbv": 1.51,
  "sector_pbv": 0.93,
  "dy_pct": 0.98,
  "dps": 0.57,
  "eps_4qt": 6.27,
  "nav": 38.45,
  "roe_pct": 21.74
}
```

## Dividends

- Rows: **2331** · parsed XD: **2331** · symbols: **267**
- XD range: `2015-12-23` → `2026-08-17`
- Upcoming from as-of: **14**
- XD-soon horizon counts (days → events): `{'3': 2, '7': 5, '14': 8, '30': 14}`

### Next XD events

```json
[
  {
    "symbol": "VLL.N0000",
    "d_ann": "2026-07-09",
    "d_xd": "2026-07-20",
    "d_pay": "2026-08-07",
    "dps": 0.2,
    "interim": "First",
    "fy": "FY27"
  },
  {
    "symbol": "VLL.X0000",
    "d_ann": "2026-07-09",
    "d_xd": "2026-07-20",
    "d_pay": "2026-08-07",
    "dps": 0.2,
    "interim": "First",
    "fy": "FY27"
  },
  {
    "symbol": "AAF.N0000",
    "d_ann": "2026-06-30",
    "d_xd": "2026-07-24",
    "d_pay": "2026-08-13",
    "dps": 0.57,
    "interim": "Final",
    "fy": "FY26"
  },
  {
    "symbol": "AAF.P0000",
    "d_ann": "2026-06-30",
    "d_xd": "2026-07-24",
    "d_pay": "2026-08-13",
    "dps": 0.7,
    "interim": "Final",
    "fy": "FY26"
  },
  {
    "symbol": "BUKI.N0000",
    "d_ann": "2026-07-15",
    "d_xd": "2026-07-24",
    "d_pay": "2026-08-13",
    "dps": 5.73,
    "interim": "First",
    "fy": "FY27"
  },
  {
    "symbol": "GLAS.N0000",
    "d_ann": "2026-05-22",
    "d_xd": "2026-07-27",
    "d_pay": "2026-08-14",
    "dps": 2.98,
    "interim": "Final",
    "fy": "FY26"
  },
  {
    "symbol": "ALLI.N0000",
    "d_ann": "2026-06-25",
    "d_xd": "2026-07-27",
    "d_pay": "2026-08-14",
    "dps": 10.0,
    "interim": "Final/Other",
    "fy": "FY26"
  },
  {
    "symbol": "SFCL.N0000",
    "d_ann": "2026-06-15",
    "d_xd": "2026-07-31",
    "d_pay": "2026-08-19",
    "dps": 2.8,
    "interim": "Final",
    "fy": "FY26"
  },
  {
    "symbol": "TKYO.N0000",
    "d_ann": "2026-06-30",
    "d_xd": "2026-08-05",
    "d_pay": "2026-08-24",
    "dps": 2.5,
    "interim": "Final/Other",
    "fy": "FY26"
  },
  {
    "symbol": "TKYO.X0000",
    "d_ann": "2026-06-30",
    "d_xd": "2026-08-05",
    "d_pay": "2026-08-24",
    "dps": 2.5,
    "interim": "Final/Other",
    "fy": "FY26"
  },
  {
    "symbol": "CTEA.N0000",
    "d_ann": "2026-06-19",
    "d_xd": "2026-08-07",
    "d_pay": "2026-08-28",
    "dps": 25.0,
    "interim": "Final/Other",
    "fy": "FY26"
  },
  {
    "symbol": "BRR.N0000",
    "d_ann": "2026-07-14",
    "d_xd": "2026-08-10",
    "d_pay": "2026-07-31",
    "dps": 0.2,
    "interim": "Final/Other",
    "fy": "FY26"
  },
  {
    "symbol": "SOY.N0000",
    "d_ann": "2026-06-26",
    "d_xd": "2026-08-14",
    "d_pay": "2026-09-04",
    "dps": 8.0,
    "interim": "Final/Other",
    "fy": "FY26"
  },
  {
    "symbol": "ASHO.N0000",
    "d_ann": "2026-05-25",
    "d_xd": "2026-08-17",
    "d_pay": "2026-09-07",
    "dps": 30.0,
    "interim": "Final/Other",
    "fy": "FY26"
  }
]
```

## CDS INFOLINE index

- PDF links found: **25**
- Latest: `['http://www.cds.lk/wp-content/uploads/2026/05/CDS-INFOLINE_April-2026.pdf', 'http://www.cds.lk/wp-content/uploads/2026/05/CDS-INFOLINE_March-2026.pdf', 'http://www.cds.lk/wp-content/uploads/2026/05/CDS-INFOLINE_February-2026.pdf', 'http://www.cds.lk/wp-content/uploads/2026/05/CDS-INFOLINE_January-2026.pdf', 'http://www.cds.lk/wp-content/uploads/2026/02/CDS-INFOLINE_December-2025.pdf']`

## Takeaways

```json
{
  "fundamentals_board_usable": true,
  "foreign_holding_fills_f086_gap": true,
  "xd_soon_alerts_near_term": 8,
  "would_need_for_prod": [
    "ToS / redistribution decision for LOLC",
    "Postgres tables + flag-default-0 adapters",
    "Attribution + as-of on dash",
    "CSE prices remain truth (ignore LOLC price for quotes)"
  ]
}
```

## Errors

`[]`
