# Filing metrics + YoY enablement

Pipeline is implemented behind flags (default OFF). Flip only after drains
can backfill priors. Plan: [CSE_FILING_YOY_PLAN.md](../experiments/CSE_FILING_YOY_PLAN.md).

## Prerequisites

1. `python -m koel migrate` (includes `011_filing_metrics` + `014_drain_indexes`).
2. Watchlist symbols have disclosures with `pdf_url` (use `drain-pdfs`).
3. Spot-check ≥20 financial PDFs for `extract_ok`.

## Flip order (staging → prod)

```bash
# 1) Persist only
FINANCIAL_METRICS_ENABLED=1
FILING_COMPARE_ENABLED=1
METRICS_SHADOW_MODE=1
EPS_CALC_ALERTS_ENABLED=0
YOY_COMPARE_ALERTS_ENABLED=0
YOY_APPEND_TO_DISCLOSURE=0

# Backfill
python -m koel drain-pdfs --limit 50
python -m koel drain-metrics --limit 50

# 2) Shadow week — review alert_log rows prefixed [shadow]
# 3) Live calc / YoY one flag at a time
EPS_CALC_ALERTS_ENABLED=1   # optional
YOY_COMPARE_ALERTS_ENABLED=1
# 4) Last
YOY_APPEND_TO_DISCLOSURE=1
```

## Bot

```
/alert SYMBOL eps above|below X
/alert SYMBOL eps|rev|profit yoy above|below PCT
```

Every fire keeps NFA framing. Dash symbol page shows YoY via `FilingMetricsPanel`.

## Stop / rollback

Set all `*_ENABLED=0` (keep `METRICS_SHADOW_MODE=1`). Existing `filing_metrics`
rows remain for research; no Telegram fires.
