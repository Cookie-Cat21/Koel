# WAVE1_OPS — Planning workstreams WS-041…WS-060

**Lane:** OPS (`.github/`, Docker, DX scripts, factory docs)  
**Goal:** CI, local one-command run, observability standards — no app feature work.  
**Baseline (Stage A):** ruff/mypy/pytest proven locally; `/health` + structlog + `alert_latency_ms` exist; **no** GitHub Actions, docker-compose, Makefile/justfile, pre-commit, CONTRIBUTING, or PR templates yet ([FINAL_REPORT.md](../../FINAL_REPORT.md), [README.md](../../README.md)).  
**Fence:** Planning + OPS/DX scaffolding only when implemented; do not touch alert semantics, bot UX, or DASH product code in these WS commits.

---

## WS-041 — GitHub Actions CI (lint + typecheck + unit tests)

| Field | Content |
|---|---|
| **id** | WS-041 |
| **title** | GitHub Actions CI for ruff, mypy, and pytest |
| **why** | Factory quality bar requires proof on every PR; today checks only run locally. Pass 1 OPS in COMMIT_FACTORY is exactly this. |
| **acceptance criterion** | On `push`/`pull_request` to the default branch, a workflow runs `ruff check`, `mypy koel`, and `pytest` (using `pyproject.toml` addopts / cov-fail-under=85) and fails the job on any non-zero exit. |
| **commits 1–5** | 1. Add `.github/workflows/ci.yml` skeleton (checkout, setup-python 3.11). 2. Cache pip + install `.[dev]`. 3. Add ruff + mypy steps. 4. Add pytest step (no Postgres service yet). 5. Document CI badge / “CI” section pointer in README (one short paragraph). |
| **deps** | None (first OPS wave item). |
| **risk** | Low — path filters / wrong Python version could flake; pin `actions/setup-python` major. |

---

## WS-042 — docker-compose Postgres for local DX

| Field | Content |
|---|---|
| **id** | WS-042 |
| **title** | docker-compose service for ephemeral local Postgres |
| **why** | README assumes `DATABASE_URL`; without compose, contributors need external Neon/Supabase just to migrate and run advisory-lock tests. |
| **acceptance criterion** | `docker compose up -d` starts Postgres 16 (or 15+) exposing a documented port; `.env.example` documents a matching `DATABASE_URL`; data volume is named and gitignored if bind-mounted. |
| **commits 1–5** | 1. Add `docker-compose.yml` with `postgres` service + healthcheck. 2. Add named volume + sane defaults (user/db/password `koel`). 3. Align `.env.example` `DATABASE_URL` with compose. 4. Add short “Local Postgres” subsection to README. 5. Add `.dockerignore` if an app Dockerfile is not yet present (compose-only is fine). |
| **deps** | None (pairs with WS-054 for one-command). |
| **risk** | Low — port 5432 conflicts on contributor machines; document `ports` override. |

---

## WS-043 — Seed / demo data script

| Field | Content |
|---|---|
| **id** | WS-043 |
| **title** | Idempotent seed/demo data for local and CI smoke |
| **why** | Empty DB blocks manual `/health` + rule-engine demos; factory needs a fixed symbol set without hitting cse.lk for every DX path. |
| **acceptance criterion** | A documented command (e.g. `python -m koel seed` or `scripts/seed_demo.py`) inserts deterministic stocks, one demo user (fake telegram_id), watchlist rows, and inactive sample alert_rules; re-run is idempotent (no duplicate key failures). |
| **commits 1–5** | 1. Add seed SQL or Python module under `db/` or `scripts/` (OPS-owned). 2. Wire CLI entry or script README usage. 3. Seed only non-secret fake telegram_ids; never real tokens. 4. Add pytest that seed is idempotent when `DATABASE_URL` set (skip otherwise). 5. Link seed from README + CONTRIBUTING (when present). |
| **deps** | WS-042 (local DB); migrate path already exists. |
| **risk** | Medium — must not invent production schema changes; stay within existing tables from `001_initial.sql`. |

---

## WS-044 — Coverage reporting in CI

| Field | Content |
|---|---|
| **id** | WS-044 |
| **title** | Publish pytest coverage artifact / summary in CI |
| **why** | `cov-fail-under=85` already gates locally; CI should surface term-missing and retain an artifact so regressions are reviewable without re-running. |
| **acceptance criterion** | CI pytest step emits coverage (term + XML or HTML); job uploads `coverage.xml` or `htmlcov/` as a workflow artifact; job still fails if coverage &lt; 85% on `koel.rules`. |
| **commits 1–5** | 1. Extend pytest CI step with `--cov-report=xml` (keep fail-under). 2. `actions/upload-artifact` for coverage. 3. Optional PR comment or job summary with coverage %. 4. Ensure `.gitignore` still ignores `htmlcov/` / `.coverage`. 5. Note coverage gate in release checklist (WS-045). |
| **deps** | WS-041. |
| **risk** | Low — artifact retention defaults; avoid third-party coverage SaaS unless free and logged in THIRD_PARTY.md. |

---

## WS-045 — Release checklist

| Field | Content |
|---|---|
| **id** | WS-045 |
| **title** | Documented release checklist for tagged versions |
| **why** | Stage A has no release process; OPS bar expects one-command run + honest latency claims — releases must not oversell CSE→TG SLO. |
| **acceptance criterion** | `docs/factory/RELEASE_CHECKLIST.md` (or `docs/RELEASE_CHECKLIST.md`) lists ordered gates: CI green, migrate dry-run, health probe, NFA copy spot-check, latency claim wording, version bump in `pyproject.toml`, tag format `vX.Y.Z`. |
| **commits 1–5** | 1. Add checklist skeleton with Stage A proof commands. 2. Add “latency honesty” checkbox citing README SLO. 3. Add secrets / `.env` not-in-tag checkbox. 4. Add rollback note (revert tag + migrate forward-only policy). 5. Link checklist from README “Stack” or factory index. |
| **deps** | WS-041 (CI exists to check off). |
| **risk** | Low — doc-only; keep out of product marketing tone. |

---

## WS-046 — Structured log fields standard

| Field | Content |
|---|---|
| **id** | WS-046 |
| **title** | Canonical structlog field names and event catalog |
| **why** | `logging_setup.py` JSON-logs today, but field names for alerts/polls/CSE errors are ad hoc; OPS quality bar needs greppable, stable keys across agents. |
| **acceptance criterion** | `docs/ops/LOG_FIELDS.md` defines required/optional keys (`event`, `symbol`, `rule_id`, `alert_latency_ms`, `component`, `error_type`, …) and forbidden PII (tokens, full connection strings); existing high-traffic log sites either already comply or are listed as follow-up CORE tickets — **no** semantic rule changes in this WS. |
| **commits 1–5** | 1. Draft field catalog from current poller/notify/adapter logs. 2. Document levels (INFO vs WARNING) for CSE failures. 3. Add “never log TELEGRAM_BOT_TOKEN / DATABASE_URL password” rule. 4. Optional tiny helper constants module *only if* zero behavior change. 5. Cross-link from CONTRIBUTING. |
| **deps** | None for the doc; code alignment may soft-depend on CORE. |
| **risk** | Medium if commits refactor log call sites aggressively — prefer doc-first; limit code to additive keys. |

---

## WS-047 — Latency metric export

| Field | Content |
|---|---|
| **id** | WS-047 |
| **title** | Export claim→send latency beyond structlog lines |
| **why** | FINAL_REPORT marks latency **partial**: `alert_latency_ms` is logged; OPS needs a scrape/export path for p95 tracking without claiming CSE→TG &lt;5s. |
| **acceptance criterion** | Documented export: either Prometheus text on `/metrics` (opt-in env) **or** a append-only JSONL/metrics file of `alert_latency_ms` samples; README states instrumented segment = claim→send only. |
| **commits 1–5** | 1. Spec metric name + labels (`rule_type` optional) in `docs/ops/METRICS.md`. 2. Implement opt-in exporter behind env flag (default off). 3. Unit test that a recorded sample appears in export format. 4. Wire health process or side endpoint without breaking `/health` contract. 5. Update release checklist latency checkbox. |
| **deps** | WS-046 (field names); health module ownership stays OPS-compatible. |
| **risk** | Medium — avoid pulling heavy metrics stacks; keep dependency count minimal (stdlib or tiny). |

---

## WS-048 — Migrate against ephemeral Postgres in CI

| Field | Content |
|---|---|
| **id** | WS-048 |
| **title** | CI job: apply migrations on service-container Postgres |
| **why** | Migrations are CLI-only today; broken SQL would only fail on a human’s DB. Ephemeral migrate is the OPS gate for schema commits. |
| **acceptance criterion** | CI starts `postgres` service, sets `DATABASE_URL`, runs `python -m koel migrate` successfully; job fails on migrate error. |
| **commits 1–5** | 1. Add Postgres service to workflow (image + health). 2. Export `DATABASE_URL` for job env. 3. Run migrate step after install. 4. Optionally run seed (WS-043) after migrate. 5. Document “migrate CI” in RELEASE_CHECKLIST. |
| **deps** | WS-041; WS-043 optional for seed step. |
| **risk** | Low — service container startup time; use health-cmd wait. |

---

## WS-049 — Optional pre-commit hooks

| Field | Content |
|---|---|
| **id** | WS-049 |
| **title** | Optional pre-commit config (ruff + basic secrets hygiene) |
| **why** | Contributors may want local gates before push; must remain optional so Cloud Agents / CI remain source of truth. |
| **acceptance criterion** | `.pre-commit-config.yaml` runs ruff (and optionally `end-of-file-fixer`); README/CONTRIBUTING say “optional”; CI does **not** require pre-commit installation. |
| **commits 1–5** | 1. Add `.pre-commit-config.yaml` with ruff. 2. Pin hook revisions. 3. Document `pre-commit install` as optional. 4. Add `dev` extra note or leave as standalone pip tool. 5. Do not enable auto-format commits that thrash history (factory ban). |
| **deps** | WS-041 (same ruff config as CI). |
| **risk** | Low — avoid mypy-in-pre-commit if too slow; keep hooks lean. |

---

## WS-050 — CONTRIBUTING guide

| Field | Content |
|---|---|
| **id** | WS-050 |
| **title** | CONTRIBUTING.md for factory + local DX |
| **why** | New agents/humans need lane ownership, quality bar, and “proper commit” rules without reading only COMMIT_FACTORY. |
| **acceptance criterion** | Root `CONTRIBUTING.md` covers setup (`pip install -e ".[dev]"`, compose, migrate), proof commands (ruff/mypy/pytest), lane file ownership (CORE/DASH/OPS), NFA/compliance pointers, and link to COMMIT_FACTORY. |
| **commits 1–5** | 1. Scaffold CONTRIBUTING with setup. 2. Add proof commands from FINAL_REPORT. 3. Add lane table + “no competitor scrape” note. 4. Add PR expectations (CI green, one concern). 5. Link from README. |
| **deps** | WS-042 recommended; WS-041 for CI mention. |
| **risk** | Low — keep short; no README thrash for count. |

---

## WS-051 — Branch and PR templates

| Field | Content |
|---|---|
| **id** | WS-051 |
| **title** | PR template + branch naming notes |
| **why** | Factory uses long-lived epoch PRs with pass reports; templates force acceptance criterion + proof commands into the description. |
| **acceptance criterion** | `.github/PULL_REQUEST_TEMPLATE.md` requires: summary, acceptance criterion, proof commands, fence check (CLAUDE.md), risk; `docs/ops/BRANCHING.md` (or CONTRIBUTING section) documents `factory/*` / `ops/*` naming — not enforced by bots in this WS. |
| **commits 1–5** | 1. Add PR template. 2. Add optional ISSUE_TEMPLATE for audit findings. 3. Document branch naming in CONTRIBUTING. 4. Add “Co-authored-by” trailer note from COMMIT_FACTORY. 5. Ensure templates do not mandate product features. |
| **deps** | WS-050. |
| **risk** | Low. |

---

## WS-052 — Secret scanning notes

| Field | Content |
|---|---|
| **id** | WS-052 |
| **title** | Secret scanning / hygiene documentation and baseline guards |
| **why** | Bot token + DB URL are the blast radius; `.gitignore` already ignores `.env`, but OPS should document GitHub secret scanning / push protection and add a cheap local guard. |
| **acceptance criterion** | `docs/ops/SECRETS.md` documents: never commit `.env`, use GitHub Actions secrets for any future deploy, enable GitHub secret scanning/push protection (human toggle), and lists sensitive env keys from `.env.example`; optional CI `rg`/gitleaks-lite step fails on committed `.env` or `TELEGRAM_BOT_TOKEN=` with non-empty value in tracked files. |
| **commits 1–5** | 1. Write SECRETS.md. 2. Add CI grep step for obvious leaked patterns in tracked files. 3. Confirm `.env.example` stays placeholder-empty. 4. Link from CONTRIBUTING + RELEASE_CHECKLIST. 5. Note: do not add real tokens to sample_responses. |
| **deps** | WS-041 for CI hook; WS-050 for doc link. |
| **risk** | Low — false positives on word “token” in docs; scope patterns tightly. |

---

## WS-053 — Healthcheck probe script

| Field | Content |
|---|---|
| **id** | WS-053 |
| **title** | CLI/script probe for `/health` JSON |
| **why** | README documents `http://127.0.0.1:8080/health`; release and compose need a one-shot probe that interprets 200 vs 503 without curl folklore. |
| **acceptance criterion** | `scripts/probe_health.py` (or `python -m koel healthcheck`) GETs `$HEALTH_HOST:$HEALTH_PORT/health`, prints status JSON, exits 0 on 200 and non-zero on 503/connection error; documented in README. |
| **commits 1–5** | 1. Add probe script using httpx/stdlib. 2. Support env overrides for host/port. 3. Exit codes documented. 4. Tiny unit test with mocked response. 5. Wire into make/just `health` target (WS-054/055). |
| **deps** | Existing `koel/health.py` contract; WS-054 for DX target. |
| **risk** | Low — do not change health payload semantics beyond reading them. |

---

## WS-054 — One-command Make targets

| Field | Content |
|---|---|
| **id** | WS-054 |
| **title** | Makefile for bootstrap, lint, test, db, run |
| **why** | Quality bar #5 “one-command run”; today setup is a multi-step bash block in README. |
| **acceptance criterion** | Root `Makefile` provides at least: `install`, `lint`, `typecheck`, `test`, `up` (compose), `migrate`, `seed` (if WS-043), `probe-health`, `tick` — each target documented via `make help`. |
| **commits 1–5** | 1. Add Makefile with `.PHONY` + help. 2. Wire install/lint/typecheck/test to project tools. 3. Wire docker compose up/down. 4. Wire migrate + tick --force. 5. Point README Setup at `make install && make up && make migrate`. |
| **deps** | WS-042; WS-043 for seed; WS-053 for probe. |
| **risk** | Low — keep portable POSIX make; no GNU-only if avoidable. |

---

## WS-055 — justfile companion targets

| Field | Content |
|---|---|
| **id** | WS-055 |
| **title** | Optional justfile mirroring Make DX targets |
| **why** | Some contributors prefer `just`; factory should not fork behavior — justfile mirrors Makefile recipes. |
| **acceptance criterion** | Root `justfile` exposes the same named recipes as Makefile (`install`, `lint`, `test`, `up`, `migrate`, …); CONTRIBUTING says “Make **or** just”; no requirement to install both in CI. |
| **commits 1–5** | 1. Add justfile with install/lint/test. 2. Mirror compose/migrate/seed. 3. Mirror probe-health + tick. 4. Document just as optional in CONTRIBUTING. 5. Avoid duplicating logic via thin shell scripts under `scripts/` if recipes diverge. |
| **deps** | WS-054 (canonical recipe list). |
| **risk** | Low — drift between Make and just; prefer shared `scripts/*.sh`. |

---

## WS-056 — CI integration job (DB-backed pytest)

| Field | Content |
|---|---|
| **id** | WS-056 |
| **title** | Run skipped DB tests against CI Postgres |
| **why** | FINAL_REPORT: 3 skipped tests without `DATABASE_URL`; advisory-lock dual-holder never runs in CI today — OPS gap for quality bar #2 proof automation. |
| **acceptance criterion** | A CI job (same or follow-on to WS-048) exports `DATABASE_URL`, migrates, runs full pytest including previously skipped DB tests; advisory-lock test executes (not skipped). |
| **commits 1–5** | 1. Add `integration` job or extend ci with DB env. 2. Migrate before pytest. 3. Confirm skip markers lift when URL set. 4. Fail job if any skip remains for DB-marked tests (optional strict mode). 5. Record proof snippet template in RELEASE_CHECKLIST. |
| **deps** | WS-048; may need CORE test markers — coordinate file ownership (`tests/` is CORE; OPS owns workflow only). |
| **risk** | Medium — file ownership: OPS must not rewrite CORE tests without lane sync; prefer env-only enablement. |

---

## WS-057 — Compose stack health + poller tick smoke

| Field | Content |
|---|---|
| **id** | WS-057 |
| **title** | docker-compose profile for app smoke with health probe |
| **why** | Compose DB alone is not enough for release smoke; OPS wants `up` → migrate → tick/bot health without documenting ad-hoc terminals. |
| **acceptance criterion** | Documented profile or `make smoke`: Postgres healthy, migrate applied, process serving `/health`, `scripts/probe_health.py` exits 0 (tick may use `--force` and mocked CSE **only if** already supported — else probe after `bot`/`both` start with DB-only degraded allowed as documented). |
| **commits 1–5** | 1. Extend compose with optional `health` depends_on condition. 2. Add smoke script orchestrating migrate + start + probe. 3. Document degraded vs ok expectations. 4. Wire `make smoke` / `just smoke`. 5. Note cse.lk rate-limit: smoke must not hammer API (single tick max). |
| **deps** | WS-042, WS-053, WS-054. |
| **risk** | Medium — live CSE calls in smoke; prefer force-tick once with polite timeout or health-only if tick needs network. |

---

## WS-058 — Action pinning and Dependabot for OPS surface

| Field | Content |
|---|---|
| **id** | WS-058 |
| **title** | Pin GitHub Actions SHAs/tags + Dependabot for Actions |
| **why** | Unpinned `actions/checkout@v4` floating tags are supply-chain risk for the OPS lane’s own CI. |
| **acceptance criterion** | CI workflows use version tags or commit SHAs consistently; `.github/dependabot.yml` watches `github-actions` (and optionally pip) on a weekly schedule; docs note review duty for Action bumps. |
| **commits 1–5** | 1. Pin actions in ci.yml. 2. Add dependabot.yml for github-actions. 3. Optional pip ecosystem Dependabot with open-PR limit. 4. Document in SECRETS or CONTRIBUTING. 5. Add checklist item “review Dependabot CI PRs”. |
| **deps** | WS-041. |
| **risk** | Low — Dependabot noise; set `open-pull-requests-limit`. |

---

## WS-059 — Structured CI job summaries / failure taxonomy

| Field | Content |
|---|---|
| **id** | WS-059 |
| **title** | CI annotations and failure taxonomy for agents |
| **why** | Agentic factory needs fast triage: lint vs types vs unit vs migrate vs secrets — not one opaque red X. |
| **acceptance criterion** | CI uses separate steps/jobs named `ruff`, `mypy`, `pytest`, `migrate`, `secrets-scan`; `$GITHUB_STEP_SUMMARY` lists which gate failed; docs/ops/CI.md maps exit meanings. |
| **commits 1–5** | 1. Split monolithic run into named steps if not already. 2. Write step summaries on failure. 3. Add docs/ops/CI.md. 4. Link from CONTRIBUTING. 5. Align job names with RELEASE_CHECKLIST. |
| **deps** | WS-041, WS-044, WS-048, WS-052. |
| **risk** | Low. |

---

## WS-060 — OPS runbook + one-command DX verification matrix

| Field | Content |
|---|---|
| **id** | WS-060 |
| **title** | OPS runbook consolidating health, logs, metrics, make/just |
| **why** | Wave1 OPS ends with a single operator doc so implementation epochs can check “ops bar” without rediscovering README fragments. |
| **acceptance criterion** | `docs/ops/RUNBOOK.md` covers: local up (make/just), migrate/seed, bot/poller/both, health probe, log field pointer, latency metric export, CI proof commands, secret handling, release checklist link; includes a verification matrix (command → expected). |
| **commits 1–5** | 1. Create docs/ops/ structure index. 2. Write RUNBOOK sections from WS-046/047/053/054. 3. Add verification matrix table. 4. Link RUNBOOK from README + COMMIT_FACTORY doc index. 5. Mark WAVE1_OPS planning complete in workstreams INDEX when that file exists. |
| **deps** | WS-045…WS-055 ideally drafted; can land docs stubs first. |
| **risk** | Low — doc drift; treat RUNBOOK as OPS-owned source of truth. |

---

## Dependency graph (planning)

```
WS-041 CI ──┬── WS-044 coverage
            ├── WS-048 migrate@CI ── WS-056 DB pytest
            ├── WS-049 pre-commit
            ├── WS-052 secrets scan
            ├── WS-058 action pins
            └── WS-059 CI taxonomy
WS-042 compose ── WS-043 seed
                 └── WS-054 make ── WS-055 just
                                   └── WS-057 smoke
WS-046 log fields ── WS-047 latency export
WS-050 CONTRIBUTING ── WS-051 PR templates
WS-053 health probe ── (make/smoke)
WS-045 release checklist ← many
WS-060 runbook ← consolidates
```

## Suggested implementation order (≤8 concurrent, disjoint files)

1. WS-041, WS-042, WS-046, WS-050 (parallel)  
2. WS-044, WS-048, WS-043, WS-053  
3. WS-049, WS-051, WS-052, WS-054  
4. WS-047, WS-055, WS-056, WS-045  
5. WS-057, WS-058, WS-059, WS-060  

## Out of scope for this wave file

- CORE alert/rule fixes, DASH `web/` features, Ceyfi merge, payment/portfolio/screener/TA.
