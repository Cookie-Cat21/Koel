# Plan: Calc alerts (`/alert SYMBOL eps above X`)

Status: **research-feasible at ≥99% on non-circular gold**  
Harness: `scripts/experiments/cse_eps_calc_alert_feasibility.py`  
Latest report: `docs/experiments/CSE_EPS_CALC_ALERT_FEASIBILITY.md`

## What “calc alert” means (v1 semantics)

| Field | Rule |
|---|---|
| Metric | **Basic EPS** (diluted stored, not default trigger) |
| Period | Current quarter (quarterlies) / full year (annuals) |
| Entity | **Group** preferred over Company-only |
| Trigger | New financial PDF extract vs user threshold |
| Compare | `eps_above`: fire if `eps_basic > X`; `eps_below`: `eps_basic < X` |
| Dedupe | One fire per `(rule_id, filing_id)` — not continuous polling |
| Fail closed | If extract gates fail → **do not fire**; log only |

This is not a live price poll. It is a filing-event alert.

## Feasibility evidence (must hold before bot wiring)

Gates (all required):

1. Human-seed EPS accuracy ≥ 99% (hand-labeled SOPL truth)
2. Human+dual-agree scored set ≥ 99%
3. Synthetic threshold decision accuracy ≥ 99%
4. Filing→filing crossing accuracy ≥ 99%
5. Disagreements excluded from gold until human-labeled (no circular “prefer main”)

Latest run: **YES** — seed 15/15, scored 37/37, alerts 100%, crossings 28/28.

Hard bugs fixed before this gate was honest:

- Note refs mistaken for EPS (`38.1`, `12.1`, `23` / page `300`)
- Quarterly-analysis `(1.45)` beating SOPL `1.45`
- TOC page numbers (e.g. `253`) as EPS

## Production path (ordered)

### Phase 0 — freeze research contract (done when gates pass)

- [x] Extractor note/TOC stripping + SOPL preference
- [x] Non-circular gold scoring
- [x] Feasibility harness green at 99%
- [ ] Expand **human** gold to ≥50 filings (still required before flag flip)
- [ ] Spot-check the 4 `extractor_only` rows (ACL, ACME, AMF, ASHO)

### Phase 1 — storage

Migration:

```text
filing_metrics (
  id, symbol, filing_id, kind,  -- quarterly|annual
  published_at, pdf_url,
  eps_basic, eps_diluted,
  revenue, profit,
  scale,            -- units|thousands|millions
  entity,           -- group|company
  period_tag,       -- quarter|annual
  extract_ok,       -- bool gate
  extract_notes,    -- jsonb
  created_at
)
unique (filing_id) or (symbol, pdf_url)
```

Extend `alert_rules.type`:

- `eps_above`
- `eps_below`

Add `alert_log` uniqueness on `(rule_id, filing_id)` (or equivalent dedupe key).

### Phase 2 — extract job (not in Telegram request path)

On new CSE financial disclosure for a watched symbol:

1. Download PDF
2. Run extractor (promote from research script → `koel/extractors/financial_pdf.py`)
3. Gate: `eps_basic` present + adjacency verified + not analysis-page-only
4. Persist `filing_metrics` (`extract_ok=true|false`)
5. If `extract_ok`, evaluate matching `eps_*` rules
6. Fire Telegram once; include EPS, period, scale, Group/Company, PDF link, NFA

Rate-limit politely; reuse disclosure poller — do not scrape on `/alert`.

### Phase 3 — bot UX

```text
/alert SYMBOL eps above X
/alert SYMBOL eps below X
/myalerts   # shows eps rules with last filing EPS if known
```

Validation:

- Symbol on watchlist (or auto-watch)
- `X` finite float
- Reply confirms semantics: “fires when next financial filing’s **basic EPS** is above X (not live price)”

### Phase 4 — safety rails (non-negotiable)

- Fail closed on extract failure
- Message always: not financial advice
- Never fire on narrative/highlights-only pages
- Feature flag `EPS_CALC_ALERTS_ENABLED=false` until human gold ≥50 and a week of shadow mode
- Shadow mode: compute would-fire into `alert_log` with `message_sent=false`

### Phase 5 — shadow → prod

1. Shadow on all watched financial PDFs for ≥1 market week
2. Diff would-fire vs human spot checks
3. Flip flag for allowlisted symbols, then all

## Explicit non-goals (still)

- No diluted-default alerts in v1
- No YoY / QoQ auto calc beyond raw filing EPS
- No “estimated EPS” / broker consensus
- No wiring into price poller

## Implementation sketch (code touchpoints)

| Area | Change |
|---|---|
| `migrations/` | `filing_metrics` + rule types + dedupe |
| `koel/extractors/financial_pdf.py` | Promote hardened extractor from experiments |
| Disclosure/poller job | Call extractor on new financial PDF |
| Rule engine | `eps_above` / `eps_below` vs `filing_metrics` |
| `bot.py` | Parse `/alert … eps above|below` |
| Config | Feature flag + shadow mode |

## Go / no-go

| Condition | Decision |
|---|---|
| Feasibility gates green + human gold ≥50 + shadow clean | Ship behind flag |
| Any seed miss / note-ref regression | Stay research-only |
| User asks for live “EPS estimate” alerts | Refuse — out of v1 semantics |
