# R1 — Adversarial review: factory process docs

**Scope:** `COMMIT_FACTORY.md`, `METRICS.md`, `ORCHESTRATOR_PROMPTS.md` only.  
**Verdict:** Gates are directionally right but still farmable via severity laundering, verify theater, ownership races, and minor-fix infinite loops. Patch language below; do not add more process pages.

---

## 1. Commit farming that survives the ban list

| Attack | Why it works today | Patch |
|---|---|---|
| **Severity laundering** | Convergence stops only on findings *above* minor. Agents reopen the same issue as `minor` forever, or bump/down-grade to keep the lane alive. | Treat “same root cause reopened” as major; cap consecutive minor-only passes (see §4). |
| **AC theater** | “Acceptance criterion written before coding” is unchecked; agents write AC after the fact in the report. | Require AC in plan file *before* implementer spawn; report must cite plan path + line. |
| **Verify theater** | “Proof” = paste of green output; no requirement that commands ran on *this* diff / SHA. | Bind proof to `git rev-parse HEAD` + command + exit code in report. |
| **Concern splitting via tags** | `feat` + `test` + `fix` for one logical change still score as 3 proper commits if each has an AC. | One concern → one commit unless AC *explicitly* demands a separate proof commit (METRICS already says ≤3; enforce “default 1”). |
| **Docs / OPS padding** | `docs` that “unblock a gate” and `ops` DX nits are subjective; factory docs edits score. | Score `docs`/`ops` only if they close a named quality-bar blocker id, not “clarify wording.” |
| **Joint implementer+test commit escape** | Test-writer may “prefer one commit” *or* separate — agents choose separate for count. | Orchestrator assigns commit mode up front: `joint` \| `impl_only` \| `test_only` (exactly one). |
| **Ban list is examples, not detectors** | “Manufacturing audit findings” is forbidden but AUDIT still ranks whatever agents invent. | Cap new findings per pass (e.g. ≤8); new finding must map to a quality bar + file path that existed pre-pass. |

---

## 2. Orchestrator prompt gaps

| Gap | Risk | Fix |
|---|---|---|
| **No wave ownership ledger** | Shared constitution says “disjoint files” but Orchestrator does not emit a locked `FILE_LIST` matrix before spawn. Implementer template has `{{FILE_LIST}}`; orchestrator never mandates filling it for *all* agents including Test-writer and Dash. | Orchestrator step 3 must write `OWNED_FILES` table (agent → paths) into the plan; cancel on overlap. |
| **Verify not in Implementer wait-gate** | Orchestrator “runs verify yourself” *after* agents may have already committed. Race: bad commit lands, then rejected “claim” but SHA remains. | Rule: agents push patches uncommitted *or* commits only after orchestrator verify green; no claim until verify-on-SHA. |
| **Cross-lane API surface** | DASH owns “dash API”; CORE owns `koel/`. Concurrent CORE+DASH waves can both edit the same route/handler. | Explicit ownership: dash API paths listed in plan; CORE may not touch them in same wave (and vice versa). |
| **No conflict detector** | “If conflicts → cancel” is aspirational; no `git merge-tree` / path-intersection check. | Before merge to factory branch: fail wave if any two agents’ changed paths intersect. |
| **Adversarial spawn after “accepted”** | Reviewer sees claimed commits; if refute drops *claim* but not commit, history still farms. | REFUTE → revert or fixup same pass before scorecard; unscored commits must not remain on factory tip. |
| **Researcher / planning commit ambiguity** | Planning says docs-only “must still be a proper commit”; METRICS says planning/METRICS edits often score 0. Contradicts. | Planning commits: score 0 unless human-approved constitution amend. |
| **Missing STOP state handoff** | Convergence in shared block; Orchestrator does not require reading prior pass’s stop signal / residual minors list. | Step 1: load last 2 scorecards; if STOP armed, exit without AUDIT. |

---

## 3. Metrics that can be gamed — fix proposals

| Metric / rule | Game | Fix |
|---|---|---|
| `proper_commits(pass)` | Maximize small accepted commits | Add **pass yield cap**: score `min(raw_proper, findings_closed_clusters)` — cannot outrun closed clusters. |
| Pass yield `proper / Done passes` | One mega-pass with many micros still looks “healthy” | Report **median commits per cluster** (target ≈1); flag >1.5. |
| Refute rate | Rubber-stamp → low refute = “healthy”; or invent refutes then same-pass fix = busywork | Count **net refute-without-fix** and **same-pass-fix rate** separately; neither is a vanity target. |
| Backlog burn | Close WS by marking `done` without product change; cluster merge shrinks backlog without commits | Require each closed cluster → ≥1 scored commit SHA or explicit `wontfix` + human. |
| Quality bar “improved” | Checkbox without proof path | Status `improved` invalid unless proof column cites test name or metric delta. |
| `docs` / `ops` Yes | Gate-unblock stories | Require `closes: BAR-#` or `closes: WS-###` trailer to score. |
| Rolling 30d proper rate | Incentive to keep shipping minors | Pair with **convergence obedience**: lanes past STOP that keep committing score 0. |

---

## 4. Convergence edge cases (infinite minor-fix churn)

Current rule: *2 consecutive passes with 0 findings **above** minor → STOP.*

| Edge case | What happens | Patch |
|---|---|---|
| Endless `minor` queue | Lane never stops; polish forever | **STOP also if** 2 consecutive Done passes have *only* minor findings (even if minors remain), **or** after N minor-only passes (propose **N=2** same as today, but include “minors-only” not just “zero > minor”). |
| Reopen-as-minor | Finding closed as fixed, re-audited as new minor | Dedup by `(bar, path, symptom hash)`; reopen within 3 passes ⇒ escalate to major or `wontfix`. |
| Rotate lanes | CORE stops; work relaunders under OPS/DASH docs | STOP is per **epoch**, not only per lane label; cross-lane duplicate findings don’t reset. |
| “Residual risk ≤ minor” ACCEPT | Reviewer parks real bugs as minor follow-ups | ACCEPT may list follow-ups; they do **not** auto-enter next AUDIT unless severity ≥ major or human promotes. |
| MAX_PASSES=100 aspiration | Agents treat ceiling as runway | Orchestrator: remaining passes irrelevant once STOP fires; delete “fill toward 100” language wherever implied. |

**Proposed convergence (single sentence):** STOP when two consecutive Done passes add no finding with severity ≥ major **and** do not close a pre-listed major/blocker — minors alone never extend the epoch.

---

## 5. Concrete edits (max 10) — quote → replacement

### E1 — `COMMIT_FACTORY.md` §0 Convergence
> Convergence: two consecutive passes with zero findings above **minor** → STOP that lane.

→ Convergence: two consecutive Done passes with no finding ≥ **major** and no closure of a pre-listed blocker/major → STOP that lane/epoch. Minors alone do not extend. Reopened same `(bar,path,symptom)` within 3 passes escalates to major or `wontfix`.

### E2 — `COMMIT_FACTORY.md` Banned
> - Manufacturing audit findings to fill `MAX_PASSES`

→ - Manufacturing or severity-laundering findings to fill `MAX_PASSES` / avoid STOP  
→ - Scoring more than one commit per concern unless the pass plan pre-declared a separate proof commit  
→ - Leaving refuted commits on the factory tip (revert or fixup before score)

### E3 — `COMMIT_FACTORY.md` §1 proper commit #3
> **Proof** attached in the pass report: command output for `ruff`, `mypy`, `pytest` (and dash smoke when relevant).

→ **Proof** attached in the pass report: `git` SHA + full command + exit code + excerpt for `ruff`, `mypy`, `pytest` (and dash smoke when relevant), run on that SHA after the change.

### E4 — `METRICS.md` Formula
> `factory_score(pass)  = proper_commits(pass)   # not raw git commit count`

→ `factory_score(pass) = min(proper_commits(pass), clusters_closed(pass))`  
→ Commits on a lane after STOP fired score 0 until human reopens the epoch.

### E5 — `METRICS.md` docs/ops scoring
> `| docs | **Only if** | Docs unblock a gate or correct a constitution/fence error — not narrative thrash |`

→ `| docs | **Only if** | Commit trailer `closes: BAR-#` or `closes: WS-###` for a real gate/fence error — not narrative thrash |`  
(same trailer rule for `ops` nits that aren’t BAR-5.)

### E6 — `METRICS.md` Lane epoch STOP
> **Lane epoch STOP:** two consecutive Done passes with zero findings above **minor**.

→ **Lane epoch STOP:** two consecutive Done passes with no ≥ major findings **and** no blocker/major closures — equivalent to “minors-only or empty.” Human required to reopen.

### E7 — `ORCHESTRATOR_PROMPTS.md` Shared CONVERGENCE
> CONVERGENCE: If this lane had 2 consecutive passes with zero findings above minor → STOP. Do not invent work.

→ CONVERGENCE: If last 2 Done passes were minors-only (no ≥ major, no blocker/major closed) → STOP epoch. Do not invent or relaunder work. Post-STOP commits score 0.

### E8 — `ORCHESTRATOR_PROMPTS.md` Orchestrator PLAN step
> 3. PLAN: pick ≤8 non-overlapping work items (disjoint file ownership). Write acceptance criteria per item. Assign Implementer / Test-writer / (DASH→Dashboard implementer) / Researcher only if OSS needed. Cap spawn ≤8 (hard 16).

→ 3. PLAN: pick ≤8 items. Write AC **in the plan file first**. Emit `OWNED_FILES` table (agent→paths) including Test-writer and Dash API paths; cancel on overlap. Pre-assign commit mode per item: `joint` \| `impl_only` \| `test_only`. Cap spawn ≤8 (hard 16). Cap **new** audit findings this pass at 8; each must cite pre-existing path + quality bar.

### E9 — `ORCHESTRATOR_PROMPTS.md` Orchestrator VERIFY/REVIEW
> 5. VERIFY: run the verify commands yourself (plus dash smoke if DASH). Reject any commit without proof.  
> 6. Spawn Adversarial reviewer on each accepted change. Refuted → fix same pass or drop the commit claim.

→ 5. VERIFY on the wave SHA (plus dash smoke if DASH). No score without SHA-bound proof. Path-intersect across agents → fail wave.  
→ 6. Adversarial review each change. REFUTE → fixup or **revert** same pass before scorecard (drop claim alone is insufficient).

### E10 — `ORCHESTRATOR_PROMPTS.md` Implementer commit step
> 4. One proper commit: subject states the concern; body notes acceptance criterion + how verified.

→ 4. Commit only in the mode the orchestrator assigned. Subject = one concern; body cites plan AC path, verify commands, SHA. Do not invent a sibling `test`/`fix` commit for count.

---

## Residual (out of edit budget)

- Align planning-wave “proper docs commit” with METRICS score-0 for meta docs (E5 covers scoring; prompts still imply planning commits are “proper”).  
- Add machine-checkable ownership via a tiny `OWNED_FILES` manifest artifact — process text alone will regress under pressure.
