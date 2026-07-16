# Signal Board Factor Catalog (F-001…F-100)

**Status:** Waves 1–4 landed in `path_v4`.  
**Product:** Research scores + forecasts · NFA · never “invest tips”.

## Status board

| ID | Hypothesis | Status |
|---|---|---|
| F-001…004 | Path returns / vol / range | **DONE** |
| F-011…012 | Volume spike / regime / turnover | **DONE** |
| F-021…022 | Sector-peer RS / ASPI session RS | **DONE** |
| F-031…032 | Filing YoY | **DONE** |
| F-041…042 | Disclosure count / financial share | **DONE** |
| F-051 | Notice count 30d | **DONE** (live after `notices-backfill`) |
| F-052 | Notice subtype weights | **DONE** |
| F-061 | Weekday / month-end | **DONE** |
| F-071 | Return-rank stability | **DONE** |
| F-081 | Thin history discount | **DONE** |
| F-082 | Dual-listing `.N`/`.X` path gap | **DONE** |
| F-062…070 | Holiday calendar | OPEN |
| F-072…080 | Score-rank autocorrelation | OPEN |
| F-083…090 | More issuer quirks | OPEN |
| F-091…100 | Macro | **DEFER** |

## Forecast lane

Walk-forward hit rate ≈ **0.46** — noise; overlay stays opt-in.  
See [SIGNAL_WALK_FORWARD.md](../../experiments/SIGNAL_WALK_FORWARD.md).

## Ops

```bash
python3 -m chime notices-backfill --force
python3 -m chime sector-backfill --force --limit 1000
python3 -m chime score-signals --limit 1000
```
