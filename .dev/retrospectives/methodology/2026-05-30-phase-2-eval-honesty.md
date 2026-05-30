# Methodology retrospective — phase-2-eval-honesty

## 1. Task identifier

**Task:** phase-2-eval-honesty (MVP eval honesty — retrieval YAMLs, stub removal, CI label, slow replay)  
**Date:** 2026-05-25 (context map) · execution/amendment 2026-05-30  
**Plan versions:** v1.0 → v1.1 (§8 on disk, pre-commit) → v1.2 (audit-driven amendment T5–T7)  
**Skills:** orchestrator-planning v0.6, pre-plan-exploration v0.2, executor-subtask-execution, auditor-review  
**One line:** Make five medium-tier retrieval goldens pass (Option A synthetic context), remove `requires_multi_hop` always-pass stub, rename misleading CI step label, add one slow-tier replay case; audit, then wire unit tests into CI and close plan artifacts.

---

## 2. Plan vs reality

### DAG vs execution

- **Planned (original):** `{T1, T2, T3, T4}` parallel — zero file overlap.
- **Actual (original):** Four separate commits in one session, order T3 → T1 → T2 → T4 (`ee55260`, `aed77d1`, `787d413`, `3a60717`). Not parallel agents, but disjoint file sets — no conflicts.
- **Planned (amendment):** `{T5, T6}` parallel → T7 sequential.
- **Actual (amendment):** T5 → T6 → T7 (`678aaea`, `63d65a2`, `e3036a3`), then follow-up `42d8cd2` (re-audit §15 + amendment packets + `uv.lock`).
- **Unsafe parallelization:** None observed; original parallel group was safe.
- **Deviation:** T7 produced **multiple dangling commits** (`ab594b9`, `26b05116` — not on branch ancestry) before `e3036a3` landed. §8.1 still cites orphaned `26b05116` at current `HEAD` (`42d8cd2`).

### Contracts at implementation surface

| §2 surface | Enforced in code + test? | Notes |
|------------|-------------------------|-------|
| `requires_multi_hop` declarative only | Yes | `test_run_retrieval_check_requires_multi_hop_does_not_affect_outcome`; stub grep-confirmed removed |
| Medium retrieval Option A (q1–q5) | Yes (pass path) | `--golden-tier=medium` green; **no negative** for wrong context (F-06 deferred) |
| `ReplayFixture` + committed JSON | Yes (golden slow) | q6 E2E via `test_goldens.py --golden-tier=slow` |
| Replay unit round-trip symbol | **Partial until T6** | Shipped `test_run_replay_check_passes_with_inline_fixture`; uses **inline mock**, not committed JSON (F-05 deferred) |
| CI gate for `test_runner_unit.py` | **Hollow T2→T5** | T2 added file; PR CI ran only `test_goldens.py --golden-tier=fast` until audit F-03 → T5 |
| Decision log path | Yes | `.dev/decision-logs/T2-requires-multi-hop.md` at HEAD |
| Naming (q6, fixture, unit file) | Yes | Manifest coverage passes |

**Hollow-contract window:** From T2 commit through audit at `3a60717`, §2 Tests implied regression coverage for stub removal but CI did not run `test_runner_unit.py`. Re-introducing `multi_hop_declared` would not fail medium/slow goldens — only local unit tests would catch it.

### §2 / decision-log narrative vs later subtasks

- **Original §2 Typed-surface bullet** named `test_run_replay_check_with_fixture`; T2 shipped `test_run_replay_check_passes_with_inline_fixture` — drift **repaired in T6 §2 Amendment**, not by renaming tests (correct escalation path per T6 kill criterion b).
- **T2 decision log** header updated to plan v1.2 in T6; rationale remained accurate; no stale post-amendment prose.
- **Original §§0–6 §2 rows** left read-only; v1.2 §2 Amendment *Landed:* rows supersede — same pattern as phase 1; requires auditor to read amendment block.
- **Plan §8.1 closure SHA** narrates `26b05116` while branch tip is `e3036a3` / `42d8cd2` — **not repaired** after re-audit F-11 condition; context-map *Post-execution* same stale pointer.

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T3 | trivial | OK — single YAML label edit |
| T1, T4 | standard | OK — YAML/fixture/manifest with real exit tests |
| T2 | architectural | OK — decision log + stub removal + new test file |
| T5, T6, T7 | standard | OK — CI/doc/closure; T5 arguably should have been **in original plan** given T2 regression intent |
| T7 | standard | **Under-disciplined execution** — multiple orphaned closure commits; SHA pointer still wrong at `HEAD` |

### Closure vs committed reality

- **Substantive code closure:** `3a60717` (T4) — all T1–T4 artifacts at HEAD; 38 tests pass (verified 2026-05-30).
- **First audit:** `3a60717`, working tree **dirty** — plan v1.1 + §8 on disk but not committed (`F-01`, `F-07`). Same failure mode as mvp-phase1 F-07.
- **Amendment closure commit on branch:** `e3036a3` (T7 — plan §8 + audit rev. 1 committed).
- **Post-re-audit commit:** `42d8cd2` — audit §15 re-audit, packets T5–T7, unrelated `uv.lock` churn.
- **§8.1 Tree SHA:** Records `26b05116` — **dangling commit**, not ancestor of `HEAD`; `git show 26b05116:<path>` works but pointer is archival fiction → **F-11 open**.
- **§8.2 artifacts at `42d8cd2`:** Plan, audit, decision log, code, CI, CHANGELOG present; amendment packets now committed in `42d8cd2` (were untracked at re-audit time).
- **First audit** ran on committed T1–T4 at clean `HEAD` but **dirty** for plan §8 — auditor correctly flagged F-07.
- **Re-audit:** `pass-with-conditions` at `e3036a3`; condition F-11 **not closed** in `42d8cd2`.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Count: 0** formal HALTs recorded in decision logs, changelogs, or commit messages.

| Situation | HALT? | Assessment |
|-----------|-------|------------|
| T2 kill criterion 1 (`multi_hop_declared` grep) | No | Correct — grep passed; stub removed |
| T4 kill criteria (dispatch, fixture fields, manifest) | No | Correct — golden slow green first pass |
| T2 ships unit file without CI wiring | No | **Should have escalated or HALT-shaped gap** — plan §2 Tests binding did not explicitly require CI, but T2 scope/rationale implied regression gate; audit had to find F-03 |
| T7 §8 written before commit (rev 1 audit) | No | **Process gap** — same as phase 1; F-01/F-07 |
| T7 closure SHA thrashing (`ab594b9` → `26b05116` → `e3036a3`) | No | **Improvised** — amend/reset without updating §8.1 to match landed `HEAD` |
| T6 kill (b) test rename vs plan reconciliation | Not triggered | Correct — plan *Landed:* preferred over rename |

**HALT-shaped improvisation (no escalation):**

- **CI gap (F-03):** T2 added regression-critical unit tests; executor did not wire CI or document explicit deferral — green local tests treated as sufficient until audit.
- **§8 handoff before commit:** Plan marked Complete on disk while `git show HEAD:plan.md` still v1.0 — handoff narrative ahead of committed reality.
- **F-11:** Re-audit named condition; `42d8cd2` fixed packets/re-audit commit but **not** §8.1 SHA alignment — condition treated as optional hygiene.

### Amendment cycles

- **One amendment wave:** v1.2 extension → T5 (CI) + T6 (§2 Amendment) → T7 (closure + audit commit); post-re-audit `42d8cd2`.
- **Scope:** Right-sized — no revert of T1–T4; no real `requires_multi_hop` validator; F-05/F-06/F-08 explicitly deferred.
- **Closure:** Re-audit **pass-with-conditions** on first amendment pass for blockers F-01/F-03; **one residual condition (F-11) still open** at `HEAD`.
- **Amendment packets:** T5–T7.md emitted in plan §6 extension but **not committed until after re-audit** — minor artifact-chain lag.

---

## 4. Adversarial pass calibration

### Rejected alternatives that mattered later

- **Option B for G1 (EvalRecorder + live fixtures):** Avoided — Option A sufficient for stated honesty goal (F-09 observation confirms).
- **Single "Big T1" subtask:** Rejected — four parallel commits worked without merge pain.
- **Defer G2/G3/G4 to later phase:** Rejected — all four goals shipped in one phase as MVP_PICKUP required.
- **Revert T1–T4 on amendment (audit non-goal):** Correctly rejected.

### Load-bearing assumptions

| Assumption | Held? |
|------------|-------|
| `DEFAULT_COMPONENT_KEYWORDS` covers q1–q5 components | **Yes** — T1 HALT criterion satisfied; medium tier green |
| `run_replay_check` dispatch reachable via `expect.replay` | **Yes** — T4 verified; 33 slow goldens pass |
| `multi_hop_declared` not consumed outside `runner.py` | **Yes** — grep confirmed; Surface 7 ruled out |
| `ReplayFixture(**raw)` succeeds for T4 JSON | **Yes** — golden replay passes |
| T2/T4 response key alignment (Surface soft dep) | **Yes** — inline unit fixture matches §2 key list |
| graphrag keyword coupling (Surface 1) | **Yes** — T1 YAML-only; no dict edit |
| manifest ↔ q6 sync (Surface 3) | **Yes** — `test_manifest_coverage` |

### Highest re-plan risk (§5.3: T4)

- **Predicted:** Hand-authored fixture sub-check mismatches (`must_mention`, `min_sources`, trace keys).
- **Actual:** T4 landed cleanly — no iteration, no re-plan. Technical risk did not materialize.
- **Process surprise:** Trouble came from **T2 CI omission** and **T7 closure commit discipline**, not from T4 fixture authoring.

---

## 5. Methodology gaps surfaced

### Orchestrator should have prompted for…

- **Explicit §2 Tests row for CI** when a new test file is the **only** gate for a code-path regression (stub reintroduction) — F-03 was predictable from T2 architectural intent + context-map Flag 6.
- **§8 commit-before-audit rule** in the original plan closure spec — phase 1 had the same F-01/F-07 class; pattern repeats across phases.
- **T7 kill criterion:** `§8.1 Tree SHA` must equal `git rev-parse HEAD` at end of T7 — would have blocked orphaned `26b05116` pointer and dangling commits.
- **Amendment packet commit** as part of T7 outputs when plan §6 lists packet paths — avoid untracked-until-`42d8cd2` lag.

### Executor should have blocked or escalated…

- Shipping `test_runner_unit.py` without either (a) CI wiring or (b) explicit CHANGELOG deferral + plan note that stub regression is **local-only** until amendment.
- Writing plan §8 / Status Complete on disk before `git commit` — executor handoff implied closure while HEAD still v1.0 *Ready for execution*.
- Recording closure SHA in §8.1 without verifying `git merge-base --is-ancestor <SHA> HEAD` — produced citation of dangling `26b05116`.

### Contracts schema missing or vestigial

- **§2 Typed-surface "round-trip test"** language implied committed-fixture load; inline mock satisfied pass/fail but not fidelity narrative — F-05 remains a recurring gap when unit tests mock what §2 names as on-disk round-trip.
- **§2 Amendment supersession pattern** worked for test-name drift (F-04); closure SHA has no *Landed:* equivalent — F-11 is a pointer bug, not a behavior bug.
- **"Tests exit commands" vs "CI gate"** — conflating local pytest success with PR regression coverage allowed F-03.

*Do not edit skills from this file.*

---

## 6. Single sentence verdict

**Partially yes:** The parallel DAG, adversarial assumptions (especially T4), kill criteria at execution time, and amendment loop (T5–T7 → re-audit pass on blockers) held up for substantive Phase 2 intent; the methodology **leaked** on closure discipline (§8 committed after narrative handoff, F-01/F-07 repeat), regression CI wiring left implicit until audit (F-03), and closure SHA management (dangling T7 commits, F-11 still open at `HEAD`).
