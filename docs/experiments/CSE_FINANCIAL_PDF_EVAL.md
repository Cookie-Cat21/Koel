# CSE financial PDF extraction spike

Generated: `2026-07-13T04:54:32Z`  
Sample: **100** PDFs from `POST /api/financials` (50 quarterly + 50 annual across ~25 issuers), parsed with **pypdf** + **pdfplumber**.  
Harness: `scripts/experiments/cse_financial_pdf_eval.py`

## Headline

| Metric | Count | % |
|---|---:|---:|
| Downloaded OK | 89 | 89.0 |
| Extractable text (≥400 chars) | 87 | 87.0 |
| Scanned / empty-like | 2 | 2.0 |
| Calc-ish candidates (rev/profit labels + ≥20 numbers) | 86 | 86.0 |
| Strong bundle (rev+profit+EPS labels + ≥40 numbers) | 72 | 72.0 |

11 download failures were **spaces/parentheses in CDN paths** (now fixed with URL-encoding in the harness).

### Metric *label* hits (not verified values)

| Label family | Hit % |
|---|---:|
| revenue / turnover | 85.0 |
| profit / PAT | 79.0 |
| EPS | 77.0 |
| assets / equity | 85.0 |

## Deeper spot-check (15 PDFs, regex candidates)

Open-source text extract often **finds numbers**, but disambiguation is the hard part:

| Observation | Example |
|---|---|
| Multiple EPS candidates | `5.48`, `2.26`, `1.58` in one quarterly (basic vs diluted / YTD vs quarter / group vs company) |
| Empty / near-empty extract | One “annual” file returned ~19 chars (scan or bad PDF) |
| False “revenue” numbers | Year tokens (`2023`, `2024`) or scale stubs (`000`) matched near labels |
| Sometimes clean-looking | `AAF` quarterly: revenue `473,872,301` + EPS candidates present |

**Conclusion:** CSE PDFs are **good enough to attempt** extraction (~87% text-ok). They are **not good enough to trust auto-calcs in Telegram** without a verification layer (unit/scale, period, basic vs diluted, consolidated vs company).

## Vs open-source “fin statement” tools

| Approach | Fit for CSE |
|---|---|
| `edgartools` / US XBRL | Poor fit — CSE archives are PDFs, not XBRL |
| `FinTable` / `report_parser` / LLM table parse | Plausible on the 72% “strong” subset; needs per-layout tweaks + validation |
| Quiverly `pypdf` briefs (already shipped) | Right layer for **narrative** summaries |

## Recommendation for Quiverly

1. **Do try calcs offline** on the strong subset (this spike supports that).  
2. **Do not** push raw computed EPS/PE/YoY as alert truth in v1.  
3. If we continue: build a validator (period + scale + basic/diluted) and only surface figures with “verify in filing”.  
4. Keep product default: disclosure alert + AI brief.

**Follow-up (done):** `CSE_FINANCIAL_TABLE_VALIDATE_EVAL.md` — FinTable-style page-text parse + validators on the 72 strong PDFs.  
**Accuracy follow-up (done):** `CSE_FINANCIAL_ACCURACY_EVAL.md` — iterated extractor to **100% coverage** on 41 unique strong filings and **100% human-gold value match** on a 10-filing panel (current-quarter / Group conventions). Still research-only.

## Errors (pre URL-encode fix)

Mostly unescaped spaces in `cdn.cse.lk` paths — harness now encodes path segments.

## Kinds

```json
{ "quarterly": 50, "annual": 50 }
```

Raw machine output: `cse_financial_pdf_eval_20260713T045432Z.json`
