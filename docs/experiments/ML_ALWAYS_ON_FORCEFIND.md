# Always-on force-find ledger

**Baseline (locked):** `baseline_cs_lmt_bag` mean symbol hit = **0.5930**  
**Keep rule:** Δ ≥ **+0.005** under purged protocol.  
**Always-on 70% target:** **not reached** — best keep stacks plateau **~0.599**.

## Cycles

| Lever | Mean symbol hit | Δ vs baseline | Keep? |
|---|---:|---:|:---:|
| baseline_cs_lmt_bag | 0.5930 | — | lock |
| events (disc/notice counts, ~4.9k disc / 1y) | 0.5927 | −0.0003 | **NO** |
| sector_rs (peer-relative ret 5/20) | 0.5938 | +0.0008 | **NO** |
| sector_rs + events | 0.5935 | +0.0005 | **NO** |
| + disc history to 2023 (~14.6k) + interactions | 0.5918 | −0.0012 | **NO** |
| ASPI daily regime (`POST /chartData` period=5, 240 pts) | 0.5938 | +0.0008 | **NO** |
| Financial filing **dates** basic (`POST /financials`) | 0.5973 | +0.0042 | **NO** (near) |
| **Financial filing dates rich** (q90/q365/days/recent) | **0.5987** | **+0.0057** | **YES** |
| fin_rich + ASPI | 0.5914 | −0.0016 | **NO** |
| fin_rich + sector_rs | 0.5980 | +0.0050 | **YES** (marginal) |
| PDF extract YoY only (214 comps / 72 syms) | 0.5934 | +0.0004 | **NO** |
| fin dates + YoY | 0.5972 | +0.0042 | **NO** |
| **fin dates + YoY + sector_rs** | **0.5989** | **+0.0059** | **YES** |
| denser YoY (385 comps / 128 syms) + fin+sector | 0.5979 | +0.0049 | **NO** |
| liquid top-33% + fin_rich | 0.5908 | −0.002 | **NO** |
| YoY-covered universe only | 0.5818 | −0.011 | **NO** |
| abs (no panel) + fin_rich | 0.5580 | −0.035 | **NO** |
| fin_rich + ensemble | 0.5929 | −0.000 | **NO** |

### PDF metrics drain (this wave)

- Seeded **2667** financial disclosures with CDN `pdf_url` via `financials-backfill`
- Processed **900** metrics rows → **576 extract_ok**, **214 YoY comparisons**, **72** symbols with YoY
- Installed runtime `pypdf`/`pdfplumber` (were missing in env)
- CLI: `financials-backfill`, `ml-always-on --yoy`

### Probe note (from cse-api-test endpoints)

- `chartData` → usable **ASPI daily** (~1y) — wired; small lift alone.
- `financials` → **PDF metadata to ~2012**, not numeric line items (`reqFinancial` is labels only). Date/recency features are what moved the needle slightly.
- `getFinancialAnnouncement` → recent market-wide financial PDF feed (good for ops drain next).

**Still needed for bigger lifts:** actual YoY EPS/rev extracted from those PDFs.

## Data ingested this wave

- `disclosures-backfill`: **273** symbols, **~14.6k** rows (2023-01 → 2026-07)
- `stocks.sector` already populated (prior wave)
- `index_snapshots`: only **intraday today** — not usable for walk-forward regime yet
- `market_notices` with symbol: **53** (sparse)

## Interpretation

- Announcement **counts** ≈ no lift.
- ASPI daily regime ≈ noise at current horizon.
- **Financial filing calendar (rich)** was the first **KEEP** (~0.599).
- **YoY from PDFs** helps only when combined (fin+yoy+sector_rs also KEEP ~0.599); YoY alone is too sparse/noisy so far.
- Always-on still **high-50s** — not a breakout. More YoY coverage + cleaner extracts may add a bit more.
- Lean on **HPE (~90% when speaking)** for high precision; keep force-finding always-on.

Also: lean on **HPE (~90% when speaking)** while always-on crawls.

## Commands

```bash
python3 -m koel ml-always-on                 # baseline scoreboard
python3 -m koel ml-always-on --events        # vs baseline
python3 -m koel ml-always-on --sector-rs
python3 -m koel disclosures-backfill --force --limit 0
```

Research only — not financial advice.
