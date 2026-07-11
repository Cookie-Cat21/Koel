# Epoch 1 — Integration code review (`CR_INTEGRATION`)

| Field | Value |
|---|---|
| **Reviewer role** | Integration (cross-module / fleet / tooling) |
| **Branch** | `cursor/epoch1-execute-cb19` |
| **Reviewed HEAD** | `2751414125c300eb2d8e431430202026a10e7ff1` (last code commit; tip may include later `docs(review):` only) |
| **Epoch window** | `03beeff` … `2751414` (ops → core/quality/dash → adversarial → fixup) |
| **Scope** | Agent edit overlap · import/API mismatches · poller↔storage contradictions · pyproject vs CI vs Makefile |
| **Method** | `git log`/`git show` on Epoch commits + read call sites. No invented endpoints. Rank by blast radius if modules are wired as shipped. |

## Verdict

**Integration is not clean enough to treat Epoch 1 as converge-ready.** Runtime imports between `poller` / `storage` / `rules` / `bot` / `notify` line up (no missing symbols). The live risks are **semantic drift** (frozen dash contract vs post-fixup `create_alert_rule`), **notify×advisory-lock coupling** (WS-083 only partially closed), and **watchlist-gated evaluation** that can strand active rules. Fleet history is linear and mostly file-partitioned — no git conflict stomps — but scorecard/docs were soft-stomped.

---

## Ranking key

| Rank | Meaning |
|---|---|
| **HIGH** | Cross-module contract break that will ship the wrong behavior if another lane follows the frozen doc |
| **MEDIUM** | Real coupling defect under concurrency, crash, or load |
| **LOW** | Tooling/docs drift or dead surface; limited runtime blast radius |
| **PASS** | Checked; no finding worth a ticket |

---

## Ranked findings

### 1. HIGH — Frozen `API_CONTRACT_V1` still mandates deactivate-then-insert; storage no longer does

**Where:** `docs/factory/API_CONTRACT_V1.md` (WS-024 / `4b5ef5b`) vs `chime/storage.py` `create_alert_rule` (`2751414`)

**Evidence:**

- Contract global parity + `POST /api/v1/alerts`: *“deactivate any identical active rule then insert”* / *“duplicate active rules → deactivate-then-insert (not hard 409)”* / *“soft-replace duplicates”*.
- HEAD storage: fetch active twin → return it; else `INSERT`; on `UniqueViolation` rollback and return survivor. Explicitly **avoids** deactivate-then-insert (WS-009 TOCTOU fix after adversarial refute).

**Integration failure:** A DASH implementer obeying the frozen contract reintroduces the race WS-009 just closed (parallel create deactivates the id already returned to the user). CORE and DASH lanes disagree on the single mutation spine the contract claims to mirror.

**Not excused by:** `CR_DASH_DOCS` still treating “storage soft-replace” as aligned — that was true at contract freeze (`4b5ef5b`), false after `2751414`.

---

### 2. MEDIUM — `notify.send_message` still couples Telegram flood sleep to poller advisory-lock hold

**Where:** `chime/notify.py`, `chime/poller.py` `run_once` / `_retry_unsent`, `chime/storage.py` `try_advisory_lock` / `advisory_unlock`

**Evidence:**

- Lock acquired at start of `run_once`; unlocked only in `finally` after prices + disclosures + `_retry_unsent`.
- `send_message` on `RetryAfter`: `asyncio.sleep(min(retry_after, 30) + 0.5)` then one retry. Cap landed in `2751414`; **no** global backoff, send queue, or unsent ceiling.
- `_retry_unsent` walks up to `unsent_alerts(limit=50)` sequentially through the same `send` path while the lock is held.

**Concrete failure:** K unsent/claimed sends each getting `RetryAfter≥30` → wall time ≈ K×30.5s under lock → dual-poller `lock_held_skip`, delayed crosses, retry pile-up next tick. Cap bounds *per call*, not *per tick*.

**Test gap:** `tests/test_notify_retry.py` proves one-message cap; does not assert tick lock hold under burst≥20. Matches adversarial HIGH on WS-083; 30s sleep alone does not meet WAVE1 “global backoff / bound unsent” intent.

---

### 3. MEDIUM — Poller evaluates only `watched_symbols()`; active rules can become dead storage

**Where:** `chime/poller.py` `_poll_prices` / `_poll_disclosures`; `chime/bot.py` `cmd_unwatch`; `chime/storage.py` `watched_symbols` / `active_rules_for_symbols` / `remove_watch` / `deactivate_rules_for_symbol`

**Evidence:**

- Price and disclosure legs load symbols from `watchlist_items` (`watched_symbols`), then `active_rules_for_symbols(those)`.
- `cmd_unwatch` awaits `remove_watch` then `deactivate_rules_for_symbol` on **separate** pool connections (not one transaction).

**Concrete failure:** Crash / kill between the two awaits → watch row gone, `active=true` rules remain. Storage still lists them in `list_alerts`; poller never sees the symbol → **alerts never fire**. Inverse (deactivate without remove) only wastes tradeSummary filtering, not silence.

**Related (by design, still a coupling footgun):** Orphan active rules for symbols absent from *any* watchlist are invisible to the poller forever. Disclosure scoping (WS-020) correctly skips CSE for price-only rules; it does not compensate for watchlist/rule split brain.

---

### 4. MEDIUM — Fleet soft-stomp: pass scorecard vs adversarial refute left contradictory

**Where:** `docs/factory/passes/EPOCH1_PASS.md`, `docs/factory/passes/EPOCH1_ADVERSARIAL.md`; commits `3ad70f7` → `98060e1` → `2751414`

**Evidence:**

- Pass (`3ad70f7`) claimed `16/16` at verify SHA `4b5ef5b`.
- Adversarial (`98060e1`) reviewed that claim → **DO NOT CONVERGE_EPOCH1**; reopened WS-083 / WS-009 / WS-068 with concrete failure scenarios.
- Fixup (`2751414`) patched code for those three and **rewrote** `EPOCH1_PASS.md` to `16/16` again; left `EPOCH1_ADVERSARIAL.md` verdict and “required before CONVERGE” list unchanged (still refutes pre-fixup HEAD).

**Integration risk:** Downstream agents reading only PASS will converge; agents reading ADVERSARIAL will reopen. Same-pass refute→fix is intended by factory rules; leaving the refute document stale is scorecard stomping, not proof.

**Git stomps (narrower claim):** Epoch commits are **linear** (`03beeff`…`2751414`), landed ~12:36–12:40 UTC with disjoint file sets (ops / adapter+rules / tests / poller+storage / dash docs). **No merge-conflict overwrites.** Soft stomps only: `storage.py` incomplete WS-009 then rewrite; `EPOCH1_PASS.md` twice; DASH contract frozen then CORE semantics changed without contract patch (finding #1).

---

### 5. LOW — CI Python 3.12 vs project/tooling 3.11 contract

**Where:** `.github/workflows/ci.yml` (`python-version: "3.12"` both jobs); `pyproject.toml` `requires-python = ">=3.11"`, ruff `target-version = "py311"`, mypy `python_version = "3.11"`; `WAVE1_OPS` WS-041 commits specified setup-python **3.11**; `R1_OPS` warned against “helpfully” adding 3.12.

**Impact:** CI runtime ≠ typecheck target. Compatible today (`>=3.11` allows 3.12) but diverges from the Epoch OPS acceptance text and invites 3.12-only syntax that mypy-on-3.11 will not catch locally the same way. Already noted as MINOR in adversarial; still open drift.

---

### 6. LOW — Verify / Makefile / CI ruff invocation drift

| Surface | Command |
|---|---|
| Makefile + CI | `ruff check .` |
| `EPOCH1_PASS.md` verify block | `ruff check chime tests` |
| mypy / pytest | Aligned: `mypy chime`, `pytest` (pyproject `addopts` cov gate) |

**Impact:** Proof snippet ≠ what CI/Make run. Unlikely to hide failures today (both cover `chime`+`tests`); trains agents to copy the weaker scoped command.

**Also:** README documents `pip install` + `python -m chime …` but not `make` / `docker compose` added in `03beeff`. Compose credentials match `.env.example` and CI (`chime`/`chime`/`chime`) — **PASS** on that sub-check. Migrate entrypoints: Makefile/CI `python -m chime.migrate`; README `python -m chime migrate` — both valid; not a break.

---

### 7. LOW — Dead / unused surfaces adjacent to the poller spine

| Symbol | Status |
|---|---|
| `Storage.latest_snapshot` | No callers outside `storage.py` |
| `domain.as_dict` | Defined, never imported |
| `Storage.connection` | Public CM; no external callers (pool used directly) |
| `previous_snapshot` | Used by `get_previous_state` — **not** dead |

Not contradictory behavior by themselves; noise for agents grepping “the” snapshot API.

---

### 8. LOW — `bot`-only process: health server never updated; README overclaims

**Where:** `chime/__main__.py` `_run_bot`; `README.md` health section

**Evidence:** `_run_bot` starts `HealthState` + HTTP server but never calls `health.update`. Defaults stay `ok=True` with empty details. README: when `bot`, `poller`, or `both` is running, `/health` returns “liveness / last-tick status”. Tick fields only exist for `poller`/`both`.

Ops false confidence if someone runs `bot` alone behind a probe expecting poller honesty.

---

## Checks that PASS (accurate non-findings)

| Check | Result |
|---|---|
| Import / method wiring poller→storage→rules→notify | Call signatures match (`claim_alert`, `insert_disclosure_if_new`, `get_previous_state`, `set_rule_armed`, `unsent_alerts`, etc.). No missing attributes at HEAD. |
| CSEClient ctor defaults vs `tick` path | `tick` uses `CSEClient(base_url=…)` only; defaults match Settings defaults for circuit/timeout. |
| Disclosure `snapshot_id=None` → `alert_log` | Schema allows NULL `snapshot_id`; claim path OK. |
| Unit CI `DATABASE_URL: ""` | DB tests use `.strip()` skipif; dotenv does not override set env → skips work. |
| Compose ↔ CI DB URL | Same user/db/password/port as `.env.example`. |
| Concurrent agent **file** stomps | Linear history + lane file partitions; no lost hunks from merge. |

---

## Epoch commit map (for stomping audit)

| Commit | ~UTC | Lane signal | Touched runtime |
|---|---|---|---|
| `03beeff` | 12:36:24 | OPS WS-041/042/048 | CI, compose, Makefile, `.env.example` |
| `2c2e18f` | 12:36:44 | CORE WS-001/002/017 | `adapters/cse.py`, `rules.py` + tests |
| `dd21ba9` | 12:37:05 | QUALITY WS-066/068/077/083 | tests only |
| `8e39270` | 12:37:13 | CORE WS-020/012/009 | `__main__`, `poller`, `storage` + resilience tests |
| `4b5ef5b` | 12:37:20 | DASH WS-023/024 | ADR + `API_CONTRACT_V1` + `DASH_IA` |
| `3ad70f7` | 12:38:12 | PASS docs | `EPOCH1_PASS.md` |
| `98060e1` | 12:40:00 | ADV review | `EPOCH1_ADVERSARIAL.md` |
| `2751414` | 12:40:52 | CORE fixup WS-009/068/083 | `storage`, `bot`, `notify` + tests + PASS rewrite |

---

## Recommended fixes (integration-only; not implemented here)

1. Patch `API_CONTRACT_V1` (+ dash soft-replace wording) to **idempotent return-existing** matching `create_alert_rule`; or revert storage to match contract (do not leave both).
2. Move Telegram send/retry **off** the advisory-lock critical section, or add global backoff + hard unsent budget; add burst probe under lock.
3. Unwatch: one DB transaction for remove_watch + deactivate; or poller also consider symbols from `active_rules`.
4. Reconcile `EPOCH1_ADVERSARIAL.md` with post-`2751414` reality (update verdict / reopen residual WS-083) and re-bind PASS verify SHA to post-fix HEAD.
5. Pin CI to 3.11 **or** bump mypy/ruff target + WAVE1 note to 3.12; make PASS proof commands match Makefile/CI.

Until (1)–(4): **do not treat Epoch 1 integration as closed.**
