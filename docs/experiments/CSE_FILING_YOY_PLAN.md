# Plan: Filing metrics + YoY compare + calc alerts

Status: **implemented behind feature flags (default OFF)**  
Research foundation: board EPS stress Perfect + extract promote.

## Flags (`.env`)

| Flag | Default | Role |
|---|---|---|
| `FINANCIAL_METRICS_ENABLED` | `0` | PDF → `filing_metrics` |
| `FILING_COMPARE_ENABLED` | `0` | Prior-year pairing → `filing_comparisons` |
| `EPS_CALC_ALERTS_ENABLED` | `0` | Absolute EPS Telegram fires |
| `YOY_COMPARE_ALERTS_ENABLED` | `0` | YoY % Telegram fires |
| `METRICS_SHADOW_MODE` | `1` | Claim `[shadow]` alert_log without send when alerts off |
| `YOY_APPEND_TO_DISCLOSURE` | `0` | (ready) append helper `format_yoy_comparison_block` |

## Bot

```text
/alert SYMBOL eps above|below X
/alert SYMBOL eps yoy above|below PCT
/alert SYMBOL rev yoy above|below PCT
/alert SYMBOL profit yoy above|below PCT
```

YoY `below PCT` means `delta_pct < -PCT`.

## Pipeline

```text
disclosure insert → pdf_url enrich → metrics worker
  → filing_metrics → resolve_prior → filing_comparisons
  → evaluate_filing_metrics_rules → claim (+ deliver or shadow)
```

## Schema

Migration `011_filing_metrics.sql`: `filing_metrics`, `filing_comparisons`, new alert types.

## Fail closed

- Non-financial titles skipped
- `extract_ok=false` → no calc/YoY fire
- USD / indicative dollar pages → not LKR truth
- Missing prior → no YoY fire
- Zero prior base → undefined % → no YoY fire

## Go / no-go before flipping flags

1. Human gold ≥50 (still open)
2. Shadow week clean
3. YoY pairing harness ≥95% on local cache when PDFs present
4. Spot-check shadow would-fires vs PDF
