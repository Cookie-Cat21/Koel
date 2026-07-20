# Signal Board Factor Catalog (F-001…F-100)

**Status:** Catalog complete (100 IDs). Implemented through `path_v5` (components jsonb).  
**Product:** Research scores + forecasts · NFA · never “invest tips”.  
**Concurrency:** Waves ≤8 preferred / 16 hard — do not spawn 100 agents.

## Rules

| Field | Meaning |
|---|---|
| Hypothesis | What the factor claims |
| Source | CSE path / filings / notices / indexes / DEFER 3rd party |
| Feature | Concrete input to score blend |
| Leakage | As-of rule |
| Kill | Drop if fails |
| Status | DONE / OPEN / DEFER |
| OWNED | Implementer paths |

---

## Bucket 1 — Price path microstructure (F-001…010)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-001 | Multi-horizon path returns predict short-horizon rank | `daily_bars` | ret_5/20/60 | bars ≤ as_of | IC≤0 | **DONE** | `chime/signals/score.py` |
| F-002 | High realized vol is a risk penalty | `daily_bars` | vol_20d | same | no lift | **DONE** | `chime/signals/score.py` |
| F-003 | Log liquidity tilts liquid names | `daily_bars` | liquidity_20d | same | no lift | **DONE** | `chime/signals/score.py` |
| F-004 | Wide H–L range = risk | `daily_bars` | range_20d | same | no lift | **DONE** | `chime/signals/score.py` |
| F-005 | Overnight gap (open vs prior close) | `daily_bars` | gap_1d | need open | OPEN if open sparse | OPEN | `chime/signals/` |
| F-006 | Stale ticks (flat price ≥N days) | `daily_bars` | stale_days | same | OPEN | OPEN | `chime/signals/` |
| F-007 | Upper/lower wick asymmetry | `daily_bars` | wick_skew | need OHLC | OPEN | OPEN | `chime/signals/` |
| F-008 | 52w distance from high/low (within 1y path) | `daily_bars` | dist_hi_lo | same | OPEN | OPEN | `chime/signals/` |
| F-009 | Autocorr of daily returns (momentum persistence) | `daily_bars` | ret_acf1 | same | \|acf\|~0 | OPEN | `chime/signals/` |
| F-010 | Drawdown from 20d peak | `daily_bars` | dd_20d | same | OPEN | OPEN | `chime/signals/` |

## Bucket 2 — Liquidity / turnover (F-011…020)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-011 | Volume spike vs 20d avg | `daily_bars` | vol_spike | same | OPEN | **DONE** | `chime/signals/score.py` |
| F-012 | Volume regime + turnover proxy | `daily_bars` | vol_regime, turnover | same | OPEN | **DONE** | `chime/signals/score.py` |
| F-013 | Amihud illiquidity \|ret\|/volume | `daily_bars` | amihud_20 | same | OPEN | OPEN | `chime/signals/` |
| F-014 | Zero-volume session share | `daily_bars` | zero_vol_share | same | OPEN | OPEN | `chime/signals/` |
| F-015 | Trade-count intensity (if present) | snapshots | trade_count | poller ts | OPEN | OPEN | `chime/signals/` |
| F-016 | Turnover concentration top-5 days | `daily_bars` | turn_hhi | same | OPEN | OPEN | `chime/signals/` |
| F-017 | Volume–return correlation | `daily_bars` | vol_ret_corr | same | OPEN | OPEN | `chime/signals/` |
| F-018 | Liquidity dry-up after spike | `daily_bars` | dryup_flag | same | OPEN | OPEN | `chime/signals/` |
| F-019 | Crossing volume share | snapshots | crossing_vol | poller | OPEN | OPEN | `chime/signals/` |
| F-020 | Bid/ask imbalance (optional) | order book | imb | poller | OPEN | OPEN | `chime/signals/` |

## Bucket 3 — Sector & index RS (F-021…030)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-021 | Symbol − sector-peer median ret | `daily_bars`+sector | rs_gap_20d | same | OPEN | **DONE** | `chime/signals/job.py` |
| F-022 | Session vs ASPI change | indexes | aspi_gap_1d | latest index | OPEN | **DONE** | `chime/signals/` |
| F-023 | Symbol − S&P SL20 | indexes | snp_gap | latest | OPEN | OPEN | `chime/signals/` |
| F-024 | Sector index ret (allSectors) | `sectors` | sector_ret | ingest | OPEN | OPEN | `chime/signals/` |
| F-025 | Within-sector rank of ret_20 | path+sector | sector_rank | same | OPEN | OPEN | `chime/signals/` |
| F-026 | Beta vs ASPI (1y daily) | path+ASPI daily | beta | need ASPI daily | OPEN | OPEN | `chime/signals/` |
| F-027 | Residual return after sector | path | resid_ret | same | OPEN | OPEN | `chime/signals/` |
| F-028 | Sector rotation breadth | sectors board | breadth | ingest | OPEN | OPEN | `chime/signals/` |
| F-029 | Cross-sector dispersion | sectors | disp | ingest | OPEN | OPEN | `chime/signals/` |
| F-030 | Index correlation regime | indexes | corr_regime | daily ASPI | OPEN | OPEN | `chime/signals/` |

## Bucket 4 — Filing surprise (F-031…040)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-031 | EPS YoY | `filing_comparisons` | eps_yoy_pct | published≤as_of | OPEN | **DONE** | `chime/signals/` |
| F-032 | Rev / profit YoY | same | rev/profit_yoy | same | OPEN | **DONE** | `chime/signals/` |
| F-033 | Diluted vs basic EPS gap | `filing_metrics` | eps_gap | same | OPEN | OPEN | `chime/signals/` |
| F-034 | Extract_ok rate | `filing_metrics` | extract_ok | same | OPEN | OPEN | `chime/signals/` |
| F-035 | Days since last financial PDF | disclosures | days_since_fin | same | OPEN | OPEN | `chime/signals/` |
| F-036 | Filing surprise vs path reaction | filings+path | post_filing_ret | after publish | OPEN | OPEN | `chime/signals/` |
| F-037 | Scale mismatch flags | comparisons | scale_flag | same | OPEN | OPEN | `chime/signals/` |
| F-038 | Group vs company entity | metrics | entity | same | OPEN | OPEN | `chime/signals/` |
| F-039 | Brief sentiment (flag-gated AI) | briefs | brief_tone | ready only | OPEN | OPEN | `chime/signals/` |
| F-040 | YoY missing-prior rate | comparisons | miss_prior | same | OPEN | OPEN | `chime/signals/` |

## Bucket 5 — Disclosure intensity (F-041…050)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-041 | Disclosure count 30d | disclosures | disc_30 | published≤as_of | OPEN | **DONE** | `chime/signals/` |
| F-042 | Financial-category share | disclosures | fin_share | same | OPEN | **DONE** | `chime/signals/` |
| F-043 | Corporate-action category share | disclosures | ca_share | same | OPEN | OPEN | `chime/signals/` |
| F-044 | Related-party / director dealing | disclosures | rp_count | same | OPEN | OPEN | `chime/signals/` |
| F-045 | Disclosure title length / urgency lex | disclosures | title_score | same | OPEN | OPEN | `chime/signals/` |
| F-046 | PDF present rate | disclosures | pdf_rate | same | OPEN | OPEN | `chime/signals/` |
| F-047 | Burstiness (max/day in 30d) | disclosures | burst | same | OPEN | OPEN | `chime/signals/` |
| F-048 | Category entropy | disclosures | cat_entropy | same | OPEN | OPEN | `chime/signals/` |
| F-049 | Silence spell (days w/o filing) | disclosures | silence | same | OPEN | OPEN | `chime/signals/` |
| F-050 | Watchlist coverage density | watchlist | watch_n | n/a | OPEN | OPEN | `chime/signals/` |

## Bucket 6 — Notices / corporate actions (F-051…060)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-051 | Notice count 30d | `market_notices` | notice_n | published≤as_of | OPEN | **DONE** | `chime/signals/` |
| F-052 | Notice subtype weights | notices | buy_in/nc/halt | same | OPEN | **DONE** | `chime/signals/` |
| F-053 | Recurring non-compliance | notices | nc_repeat | same | OPEN | OPEN | `chime/signals/` |
| F-054 | Halt duration proxy | notices+path | halt_gap | same | OPEN | OPEN | `chime/signals/` |
| F-055 | Board notice without issuer resolve | notices | unresolved_rate | ops | OPEN | OPEN | `chime/notices_backfill.py` |
| F-056 | Buy-in cluster in sector | notices+sector | sector_board | same | OPEN | OPEN | `chime/signals/` |
| F-057 | Time since last notice | notices | days_since | same | OPEN | OPEN | `chime/signals/` |
| F-058 | Notice→path reaction | notices+path | post_notice_ret | after | OPEN | OPEN | `chime/signals/` |
| F-059 | Market-wide halt flag | notices MARKET | mkt_halt | same | OPEN | OPEN | `chime/signals/` |
| F-060 | Notice title category taxonomy | notices | tax_score | same | OPEN | OPEN | `chime/signals/` |

## Bucket 7 — Calendar (F-061…070)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-061 | Weekday / month-end | as_of date | calendar_term | date only | OPEN | **DONE** | `chime/signals/score.py` |
| F-062 | Long calendar gaps in path | `daily_bars` | gap_penalty | same | OPEN | **DONE** | `chime/signals/score.py` |
| F-063 | Official CSE holiday calendar | public calendar | holiday_flag | file as_of | OPEN | OPEN | `chime/signals/` |
| F-064 | Turn-of-month (−2…+2 sessions) | calendar | tom_flag | same | OPEN | OPEN | `chime/signals/` |
| F-065 | Quarter-end window | calendar | qend | same | OPEN | OPEN | `chime/signals/` |
| F-066 | Pre-holiday session | calendar | pre_hol | same | OPEN | OPEN | `chime/signals/` |
| F-067 | January / April seasonality | calendar | month_dummies | same | OPEN | OPEN | `chime/signals/` |
| F-068 | Session open/close proximity | snapshots | tod_bucket | poller | OPEN | OPEN | `chime/signals/` |
| F-069 | Half-day session detect | path gaps | halfday | same | OPEN | OPEN | `chime/signals/` |
| F-070 | Ramadan / festival windows (opt) | calendar | fest | careful | OPEN | OPEN | `chime/signals/` |

## Bucket 8 — Cross-sectional rank (F-071…080)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-071 | Return-rank stability | path | rank_stab | same | OPEN | **DONE** | `chime/signals/job.py` |
| F-072 | Prior score-rank vs return-rank | `symbol_scores` | score_rank_term | prior as_of | OPEN | **DONE** | `chime/signals/job.py` |
| F-073 | Score autocorr lag-5 | scores | score_acf | prior | OPEN | OPEN | `chime/signals/` |
| F-074 | Rank momentum (Δ percentile) | path | d_pctile | same | OPEN | OPEN | `chime/signals/` |
| F-075 | Breadth of positive ret_20 | path | mkt_breadth | same | OPEN | OPEN | `chime/signals/` |
| F-076 | Cross-sectional vol of scores | scores | score_disp | same | OPEN | OPEN | `chime/signals/` |
| F-077 | Winner/loser persistence | path | persist | same | OPEN | OPEN | `chime/signals/` |
| F-078 | Mean-reversion of extremes | path | rev_ext | same | OPEN | OPEN | `chime/signals/` |
| F-079 | Decile turnover | scores | decile_turn | prior | OPEN | OPEN | `chime/signals/` |
| F-080 | Pairwise rank correlation sectors | path | sector_rho | same | OPEN | OPEN | `chime/signals/` |

## Bucket 9 — Issuer idiosyncrasy (F-081…090)

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-081 | Thin history discount | path | thin_penalty | same | OPEN | **DONE** | `chime/signals/score.py` |
| F-082 | Dual-listing `.N`/`.X` gap | path+stocks | dual_term | same | OPEN | **DONE** | `chime/signals/` |
| F-083 | Preference vs voting spread | path | pref_spread | dual | OPEN | OPEN | `chime/signals/` |
| F-084 | Name change / symbol alias | stocks | alias_flag | ops | OPEN | OPEN | `chime/` |
| F-085 | Microcap mcap bucket | snapshots | mcap_bucket | poller | OPEN | OPEN | `chime/signals/` |
| F-086 | Foreign holding % (if present) | companyInfo | foreign_pct | quote | OPEN | OPEN | `chime/adapters/` |
| F-087 | Par value / lot quirks | companyInfo | par | quote | OPEN | OPEN | `chime/adapters/` |
| F-088 | Board type (Main vs Diri Savi) | companyProfile | board_type | profile | OPEN | OPEN | `chime/sector_backfill.py` |
| F-089 | Issue age (years listed) | companyInfo | age_yrs | quote | OPEN | OPEN | `chime/adapters/` |
| F-090 | Single-name event risk score | notices+disc | event_risk | same | OPEN | OPEN | `chime/signals/` |

## Bucket 10 — External macro (F-091…100) — PLANNED (intake-gated)

Roadmap: [`MACRO_EXPANSION_MASTER_PLAN.md`](../MACRO_EXPANSION_MASTER_PLAN.md).  
Status stays intake-blocked until each row in [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md) is checked off.

| ID | Hypothesis | Source | Feature | Leakage | Kill | Status | OWNED |
|---|---|---|---|---|---|---|---|
| F-091 | USD/LKR move | CBSL FX | fx_ret | as_of | ToS | **PLANNED** | `docs/THIRD_PARTY_DATA.md` |
| F-092 | CBSL policy rate change | official | rate_chg | as_of | ToS | **PLANNED** | same |
| F-093 | Inflation print surprise | DCS CCPI | cpi_surp | as_of | ToS | **PLANNED** | same |
| F-094 | Sovereign CDS / yields | ToS-clean | yld | as_of | ToS | **DEFER** | same |
| F-095 | Oil price (energy sector tilt) | EIA | oil | as_of | ToS | **PLANNED** | same |
| F-096 | Global EM equity factor | research panel | em | as_of | ToS | **PLANNED** | same |
| F-097 | Remittance / tourism proxies | SLTDA | rem | as_of | ToS | **PLANNED** | same |
| F-098 | Rainfall / agri (plantation) | official | rain | as_of | ToS | **DEFER** | same |
| F-099 | Power tariff news | official | tariff | as_of | ToS | **DEFER** | same |
| F-100 | Macro composite regime | Tier B blend | regime | as_of | ToS | **PLANNED** | same |

---

## Implementation summary

| Model | What’s in `symbol_scores.components` |
|---|---|
| `path_v5` (current) | F-001…004,002,011,012,021,022,031,032,041,042,051,052,061,062,071,072,081,082 |

Forecast (`path_v5_fc`): walk-forward hit rate ≈ **0.46** → **opt-in overlay only** ([SIGNAL_WALK_FORWARD.md](../../experiments/SIGNAL_WALK_FORWARD.md)).

## Ops

```bash
python3 -m chime notices-backfill --force
python3 -m chime sector-backfill --force --limit 1000
python3 -m chime path-backfill --force --limit 1000
python3 -m chime score-signals --limit 1000
python3 -m chime eval-signals --limit 50
```
