# R1_OPS — Adversarial review of WAVE1_OPS

**Lane:** OPS (WS-041…WS-060)  
**Inputs:** [WAVE1_OPS.md](../workstreams/WAVE1_OPS.md), [COMMIT_FACTORY.md](../COMMIT_FACTORY.md), [README.md](../../../README.md), [pyproject.toml](../../../pyproject.toml), [FINAL_REPORT.md](../../FINAL_REPORT.md)  
**Date:** 2026-07-11

---

## 1. Verdict

**Conditional pass — cut ~40% of the catalog before Pass 1.**

The wave correctly names the real OPS hole (no GitHub Actions, no local Postgres, 3 DB tests skipped, no one-command DX). That is enough for a strong Pass 1. The rest of the wave pads the catalog with twin DX tools, day-1 Dependabot, coverage SaaS-adjacent artifacts, pre-commit, PR templates, and a Prometheus/`/metrics` export for a latency number that already lands in structlog.

COMMIT_FACTORY Pass 1 OPS is “CI workflow running ruff/mypy/pytest.” That is necessary but **insufficient**: quality bar #2’s advisory-lock proof still never runs in automation, and bar #5’s “one-command run” is still a four-line bash block. Pass 1 must close CI + ephemeral Postgres + migrate + DB pytest; everything else waits.

---

## 2. Ranked improvements (max 15)

1. **Merge CI migrate + DB pytest into the first CI ship** — WS-041 alone ships a green CI that still skips the only multi-process lock test that matters. Treat WS-048 + WS-056 as the same Pass 1 concern (or one workflow with two jobs), not wave-2/4 polish.
2. **Collapse Make early** — WS-054 depends on seed + probe; wrong. Ship `install` / `lint` / `typecheck` / `test` / `up` / `migrate` in the same pass as compose; add `seed` / `probe-health` / `smoke` later.
3. **Cut the justfile** — WS-055 doubles recipe maintenance for zero CI value. One DX entrypoint (Make **or** a single `scripts/dev.sh`). Prefer Make; delete just from Wave 1.
4. **Defer Dependabot** — WS-058 after one green CI week, not day 1. Pin action majors in WS-041; Dependabot PRs before the workflow is stable are noise.
5. **Defer latency export (WS-047)** — Stage A already logs `alert_latency_ms`. p95 scrape path is Pass 3+ observability, not a Wave 1 must. Keep WS-046 log-field doc if cheap; do not build `/metrics` yet.
6. **Defer coverage artifacts (WS-044)** — `cov-fail-under=85` already fails the job. XML/HTML upload does not catch regressions the gate misses. After CI is green.
7. **Seed is optional for Pass 1** — WS-043 helps humans demo the bot; advisory-lock and poller integration tests apply their own migrate. Do not block CI DB enablement on seed.
8. **Formal pytest markers** — Missing from the wave. Mark `integration` / `requires_db` so CI can run `pytest -m "not requires_db"` vs full suite without `skipif` folklore. Coordinate with CORE ownership of `tests/`.
9. **Pin the install surface in CI** — `pip install .[dev]` without a lockfile will drift. Either commit a `requirements-dev.txt` freeze or document `pip-compile` / uv lock as a follow-up WS. Wave 1 is silent on reproducibility.
10. **Python version contract** — `requires-python = ">=3.11"` + setup-python 3.11 is fine; add a one-line matrix note (3.11 only for now) so agents don’t “helpfully” add 3.12 and break binary wheels mid-factory.
11. **App Dockerfile is correctly optional** — Keep compose DB-only until a real deploy target exists. Do not invent multi-service app compose in WS-057 before Make + probe work.
12. **Smoke must be health-first** — WS-057 risks live cse.lk. Acceptance should be: migrate + start `both`/`poller` + `/health` 200/503 as documented — **no** forced tick against production CSE in CI/smoke unless mocked.
13. **CONTRIBUTING before PR templates** — WS-050 then WS-051 is right; do not ship templates in Pass 1. Agents need setup + lane fences more than checkbox HTML.
14. **Secrets: doc + one cheap CI grep is enough** — WS-052’s SECRETS.md + tracked-file pattern check yes; gitleaks / push-protection prose as human checklist, not a blocker WS.
15. **Runbook last, not parallel fluff** — WS-060 only after the commands it documents exist. Stub RUNBOOK early invites doc drift (factory already bans README thrash).

---

## 3. Over-engineering to cut

| Cut / defer | Why |
|---|---|
| **WS-055 justfile** | Duplicate of Make. Drift risk > contributor preference. Pick Make. |
| **WS-058 Dependabot day 1** | Pin `@v4` (or SHA) in first CI commit; Dependabot after CI is trusted. Weekly Actions bumps during factory churn waste review budget. |
| **WS-047 `/metrics` or JSONL exporter** | Latency honesty is already README + structlog. Export without a consumer is dead code. |
| **WS-044 coverage artifact + PR comment** | Fail-under is the gate; artifacts are archaeology. |
| **WS-049 pre-commit** | Explicitly optional and CI is SoT — fine as Pass 5+, not Wave 1 critical path. |
| **WS-051 PR / issue templates** | Factory already has COMMIT_FACTORY + pass reports; templates don’t unblock bar #5–#6. |
| **WS-059 failure taxonomy** | Named steps in WS-041 are enough; `$GITHUB_STEP_SUMMARY` taxonomy is polish. |
| **WS-057 full compose app profile** | Premature. DB compose + `make migrate` + manual `koel both` + probe script beats multi-service smoke theater. |
| **Five-commit micro-slicing per WS** | Constitution bans count farming. Several OPS WS should land as **1–2 commits** (e.g. CI+Postgres service = one workflow PR). |

**just + make both?** No. Canonical Make; drop just from Wave 1.  
**Dependabot day 1?** No. Pin actions now; Dependabot later with `open-pull-requests-limit`.

---

## 4. Missing must-haves for a Python + Postgres bot

Wave 1 lists DX/docs well but under-weights runtime ops for this stack:

| Gap | Why it matters |
|---|---|
| **CI Postgres + full pytest (incl. advisory lock)** | FINAL_REPORT: 3 skipped; bar #2 proof is local-only today. Highest OPS debt. |
| **Explicit `unit` vs `integration` markers** | Without markers, “strict no-skip” (WS-056) is brittle and fights CORE test style. |
| **Reproducible CI deps** | Unpinned transitive deps + `psycopg[binary]` can flake CI silently. |
| **Migrate forward-only policy in the first checklist** | WS-045 mentions it; it should ship with WS-048, not wait for a release doc. |
| **Health probe as release/smoke primitive** | WS-053 is right; undervalued vs coverage/Dependabot. |
| **No “how to run two processes” / leader election ops note** | Dual-poller + advisory lock is CORE, but OPS runbook must say: one leader, what `/health` looks like on lock-skip (503 degraded). Missing until WS-060. |
| **Graceful shutdown verification** | Bar #5 claims it; OPS wave never probes SIGTERM on `both`. Coordinate with CORE WS-012; OPS should at least document expected exit. |
| **Rate-limit / smoke CSE policy** | Noted in WS-057 risk — elevate to a hard acceptance: smoke **must not** call cse.lk in CI. |
| **`.env.example` ↔ compose alignment** | WS-042 covers it; ensure placeholders stay empty (token) and `koel`/`koel`/`koel` match compose — already planned, keep non-negotiable. |
| **No deploy target** | Acceptable for Wave 1, but RELEASE_CHECKLIST must not pretend tagging == shipped Telegram bot. |

Not missing yet (correctly deferred): app Dockerfile, K8s, log aggregation SaaS, coverage SaaS.

---

## 5. Order-of-operations fixes

**Proposed Pass-critical order (replaces the wave’s “parallel everything nice”):**

```
WS-041 CI (ruff/mypy/pytest)
   └── same pass: Postgres service + migrate (WS-048) + DATABASE_URL pytest (WS-056)
WS-042 compose ──► thin Make: install/lint/test/up/migrate (partial WS-054)
WS-053 health probe ──► Make probe-health
WS-050 CONTRIBUTING (after compose+Make exist so commands are real)
WS-052 secrets doc + CI grep (after CI exists)
WS-043 seed (after migrate path is boring)
WS-045 release checklist (after CI+migrate proof commands exist)
WS-046 log fields (doc-only, anytime low priority)
WS-060 runbook (last)

DEFER: 044, 047, 049, 051, 055, 057, 058, 059
```

**Concrete precedence bugs in the wave’s suggested order:**

| Wave says | Fix |
|---|---|
| Batch 1: 041 ∥ 042 ∥ 046 ∥ 050 | Drop 046/050 from Pass 1 critical path; 050 needs real compose/Make commands. |
| 048 in batch 2, 056 in batch 4 | Too late. 056 is why 048 exists — same pass. |
| 054 after 043 + 053 | Split: Make core with 042; extend after probe/seed. |
| 055 mirrors 054 | Cut 055. |
| 058 with late polish | Defer entirely past first green CI epoch. |
| 047 after 046 as if blocking | Neither blocks bar #5–#6; both after Pass 1. |

**File-ownership reminder:** OPS owns workflows/compose/Make/docs; enabling DB tests is **env-only**. Do not rewrite `tests/test_advisory_lock.py` in an OPS commit without CORE sync — markers are the only justified joint touch.

---

## 6. Top 5 OPS WS for Pass 1

| Rank | WS | Pass 1 scope |
|---|---|---|
| 1 | **WS-041** | `.github/workflows/ci.yml`: checkout, Python 3.11, `pip install -e ".[dev]"`, ruff, mypy, pytest. Pin action major tags. |
| 2 | **WS-048 + WS-056** (treat as one deliverable) | Postgres service container, `DATABASE_URL`, `python -m koel migrate`, full pytest — advisory-lock test **runs**, not skipped. |
| 3 | **WS-042** | `docker-compose.yml` Postgres 16 + `.env.example` alignment + README “Local Postgres” blurb. |
| 4 | **WS-054 (thin)** | Makefile: `install`, `lint`, `typecheck`, `test`, `up`, `down`, `migrate`, `help`. No seed/smoke/just yet. |
| 5 | **WS-053** | `scripts/probe_health.py` (or `python -m koel healthcheck`) with exit codes; wire `make probe-health`. |

**Explicitly not Pass 1:** justfile, Dependabot, coverage artifacts, `/metrics`, pre-commit, PR templates, compose app smoke, runbook novel, release checklist (stub OK only if it lists the five proof commands above).

---

**Bottom line:** Ship automation that proves what FINAL_REPORT already claims locally. Cut twin DX tools and day-1 supply-chain theater until CI + DB tests are boring.
