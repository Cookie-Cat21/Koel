# CR_OPS — Epoch 1 code review (CI / compose / Make / env)

**Reviewer role:** OPS CR (accurate only; no speculative rewrites)  
**Scope:** `.github/workflows/ci.yml`, `docker-compose.yml`, `Makefile`, `.env.example`  
**Cross-checks:** `pyproject.toml` (tool/runtime contract), `WAVE1_OPS.md` WS-041/042/048/054/056, `EPOCH1_PASS.md` claims  
**Date:** 2026-07-11  
**Ship commit:** `03beeff` (`ops(ci): add Actions workflow, compose Postgres, Makefile` — closes WS-041, WS-042, WS-048)

---

## Verdict

**CONDITIONAL PASS — scaffolding is real and mostly correct; fix Python-version drift and Make/DX naming before treating OPS Epoch 1 as “boring.”**

CI has a unit job (ruff/mypy/pytest with DB forced off) and an integration job (Postgres 16 service → migrate → pytest). Compose healthcheck and `.env.example` `DATABASE_URL` match `koel`/`koel`/`koel`. No production secret is committed in these four files.

Residual risk is contract drift and proof softness: CI runs **3.12** while `pyproject.toml` tools target **3.11**; Make ships `up-db`/`down-db` with no `help` (not the thin `up`/`down` surface R1/WS-054 named); WS-042’s README “Local Postgres” blurb was never landed though the WS is marked closed; integration does not assert that DB skips actually lifted.

---

## Ranked findings

### P1 — Fix before calling Epoch 1 OPS “closed”

| # | Finding | Evidence | Why it matters |
|---|---|---|---|
| 1 | **CI Python 3.12 ≠ project typecheck/lint target 3.11** | `ci.yml` both jobs: `python-version: "3.12"`. `pyproject.toml`: `requires-python = ">=3.11"`, `[tool.mypy] python_version = "3.11"`, `[tool.ruff] target-version = "py311"`. WAVE1_OPS WS-041 commit plan: setup-python **3.11**. | Runtime under test and static-analysis dialect diverge. Green CI does not prove the declared 3.11 contract. Pin one version (prefer **3.11** to match WAVE + mypy/ruff) or raise tool targets to 3.12 in the same change. |
| 2 | **Integration job never proves DB tests ran** | `integration` sets `DATABASE_URL` and runs bare `pytest`. DB modules use import-time `skipif(not DATABASE_URL)` (`tests/test_advisory_lock.py`, `tests/test_poller_integration.py`). No markers, no `-m`, no “fail if skipped” gate (WS-056 optional strict mode). INDEX still lists **WS-056 = backlog** while EPOCH1_PASS folds “integration job” into WS-048. | If env wiring regresses, the job can stay green with the same 3 skips Stage A had. Advisory-lock automation is then a claim, not a gate. |
| 3 | **Makefile DX surface ≠ thin Make contract** | Actual `.PHONY`: `install lint typecheck test migrate up-db down-db`. No `help`. R1_OPS Pass-1 thin Make and WS-054 AC name `up` / `down` / `help` (WS-054 still backlog — this file is a partial side-ship in `03beeff`). | Agents/docs that say `make up && make migrate` will miss. Targets are not broken, but they are the wrong names for the agreed DX vocabulary. |
| 4 | **WS-042 closed without README Local Postgres blurb** | WAVE1_OPS WS-042 AC: compose up + matching `.env.example` **and** README subsection. `03beeff` touches only the four scoped files; current `README.md` has no compose/`5432`/`make` mention. `.env.example` alignment itself is fine. | False-close on WS-042. Contributors still lack the documented port-conflict / one-command path the wave required. |

### P2 — Real gaps / footguns (not blockers for “CI exists”)

| # | Finding | Evidence | Why it matters |
|---|---|---|---|
| 5 | **`make test` does not mirror CI unit isolation** | CI unit job forces `DATABASE_URL: ""` so DB tests skip. Makefile `test:` is bare `pytest`. Copying `.env.example` → `.env` makes `load_dotenv` (via `koel.migrate` import in DB tests) see a URL; `skipif` lifts; without `up-db`, those tests **fail** (connection refused), not skip. | Deterministic local footgun after the documented `cp .env.example .env` path. Not CI flake, but Make `test` is a worse unit entrypoint than the workflow. |
| 6 | **Compose healthcheck is correct but thin** | `docker-compose.yml`: `pg_isready -U koel -d koel`, interval 5s, timeout 5s, retries 10. Matches `POSTGRES_USER`/`POSTGRES_DB`. No `start_period`. | Credentials/command are right — not a bug. Missing `start_period` only means early `pg_isready` failures consume retries; usually fine for `postgres:16`, slightly less forgiving on slow hosts. |
| 7 | **`.env.example` omits several `Settings` knobs** | Example documents token, `DATABASE_URL`, CSE URL, poll/log/health/circuit. `koel/config.py` also reads `HTTP_TIMEOUT_SECONDS`, `MARKET_TZ`, `MARKET_OPEN`, `MARKET_CLOSE` (defaults exist). | Not secret leakage; incomplete operator surface. Fine for v1 if intentional; do not claim `.env.example` is the full settings catalog. |
| 8 | **Unit + integration both run the full suite** | Both jobs: `pytest` (pyproject `addopts` cov gate on `koel.rules`). Integration re-runs all unit tests after migrate. | Correctness OK; waste and longer flake surface. Prefer markers later (`not requires_db` vs full) — QUALITY WS-079 / OPS WS-056 territory. |
| 9 | **`on: push` + `on: pull_request` without branch filter** | Every push and every PR event runs both jobs (duplicate on branch-push PRs in-repo). | Noise/cost, not incorrect gates. |

### P3 — Checked clear / do not “fix” as bugs

| # | Check | Result |
|---|---|---|
| 10 | **Secret leakage in scoped files** | **None.** `TELEGRAM_BOT_TOKEN=` empty. `.gitignore` ignores `.env` / `.env.*` with `!.env.example`. Compose/CI/`DATABASE_URL` use ephemeral local password `koel` by design (WAVE WS-042). Do not treat that as a leaked production secret. |
| 11 | **Compose ↔ `.env.example` URL** | **Aligned:** `postgresql://koel:koel@localhost:5432/koel` ↔ user/password/db `koel`, port `5432:5432`, named volume `koel_pgdata` (not a bind mount — gitignore clause N/A). |
| 12 | **CI migrate entrypoint** | `python -m koel.migrate` is valid (`koel/migrate.py` `__main__`). Equivalent in effect to `python -m koel migrate` / Makefile `$(PYTHON) -m koel.migrate`. Not a functional defect. |
| 13 | **Unit job empty `DATABASE_URL`** | `DATABASE_URL: ""` → `.strip()` falsy → `skipif` holds. `load_dotenv` does not override an existing empty env var. Correct skip wiring. |
| 14 | **GHA Postgres health wait** | Service `options` `--health-cmd "pg_isready -U koel -d koel"` with retries — standard, matches compose. No evidence of a systematic ready-race in the workflow definition. |
| 15 | **Integration test isolation (flake)** | DB tests use distinct telegram IDs / symbols; CI Postgres is ephemeral per job. No sleep-based waits in the workflow. **No accurate flake bug found** in these four files beyond the soft “skips can still be green” proof gap (#2). |

---

## Check matrix (requested)

| Check | Verdict | Notes |
|---|---|---|
| CI correctness | **Mostly yes** | Two-job shape, migrate before DB pytest, ruff/mypy/pytest present. Gaps: Python 3.12 drift (#1), no skip-lift proof (#2), duplicate push/PR (#9). |
| Secret leakage | **Pass** | Empty bot token; local `koel` password only; `.env` gitignored. |
| Flaky integration | **No hard flake found** | Soft proof gap if skips return (#2); compose/CI healthchecks aligned (#6/#14). |
| Compose healthcheck | **Pass** | `pg_isready -U koel -d koel` correct; optional `start_period` only. |
| Makefile targets wrong | **Names/incomplete, not broken recipes** | `up-db`/`down-db` work; wrong vocabulary vs R1/WS-054; no `help`; `test` ≠ CI unit isolation (#3/#5). |
| pyproject mismatch | **Yes — version contract** | CI 3.12 vs mypy/ruff 3.11 / WAVE 3.11 (#1). Install extra `.[dev]` matches Makefile/CI. |

---

## What is already good (do not regress)

- Split unit vs integration jobs; unit explicitly clears `DATABASE_URL`.
- Integration: Postgres 16 + health-cmd + job-level `DATABASE_URL` + migrate step + pytest.
- Compose DB-only (no premature app service) matches R1_OPS cut list.
- `.env.example` keeps `TELEGRAM_BOT_TOKEN` blank.
- Make wraps the same tools CI uses (`ruff`, `mypy koel`, `pytest`, editable `.[dev]`).

---

## Recommended fixes (OPS-only, minimal)

1. Set CI `python-version: "3.11"` **or** bump `tool.mypy.python_version` + `tool.ruff.target-version` to 3.12 — one commit, one contract.
2. Alias Make targets: `up`/`down` → existing compose recipes; add `help`; keep `up-db` as alias if desired.
3. Integration proof: `pytest -rs` + fail if advisory/poller DB tests show SKIPPED, **or** land markers (`requires_db`) and run `-m requires_db` in the integration job (coordinate QUALITY WS-079; mark WS-056 done if this is the ship).
4. Finish WS-042: short README “Local Postgres” (`docker compose up -d`, URL, port conflict). Re-open or amend the close claim until then.
5. Optional: `make test-unit` with `DATABASE_URL=` to match CI unit; leave `make test` for full suite when DB is up.

---

## Claim hygiene

| Claim | Accurate? |
|---|---|
| WS-041 CI ruff/mypy/pytest | **Yes** (version pin wrong vs WAVE text) |
| WS-042 compose + `.env.example` | **Partial** — compose/env yes; README blurb **no** |
| WS-048 migrate on ephemeral Postgres | **Yes** |
| WS-048 “+ integration job” / WS-056 | **Job present**; INDEX still backlog; skip-lift **unenforced** |
| WS-054 Make one-command | **Not claimed**; file is incomplete relative to AC |

---

**Bottom line:** Ship is usable. Rank-1 debt is version contract + Make naming + honest WS-042/056 proof — not secret leaks or a broken `pg_isready`.
