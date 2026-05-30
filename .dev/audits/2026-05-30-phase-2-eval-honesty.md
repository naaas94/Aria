# Audit report — phase-2-eval-honesty

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-30  
**Plan version:** v1.1 (on disk, working tree) / v1.0 (at `HEAD`)  
**Auditor closure SHA cited by plan §8:** `3a607176a9294f67ea8f840b2565e499dc61a230`  
**Audit-time `HEAD`:** `3a607176a9294f67ea8f840b2565e499dc61a230`  
**Working tree:** dirty — `.dev/plans/phase-2-eval-honesty/plan.md` (§8 handoff uncommitted), `uv.lock` (unrelated)

---

## 1. Audit metadata

| Field | Value |
|-------|--------|
| **Task** | phase-2-eval-honesty (MVP eval honesty — retrieval YAMLs, stub removal, CI label, slow replay) |
| **Context map** | `.dev/plans/phase-2-eval-honesty/context-map.md` — readiness **CONDITIONAL** at scout time |
| **Provenance (scout)** | `ee87002297a495389b9bc79a510966dd30ab23f7`, working tree clean |
| **Provenance (audit)** | `3a60717`, diverged from scout on all Phase 2 direct-touch files |
| **Phase 0 discipline** | Completed before reading decision logs, CHANGELOG body, plan §§3–8 prose, or MVP_PICKUP |
| **Adversarial focus** | **Integration seams** (manifest ↔ YAML ↔ `load_replay_fixture` ↔ `run_replay_check`; scout §Coupling surfaces 3–5, 7, 9) |
| **Adversarial focus** | **Regression surface** (T2 stub removal — golden medium tier alone would not detect `multi_hop_declared` reintroduction) |
| **Adversarial focus** | **Failure paths** (`FileNotFoundError` replay path; empty `retrieved_context`) |
| **Re-audit** | No prior audit for this task |

---

## 2. Provenance log

| Check | Result |
|-------|--------|
| Context map path | Present — `.dev/plans/phase-2-eval-honesty/context-map.md` |
| Scout vs audit SHA | **Diverged** — scout `ee87002` → audit `3a60717` |
| Diverged in-scope files (§File map `direct`) | All retrieval q1–q5 YAMLs, `runner.py`, `manifest.yaml`, `ci.yml`, new q6/fixture/`test_runner_unit.py` |
| Scout working tree | clean at scout time |
| Audit working tree | **dirty** — `plan.md` §8 uncommitted; `uv.lock` modified (out of Phase 2 scope) |
| Scout grep coverage | Patterns in §Coupling surfaces present; no `scout-incomplete` against orchestrator vocabulary |
| **Plan-artifact provenance** | See table below |

### Plan-artifact provenance (closure SHA `3a60717` = `HEAD`)

| Artifact | present-in-HEAD | on-disk-only | Notes |
|----------|-----------------|--------------|-------|
| `.dev/plans/phase-2-eval-honesty/context-map.md` | yes | — | Stale vs execution |
| `.dev/plans/phase-2-eval-honesty/plan.md` v1.1 + §8 | **no** | **yes** | HEAD: v1.0, Status *Ready for execution*, no §8 → **F-01** |
| `packets/T1.md` … `T4.md` | yes | — | |
| `.dev/decision-logs/T2-requires-multi-hop.md` | yes | — | |
| `CHANGELOG.md` § phase-2-eval-honesty | yes | — | |
| `tests/eval/golden_set/test_runner_unit.py` | yes | — | |
| `tests/eval/golden_set/replay/eval-replay-gdpr-erasure.json` | yes | — | |
| `.dev/audits/2026-05-30-phase-2-eval-honesty.md` | no | yes | This report (expected) |

§8.1 claims “working tree clean at handoff” — **false at audit time** due to uncommitted `plan.md` §8.

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|----------|----------|--------|
| Context map | yes | Stale-qualified for file-map predictions |
| Plan §1–§2 (Phase 0) | yes | Full plan §§3–8 read after Phase 0 |
| Packets T1–T4 | yes (spot-checked vs diff) | |
| Decision log T2 | yes | |
| CHANGELOG | yes | |
| Code diff `a2da501..HEAD` | yes | 13 files, 4 commits T1–T4 |
| Tests | run locally — 38 passed | |
| MVP_PICKUP / evaluation_ci_audit | referenced | Pre-fix narrative; not authority per plan §8.2 |

---

## 4. Cold-read log (Phase 0 — pinned)

1. **Synthetic `retrieved_context` in q1–q5** — Pass/fail is substring keyword matching only; no retrieval pipeline involved. Aligns with Option A if that was chosen; otherwise looks like green tests without retrieval fidelity.
2. **`test_runner_unit.py` replay test** — Patches `load_replay_fixture`; does not read `replay/eval-replay-gdpr-erasure.json` on disk at unit level (golden slow path may still load it).
3. **`test_runner_unit.py` absent from `.github/workflows/ci.yml`** — PR CI runs `test_goldens.py --golden-tier=fast` only; T2 unit file may never run in CI.
4. **Plan §8 / v1.1 Complete** — Visible in workspace; `git show HEAD:plan.md` still v1.0 *Ready for execution* → closure doc not in `HEAD`.
5. **`requires_multi_hop` in YAML** — No hop validation in `run_retrieval_check`; field is inert for pass/fail (post-stub-removal).
6. **q6 under `cases/retrieval/`** — Uses `expect.replay`, not retrieval lens; naming is confusing but mechanically valid if manifest/dispatch agree.

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-01 | **major** | artifact-not-in-HEAD | 0.5 | T8/handoff | Plan v1.1 + §8 auditor handoff exists on disk but not at `HEAD` (`3a60717`) |
| F-02 | **major** | context-map-stale | 0.5 | — | Scout SHA `ee87002` ≠ audit SHA; all direct file-map rows touched |
| F-03 | **major** | coverage-gap | 5 | T2 | `test_runner_unit.py` not invoked by PR or nightly workflows; stub regression not CI-gated |
| F-04 | minor | contract-violation | 2 | T2 | §2 names `test_run_replay_check_with_fixture`; shipped `test_run_replay_check_passes_with_inline_fixture` |
| F-05 | minor | coverage-gap | 5 | T2/T4 | No unit test loads committed `eval-replay-gdpr-erasure.json` (golden slow covers E2E) |
| F-06 | minor | coverage-gap | 5 | T1 | No test for partial/wrong `retrieved_context` on real golden YAMLs (deferred in CHANGELOG) |
| F-07 | minor | narrative-concealment | 1 | — | Plan §8.1 claims clean working tree; audit found uncommitted §8 |
| F-08 | minor | intent-drift | 1 | — | `.dev/MVP_PICKUP.md` G1/G3/G4 rows still describe pre-Phase-2 failure modes (plan §8.4 defers doc sync) |
| F-09 | observation | — | 1 | T1 | Option A improves CI signal honesty, not retrieval quality — explicit non-goal |
| F-10 | observation | — | 4 | T4 | Fixture `case_id` matches YAML `id`; runner does not enforce coupling (deferred) |

---

## 6. Detailed findings (above minor)

### F-01 — Plan closure not in `HEAD` (major · artifact-not-in-HEAD)

**Expected:** Plan §8 and status **Complete** at closure SHA `3a60717` per handoff narrative.  
**Found:** `git show HEAD:.dev/plans/phase-2-eval-honesty/plan.md` shows **Version 1.0**, **Status: Ready for execution**, no §8. Working tree adds v1.1 + §8 (~72 lines).  
**Evidence:** `git diff HEAD -- .dev/plans/phase-2-eval-honesty/plan.md`

### F-02 — Context map stale (major · context-map-stale)

**Expected:** Scout map reflects pre-execution codebase.  
**Found:** Scout `ee87002`; execution `3a60717`. All §File map `direct` paths in Phase 2 diff. Findings against scout “empty context / no replay / stub” predictions are **stale-qualified** — outcomes verified against current code, not scout file contents.

### F-03 — Runner unit tests not in CI (major · coverage-gap)

**Expected:** §2 Tests binding for `test_runner_unit.py`; T2 kill criterion: stub must not return without unit coverage; regressions caught in CI.  
**Found:**
- `.github/workflows/ci.yml` — `pytest tests/eval/golden_set/test_goldens.py --golden-tier=fast` only
- `.github/workflows/nightly.yml` — `test_goldens.py --golden-tier=slow` only; “Full eval suite” **ignores** `tests/eval/golden_set`
- Re-adding `multi_hop_declared` stub would **not** fail medium/slow goldens (keyword-only pass); only `test_run_retrieval_check_passes_with_keywords` asserts absence of `multi_hop_declared`

**Evidence:** `.github/workflows/ci.yml` lines 40–43; `test_runner_unit.py` lines 32–39

---

## 7. Adversarial test log

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Manifest id/tier/file matches q6 YAML | `test_manifest_coverage` passes | Manifest row `eval-replay-gdpr-erasure` / `tier: slow` / `retrieval/q6_...` | **pass** (pytest) |
| `load_replay_fixture` + `ReplayFixture(**raw)` for T4 JSON | No TypeError; replay checks run | Golden `--golden-tier=slow` includes case; 33 goldens passed | **pass** |
| `run_replay_check` strategy / sources / trace / quality | Fixture matches q6 `expect.replay` | JSON has `hybrid`, 2 sources, trace keys, answer mentions erasure/personal data | **pass** (code + golden) |
| Remove stub — medium retrieval q1–q5 | 5 pass at `--golden-tier=medium` | 32 passed, 1 skipped at medium (audit run) | **pass** |
| CI fast tier does not claim replay | Step name without “replay” | `"Golden set (fast tier)"` | **pass** |
| Reintroduce `multi_hop_declared` stub | CI should fail | CI would **not** run `test_runner_unit.py` — **unknown** in CI; unit test would fail locally | **fail** (regression surface) |
| `DEFAULT_COMPONENT_KEYWORDS` vs graphrag coupling (Surface 1) | T1 must not edit keyword dict | `git diff a2da501..HEAD` — no `runner.py` keyword edits, no `graphrag_vs_vector_rag.py` | **pass** |
| `multi_hop_declared` consumed outside runner (Surface 7 suspected) | No readers | Grep: only docs/tests/history reference string; not in `runner.py` at HEAD | **pass** (ruled out) |

---

## 8. Coverage gap list (prioritized)

1. **F-03 (major)** — Wire `pytest tests/eval/golden_set/test_runner_unit.py` into PR CI (fast) and/or nightly.
2. **F-01 (major)** — Commit plan v1.1 + §8 to `HEAD` so closure SHA matches artifact chain.
3. **F-05 (minor)** — Optional: unit test calling `load_replay_fixture("eval-replay-gdpr-erasure.json")` without mock (§2 typed-surface narrative).
4. **F-06 (minor)** — Golden negative for keyword-mismatch `retrieved_context` (CHANGELOG deferred).
5. **Deferred (documented)** — Real `requires_multi_hop` validation; fixture `case_id` ↔ YAML `id` enforcement; workflow step name assertion (T3).

---

## 9. Phase 1 — Intent traceability (summary)

| Check | Result |
|-------|--------|
| Task statement → code | **Met** — Option A context, stub removed, CI renamed, slow replay added |
| Non-goals | **Respected** — no HybridRetriever, no `tests/unit/`, no graphrag/llm changes |
| Subtask file sets | **Disjoint** — diff matches T1–T4 packets |
| §8 narrative vs cold read | **F-07** — clean-tree claim wrong; substantive outcomes otherwise align |
| Map → plan §4 | Scout direct files ⊆ plan §4; q6/fixture/unit file predicted by plan not scout file map (planner-added — OK) |
| Flag 6 (missing unit tests) | **Closed** — `test_runner_unit.py` added |
| Intent drift (honesty semantics) | **Observation F-09** — honesty = CI/lens integrity, not live retrieval (explicit in §0/§1) |

---

## 10. Phase 2 — Contract compliance (summary)

| §2 row | Status |
|--------|--------|
| `requires_multi_hop` retained, no validator | OK — `schema.py`; `test_run_retrieval_check_requires_multi_hop_does_not_affect_outcome` |
| Stub removed | OK — `runner.py` lines 179–204 |
| Naming (q6, fixture, unit file) | OK |
| `ReplayFixture` fields in JSON | OK — loads in golden replay |
| Typed-surface replay round-trip in **unit** test | **Partial** — F-04, F-05; golden provides real round-trip |
| Tests exit commands | OK — 38 passed locally at audit time |
| Decision log path | OK in HEAD |
| Literal test name in §2 | **F-04** minor |

---

## 11. Phase 3 — Decision log audit

**`.dev/decision-logs/T2-requires-multi-hop.md`**

| Check | Result |
|-------|--------|
| Chosen approach implemented | Yes — stub removed, unit tests added |
| Rejected alternatives avoided | Yes — no hop validator, field kept |
| Assumptions | Grep claim holds at HEAD |
| Deferred items | Real hop validation not implemented — consistent with plan §8.4 |
| Stale prose | Header says plan v1.0 — minor vs v1.1 on disk |

No `narrative-concealment` on cold-read F-03 (CI gap) — decision log does not claim CI wiring.

---

## 12. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|----------------|------|---------|---------|
| Surface 1 — keyword lexicon runner ↔ graphrag | confirmed coupling | **verified** — T1 did not edit dict; no divergence | — |
| Surface 2 — q1–q5 ↔ EVAL_QUESTIONS text | confirmed | **verified** — questions unchanged; context only filled | — |
| Surface 3 — manifest ↔ YAML sync | confirmed | **verified** — `test_manifest_coverage` + q6 entry | — |
| Surface 4 — replay fixture filename binding | confirmed | **verified** — golden slow replay passes | — |
| Surface 5 — CI label vs replay | confirmed | **verified** — T3 rename | — |
| Surface 6 — nightly slow includes medium retrieval | confirmed | **verified** — medium run green | — |
| Surface 7 — `multi_hop_declared` always pass | confirmed | **verified** — stub removed | — |
| Surface 8 — E2E vs replay shape | suspected | **ruled out** for T4 hand-authored fixture | — |
| Surface 9 — retrieval lens no HybridRetriever | confirmed | **verified** — Option A + recorded replay | — |
| Surface 10 — EvalRecorder unwired | suspected | **not-tested** for Phase 2 (Option B out of scope) | — |
| Flag 6 — no unit tests for run_*_check | missing_test_coverage | **verified** closed | — |
| Flag 1–5, 7 | ownership / vocabulary | **verified** resolved per plan §0 | — |

---

## 13. Verdict

### `fail`

**Must resolve before merge:**

1. **F-01** — Commit `.dev/plans/phase-2-eval-honesty/plan.md` v1.1 with §8 to `HEAD` so closure SHA and artifact chain match.
2. **F-03** — Add `tests/eval/golden_set/test_runner_unit.py` to PR CI (recommended: append to the existing golden-set step or a dedicated fast step).

**Substantive Phase 2 intent:** **Delivered** — medium retrieval greens, stub removed, CI label honest, replay lens exercised at slow tier; local verification `38 passed` at audit time.

**Does not block on:** F-02 (staleness is archival), F-08 (doc hygiene deferred to Phase 5), F-06/F-10 (explicitly deferred), Option A retrieval fidelity (non-goal).

---

## 14. Auditor notes for orchestrator

- Reconcile **F-07** when committing §8 — update §8.1 working-tree sentence.
- Consider closing `.dev/AUDIT_DIGEST.md` #8 and `evaluation_ci_audit.md` P1 in Phase 5 — code fix landed; digest still describes stub behavior.
- `uv.lock` dirty at audit — unrelated to Phase 2; do not mix into closure commit unless intentional.

---

## 15. Re-audit — revision 2

**Audit document revision:** 2  
**Supersedes:** Revision 1 §13 Verdict (`fail`) and revision 1 §14 orchestrator notes for F-01/F-03/F-07 only.  
**Does not supersede:** Revision 1 §§1–12 historical record (initial cold read, findings, adversarial log at `3a60717`).  
**Re-audit date:** 2026-05-30  
**Re-audit `HEAD`:** `e3036a3fa2a53ac53f21972f3e00f856b6132679`  
**Remediation commits (since rev. 1):** `678aaea` T5 (CI) · `63d65a2` T6 (§2 Amendment) · `26b05116` / `e3036a3` T7 (plan §8 + audit commit)  
**Working tree at re-audit:** clean except untracked `packets/T5.md`, `T6.md`, `T7.md` (not in §8.2 chain)

### 15.1 Omission-free artifact checklist (re-pass)

| Surface | Opened / verified |
|---------|---------------------|
| Plan v1.2 + amendment + §8 | `git show HEAD:.dev/plans/phase-2-eval-honesty/plan.md` |
| Context map *Post-execution* | HEAD |
| Revision 1 audit (this file) | HEAD |
| `ci.yml` golden step | HEAD — line 44 `test_runner_unit.py` |
| `test_runner_unit.py` | HEAD — `test_run_replay_check_passes_with_inline_fixture` present |
| `CHANGELOG.md` phase-2 section | HEAD — T5/T6 entries |
| `T2-requires-multi-hop.md` | HEAD |
| Code unchanged since T4 | `git diff 3a60717..HEAD` — plan/audit/ci/changelog/context only after T4 |

### 15.2 Phase 0 cold-read (re-run — fresh)

**Inputs:** §1 task statement, §2 + §2 Amendment, diff `3a60717..HEAD`, tests at `e3036a3`.

1. **CI golden step** — Second pytest line runs `test_runner_unit.py` without `-m golden`; addresses rev. 1 F-03.
2. **Plan at HEAD** — v1.2 **Complete**, §8 + amendment block present; addresses rev. 1 F-01.
3. **§8.1 Tree SHA** — Records `26b05116` but re-audit `HEAD` is `e3036a3` (second T7 commit, same parent `63d65a2`); closure pointer is one commit stale.
4. **Untracked amendment packets** — `packets/T5–T7.md` on disk only; not required by §8.2 at HEAD.
5. **Remediation scope** — No new application code; T5–T7 are process/CI/contract closure only.
6. **Golden behavior** — Unchanged since T4; 38 tests pass at re-audit.

### 15.3 Provenance log (re-audit)

| Check | Result |
|-------|--------|
| Plan v1.2 + §8 at `HEAD` | **yes** — F-01 **resolved** |
| Audit rev. 1 at `HEAD` | **yes** |
| `ci.yml` → `test_runner_unit.py` | **yes** — F-03 **resolved** |
| §2 Amendment *Landed:* rows | **yes** — F-04 **resolved** |
| Context map *Post-execution* | **yes** — F-02 **resolved** (staleness documented; scout SHA still `ee87002`) |
| §8.1 closure SHA vs `HEAD` | **diverged** — plan/context cite `26b05116`, audit `HEAD` is `e3036a3` → **F-11** (new, minor) |
| Untracked `packets/T5–T7.md` | on-disk-only — observation, non-blocking |

### 15.4 Finding status vs revision 1

| Prior ID | Prior severity | Prior type | Status | Evidence at `e3036a3` |
|----------|----------------|------------|--------|------------------------|
| F-01 | major | artifact-not-in-HEAD | **resolved** | `git show HEAD:plan.md` → v1.2, §8, Status Complete |
| F-02 | major | context-map-stale | **resolved** | `context-map.md` §Post-execution with closure note |
| F-03 | major | coverage-gap | **resolved** | `ci.yml` lines 42–44 invoke `test_runner_unit.py` |
| F-04 | minor | contract-violation | **resolved** | Plan §2 Amendment *Landed:* `test_run_replay_check_passes_with_inline_fixture` |
| F-05 | minor | coverage-gap | **open** | Deferred per plan §2 Amendment / §8.4 |
| F-06 | minor | coverage-gap | **open** | Deferred per CHANGELOG T1 |
| F-07 | minor | narrative-concealment | **resolved** | §8.1 “clean at closure commit” (no false pre-commit handoff claim) |
| F-08 | minor | intent-drift | **open** | MVP_PICKUP / AUDIT_DIGEST still pre-fix narrative; Phase 5 |
| F-09 | observation | — | **open** | Option A honesty semantics unchanged (by design) |
| F-10 | observation | — | **open** | fixture `case_id` coupling still not enforced |

**New (revision 2 only):**

| ID | Severity | Type | Description |
|----|----------|------|-------------|
| F-11 | minor | decision-log-stale | §8.1 and context-map *Post-execution* cite closure SHA `26b05116`; branch tip / re-audit `HEAD` is `e3036a3` (superseding T7). `git show 26b05116:<path>` ≠ `git show HEAD:<path>` for plan tail. |

### 15.5 Adversarial re-check (remediation-focused)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| F-03 — stub regression gated in PR CI | `test_runner_unit.py` in `ci.yml` | Line 44 present; separate invocation (no `-m golden`) | **pass** |
| F-01 — plan closure archivable | `git show HEAD:plan.md` has §8 | v1.2 Complete + §8.6 remediation table | **pass** |
| F-04 — replay test symbol | Amendment name matches code | `test_run_replay_check_passes_with_inline_fixture` at `test_runner_unit.py:60` | **pass** |
| Phase 2 combined exit | 38 passed | `pytest test_runner_unit.py + test_goldens.py --golden-tier=slow` → 38 passed | **pass** |
| §8.2 paths at recorded closure SHA | `git show <§8.1 SHA>:path` for all rows | Fails if SHA is `26b05116` but tip is `e3036a3` for identical §8 content — content equivalent; SHA pointer wrong | **fail** (F-11 only) |
| T7 kill (d) — CI still lacks unit file | Must have `test_runner_unit.py` | Present | **pass** |

### 15.6 Re-audit verdict

### `pass-with-conditions`

Revision 1 blockers **F-01** and **F-03** are **resolved** at `e3036a3`. Substantive Phase 2 intent remains delivered; remediation did not regress T1–T4 code paths.

**Condition (non-blocking):** **F-11** — Update plan §8.1 and `context-map.md` *Post-execution* closure SHA to `e3036a3` (or document that `26b05116` is intentional archival tip and branch moved — prefer aligning to `HEAD`).

**Still open by design (unchanged from rev. 1):** F-05, F-06, F-08, F-09, F-10.

**Merge recommendation:** Accept Phase 2 + amendment closure; fix F-11 in a small follow-up doc commit or fold into next hygiene pass.
