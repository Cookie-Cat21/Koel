# CSE EPS real-world stress test

Generated: `2026-07-13T09:41:09.707729+00:00`  
Research only — full-board style extract + calc-alert gates.

## Universe

- Live board symbols: **282**
- Local PDF symbols: **281**
- Filings indexed: **555**
- Text-ok filings: **531**
- Strong (rev+profit+EPS labels): **347**
- Scanned / text-poor (excluded from extract perfection): **24**
- Remaining downloadable companies without PDFs: **0**
- Board symbols with **no** CSE financial PDFs listed: `JXG.N0000`

## Extract + calc-alert gates (strong set)

| Gate | Result |
|---|---:|
| Strong unique filings | 347 |
| Extractable (text SOPL) | 335 |
| Unextractable quarantined | 12 |
| Coverage on extractable | **100.0%** (335/335) |
| Scored gold EPS accuracy | **100.0%** (n=286) |
| Human-seed EPS accuracy | **100.0%** (n=16) |
| Alert decision accuracy | **100.0%** |
| Crossing accuracy | **100.0%** (n=134) |
| Dual-agree disagreements | 0 |
| Perfect on extractable set? | **YES** |

## Unextractable (OCR / image SOPL / annualized-only / no EPS number)

- `AFSL.N0000` (quarterly) reason=ocr_garble fails=['revenue:missing', 'eps_basic:missing']
- `CABO.N0000` (annual) reason=image_or_empty_sopl fails=['revenue:missing', 'profit:missing', 'eps_basic:missing']
- `CLND.N0000` (quarterly) reason=eps_label_without_number fails=['revenue:missing', 'profit:missing', 'eps_basic:missing']
- `COMD.N0000` (quarterly) reason=eps_label_without_number fails=['eps_basic:missing']
- `CRL.N0000` (quarterly) reason=annualized_eps_only fails=['eps_basic:missing']
- `HUNT.N0000` (annual) reason=image_or_empty_sopl fails=['revenue:missing']
- `RAL.N0000` (annual) reason=image_or_empty_sopl fails=['revenue:missing']
- `SDF.N0000` (quarterly) reason=annualized_eps_only fails=['eps_basic:missing']
- `SOY.N0000` (quarterly) reason=eps_label_without_number fails=['revenue:missing']
- `SUN.N0000` (quarterly) reason=image_or_empty_sopl fails=['revenue:missing']
- `TYRE.N0000` (quarterly) reason=image_or_empty_sopl fails=['revenue:missing']
- `VFIN.N0000` (quarterly) reason=annualized_eps_only fails=['eps_basic:missing']

## Coverage misses (extractable — should be empty when perfect)

- _(none)_

## EPS misses vs scored gold

- _(none)_

## Disagreements (excluded from scored gold)

- _(none)_

Raw: `cse_eps_realworld_stress_20260713T094109Z.json`

