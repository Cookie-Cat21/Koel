# Signal Board Factor Catalog (F-001…F-100)

**Status:** Waves 1–5 landed in `path_v5`. Core plan complete.  
**Product:** Research scores + forecasts · NFA · never “invest tips”.

## Status board

| ID | Hypothesis | Status |
|---|---|---|
| F-001…004 | Path returns / vol / range | **DONE** |
| F-011…012 | Volume spike / regime / turnover | **DONE** |
| F-021…022 | Sector-peer RS / ASPI session RS | **DONE** |
| F-031…032 | Filing YoY | **DONE** |
| F-041…042 | Disclosure count / financial share | **DONE** |
| F-051…052 | Notice totals + subtype weights | **DONE** |
| F-061 | Weekday / month-end | **DONE** |
| F-062 | Long calendar gaps in path | **DONE** |
| F-071 | Return-rank stability | **DONE** |
| F-072 | Prior score-rank vs return-rank | **DONE** |
| F-081 | Thin history discount | **DONE** |
| F-082 | Dual-listing `.N`/`.X` path gap | **DONE** |
| F-063…070 | Official holiday calendar file | OPEN (optional) |
| F-073…080 | Multi-lag score autocorr | OPEN (optional) |
| F-083…090 | More issuer quirks | OPEN (optional) |
| F-091…100 | Macro | **DEFER** |

## Forecast lane

Walk-forward hit rate ≈ **0.46** — noise; overlay stays opt-in.  
See [SIGNAL_WALK_FORWARD.md](../../experiments/SIGNAL_WALK_FORWARD.md).

## Ops

```bash
python3 -m chime notices-backfill --force   # whitespace-safe company resolve
python3 -m chime sector-backfill --force --limit 1000
python3 -m chime score-signals --limit 1000
```
