# CSE financial table parse + validator spike

Generated: `2026-07-13T05:10:42.052786+00:00`  
Input: **72** PDFs from the prior “strong” set (rev+profit+EPS labels + ≥40 numbers).  
Extractor: FinTable-style SOPL page ranking (PyMuPDF) → **page-text line parse** (primary) + **pdfplumber** tables (gap-fill). Camelot/FinTable GUI stack not used (install friction); **no LLM API keys** here.  
Harness: `scripts/experiments/cse_financial_table_validate_eval.py`

## Headline

| Verdict | Count | % |
|---|---:|---:|
| Unambiguous (period+scale+EPS typed, metrics present) | 9 | 12.5 |
| Ambiguous (extracted but validator warnings) | 28 | 38.9 |
| Fail (missing metrics / no tables) | 35 | 48.6 |
| Gated OK (typed EPS + no hard conflicts; still verify-in-filing) | 9 | 12.5 |

Unique issuers in the gated/unambiguous set: **AAF, AEL, AGPL, AMSL, ASIR** (some symbols appear twice because the strong set kept two quarterlies each).

### Coverage of line items (any candidate)

- Revenue row with number: **65** / 72
- Profit row with number: **55** / 72
- Any EPS number: **58** / 72
- Basic **and** diluted both found: **9** / 72

### Validator breakdown

```json
{
  "scale_counts": {
    "unknown": 32,
    "millions": 17,
    "thousands": 23
  },
  "eps_validator": {
    "ok_basic_and_diluted": 9,
    "missing": 14,
    "ok_basic_only": 16,
    "generic_only": 27,
    "diluted_only": 6
  },
  "period_validator": {
    "ok_resolved_current_quarter": 26,
    "ok_or_assumed_annual": 37,
    "untagged": 2,
    "ok_tagged": 7
  },
  "gated_ok": 9,
  "gated_ok_pct": 12.5,
  "top_ambiguity_reasons": [
    [
      "eps:generic_unlabeled_basic_or_diluted",
      27
    ],
    [
      "revenue:conflicting_candidates",
      20
    ],
    [
      "profit:conflicting_candidates",
      10
    ],
    [
      "eps:diluted_without_basic",
      6
    ],
    [
      "scale:revenue_too_small_for_thousands",
      4
    ],
    [
      "eps:conflicting_candidates",
      2
    ],
    [
      "profit:multi_column_tie",
      2
    ],
    [
      "revenue:multi_column_tie",
      2
    ],
    [
      "period:untagged",
      2
    ],
    [
      "scale:revenue_huge_for_millions_label",
      2
    ],
    [
      "scale:unknown_and_tiny_revenue",
      2
    ]
  ],
  "top_fail_reasons": [
    [
      "profit:missing",
      17
    ],
    [
      "eps:missing",
      14
    ],
    [
      "revenue:missing",
      7
    ]
  ]
}
```

## What “unambiguous” / “gated OK” mean here

Research-only gates — **not** ground-truth audited against every PDF cell:

1. Revenue + profit numbers found on a SOPL-like page/table
2. EPS present as **basic** (or basic+diluted); generic-only → ambiguous
3. No hard conflicting candidate sets for the chosen lines
4. Period tagged or rule-resolved (leftmost = current quarter when Q+YTD)
5. Comparative multi-column layouts are **expected** (not auto-fail)

**Gated OK** = extractable enough to maybe show in a brief with “verify in filing”. Still **not** Telegram alert truth.

A human still needs to confirm the figure before it could ever be alert truth.

## Sample rows

### Unambiguous

- `AAF.N0000` (quarterly) scale=unknown periods=['annual', 'has_comparative', 'quarter', 'ytd']  
  rev=2358166994.0 (`2,358,166,994`) ← 'Interest Income'  
  pat=280257691.0 (`280,257,691`) ← 'Profit for the Period'  
  eps_b=2.26 (`2.26`) ← 'Basic Earnings Per Share (Rs.)' eps_d=1.58 (`1.58`) ← 'Diluted Earnings Per Share (Rs.)'
- `AAF.N0000` (quarterly) scale=unknown periods=['annual', 'has_comparative', 'quarter', 'ytd']  
  rev=2358166994.0 (`2,358,166,994`) ← 'Interest Income'  
  pat=280257691.0 (`280,257,691`) ← 'Profit for the Period'  
  eps_b=2.26 (`2.26`) ← 'Basic Earnings Per Share (Rs.)' eps_d=1.58 (`1.58`) ← 'Diluted Earnings Per Share (Rs.)'
- `AEL.N0000` (quarterly) scale=unknown periods=['annual', 'has_comparative', 'quarter', 'ytd']  
  rev=13400679319.0 (`13,400,679,319`) ← 'Revenue'  
  pat=1388489168.0 (`1,388,489,168`) ← 'Profit for the period'  
  eps_b=1.24 (`1.24`) ← 'Basic earnings per share' eps_d=—
- `AEL.N0000` (quarterly) scale=unknown periods=['annual', 'has_comparative', 'quarter', 'ytd']  
  rev=13400679319.0 (`13,400,679,319`) ← 'Revenue'  
  pat=1388489168.0 (`1,388,489,168`) ← 'Profit for the period'  
  eps_b=1.24 (`1.24`) ← 'Basic earnings per share' eps_d=—
- `AGPL.N0000` (quarterly) scale=thousands periods=['quarter', 'ytd']  
  rev=1606483.0 (`1,606,483`) ← 'Revenue'  
  pat=94826.0 (`94,826`) ← 'Net Profit for the Period'  
  eps_b=0.19 (`0.19`) ← 'Basic Earnings Per Share' eps_d=—

### Ambiguous

- `ABAN.N0000` (quarterly): period:untagged, profit:conflicting_candidates, scale:revenue_huge_for_millions_label  
  rev=1928502029.0 (`1,928,502,029`) ← 'Turnover' eps_g=—
- `ABAN.N0000` (quarterly): period:untagged, profit:conflicting_candidates, scale:revenue_huge_for_millions_label  
  rev=1928502029.0 (`1,928,502,029`) ← 'Turnover' eps_g=—
- `ABAN.N0000` (annual): eps:generic_unlabeled_basic_or_diluted, revenue:conflicting_candidates, scale:unknown_and_tiny_revenue  
  rev=5.13 (`5.13`) ← 'Revenue' eps_g=23.0 (`23`) ← 'EPS'
- `ABAN.N0000` (annual): eps:generic_unlabeled_basic_or_diluted, revenue:conflicting_candidates, scale:unknown_and_tiny_revenue  
  rev=5.13 (`5.13`) ← 'Revenue' eps_g=23.0 (`23`) ← 'EPS'
- `ACL.N0000` (quarterly): eps:diluted_without_basic  
  rev=12179908.0 (`12,179,908`) ← 'Revenue' eps_g=—

### Fail

- `AAF.N0000` (annual): revenue:missing
- `AAIC.N0000` (quarterly): revenue:missing
- `AAIC.N0000` (quarterly): revenue:missing
- `AAIC.N0000` (annual): eps:missing
- `AAIC.N0000` (annual): eps:missing

### Gated OK examples

- `AAF.N0000` (quarterly) verdict=unambiguous scale=unknown  
  rev=2358166994.0 (`2,358,166,994`) ← 'Interest Income'  
  pat=280257691.0 (`280,257,691`) ← 'Profit for the Period'  
  eps_b=2.26 (`2.26`) ← 'Basic Earnings Per Share (Rs.)' eps_d=1.58 (`1.58`) ← 'Diluted Earnings Per Share (Rs.)'
- `AAF.N0000` (quarterly) verdict=unambiguous scale=unknown  
  rev=2358166994.0 (`2,358,166,994`) ← 'Interest Income'  
  pat=280257691.0 (`280,257,691`) ← 'Profit for the Period'  
  eps_b=2.26 (`2.26`) ← 'Basic Earnings Per Share (Rs.)' eps_d=1.58 (`1.58`) ← 'Diluted Earnings Per Share (Rs.)'
- `AEL.N0000` (quarterly) verdict=unambiguous scale=unknown  
  rev=13400679319.0 (`13,400,679,319`) ← 'Revenue'  
  pat=1388489168.0 (`1,388,489,168`) ← 'Profit for the period'  
  eps_b=1.24 (`1.24`) ← 'Basic earnings per share' eps_d=—
- `AEL.N0000` (quarterly) verdict=unambiguous scale=unknown  
  rev=13400679319.0 (`13,400,679,319`) ← 'Revenue'  
  pat=1388489168.0 (`1,388,489,168`) ← 'Profit for the period'  
  eps_b=1.24 (`1.24`) ← 'Basic earnings per share' eps_d=—
- `AGPL.N0000` (quarterly) verdict=unambiguous scale=thousands  
  rev=1606483.0 (`1,606,483`) ← 'Revenue'  
  pat=94826.0 (`94,826`) ← 'Net Profit for the Period'  
  eps_b=0.19 (`0.19`) ← 'Basic Earnings Per Share' eps_d=—

## Vs prior spike

| Layer | Result |
|---|---|
| Text label presence (prior) | ~72% “strong” |
| Structured extract coverage (rev/profit/EPS any) | 65/72 rev, 55/72 profit, 58/72 EPS |
| Table parse + validators (this run) | 12.5% unambiguous / 38.9% ambiguous / 48.6% fail |
| Gated OK (typed EPS, period OK, no hard conflicts) | 12.5% |

Label presence ≫ structured numbers ≫ validator-clean numbers. Even gated-OK rows are research-only.

## FinTable / LLM status

- **FinTable** upstream depends on `camelot` + GUI; camelot did not install cleanly here. We reused its *idea* (keyword page rank → SOPL rows) via PyMuPDF page text (primary — CSE often keeps labels *outside* pdfplumber grids) + pdfplumber tables (gap-fill).
- **LLM table parse**: no `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` in env — skipped. Next experiment if keys available: same validator gate on LLM JSON extracts (especially the ambiguous / fail buckets).

## Spot-check (manual)

`AAF.N0000` quarterly SOPL text yields Interest Income `2,358,166,994`, Profit for the Period `280,257,691`, Basic EPS `2.26`, Diluted EPS `1.58` — matches a human reading of page text. Validators still flag residual candidate conflicts on some filings.

## Recommendation for Quiverly

1. Still **do not** ship auto EPS/PE/YoY as alert truth.
2. Offline extract + validators is useful for research / brief enrichment with “verify in filing”.
3. Highest-value next step with an API key: LLM extract on the non-gated bucket, still behind the same validators.

Raw JSON: `cse_financial_table_validate_eval_20260713T051042Z.json`

