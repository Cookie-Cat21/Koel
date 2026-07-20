# Wave 86 — Adversarial CLEAN (post-CDN soft-accept)

**Verdict:** CLEAN (0 findings above minor)  
**Date:** 2026-07-13  
**HEAD reviewed:** `afafc3f9`…`c578d60a` window (post `fix(w83)` CDN close + docs(w86) loop status; before parallel w88–w90 lands)  
**Branch:** `cursor/tijori-cse-phase1-e44e`

## Scope

Adversarial re-probe after the late CDN soft-accept close (`862295ed`) and the
thin docs(w86) loop-status push:

- Re-check claim/lock/health/count soft-accepts (w76–w85) — still closed
- Re-check `fetch_cdn_pdf` status / `is_redirect is True` / content-length
  guards from `fix(w83)`
- Spot-check bot digit parsers, `parse_hhmm`, notify RetryAfter, CSE `_request`
  status path, briefs provider HTTP errors
- No duplicate `int(True)==1` pin farming on exhausted RETURNING/COUNT surfaces

## Result

**No new medium+ defects.** Residual coerce sites remain fail-closed or below
medium (bot digit parsers, HH:MM split, provider status stringification for
error text only). CSE `status_code >= 400` on fixed `base_url` paths is not new
medium fuel relative to allowlisted CDN PDF URL fetches (already
`follow_redirects=False`).

## Relation to CLEAN×2

| Pass | Verdict |
|---|---|
| w83 | CLEAN — soft-accept isinstance hunting exhausted |
| w86 | CLEAN — post-CDN re-probe; 0 findings above minor |
| w87 | CLEAN — WS-087 clock-skew claim invariant (separate fuel) |

w83 + w86 close the soft-accept / post-CDN adversarial lane. w87 independently
closes clock-skew claim probing. Prefer briefs soak / rate-cap ops / user-visible
gaps over further pin churn.

## Gate

`DATABASE_URL= pytest -m 'not integration' --cov=koel --cov-fail-under=100`
→ **100.00%** (3866 stmts / 0 miss) at review HEAD.
