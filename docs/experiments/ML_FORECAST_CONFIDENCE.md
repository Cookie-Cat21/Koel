# Forecast confidence + unified serve

**Shipped:** migration `018_forecast_confidence.sql`, API fields, sparkline badge,  
`python3 -m koel ml-forecast-unified --mode hpe_with_fallback`.

## Modes

| Mode | Behavior |
|---|---|
| `hpe_only` | High-Precision Emitter only (~90% when speaking) |
| `hpe_with_fallback` | HPE first; always-on fill for other names with low/med/high bands |
| `always_on` | Always-on fin stack only |

## Confidence

- `confidence` ∈ [0,1] from \|model score\|  
- `confidence_band`: high / medium / low  
- `gate`: `hpe_p90` or `always_on`  
- Dash shows **Confidence High · 85%** style badge on sparkline

## Always-on 70% status

Force-find with filings/YoY/ASPI/sector/liquid filters **plateaus ~0.599**.  
**Board-wide always-on 70% is not achieved** with current public CSE path + filing features.  
Use **HPE** for high-confidence forecasts; treat always-on as low-confidence research overlay.

Research only — not financial advice.
