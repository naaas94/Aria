# Audit — mvp-phase1-golden-wet-run

**Audit date:** 2026-05-30  
**Plan version:** 1.0 (`.dev/plans/mvp-phase1-golden-wet-run/plan.md`)  
**Repository HEAD:** `d448a310cd09995b563113f5dcc47663bd8b3a3b`  
**Auditor focus areas:**
1. **Integration seams** (mandatory) — Chroma/serve port collision, pytest marker wiring, seed_corpus bypass, Regulation `id` property for T4 Cypher.
2. **Failure paths** — ingest preflight vs `aria status` vs `GET /ready` under LLM failure (T6 kill-criterion evidence).
3. **Edge cases** — `API_PORT` override precedence and invalid env values.

**Context map:** `.dev/plans/mvp-phase1-golden-wet-run/context-map.md` · readiness **CONDITIONAL** at planning time  
**Provenance check result:** SHA **diverged** (map at `ee870022`, HEAD at `d448a310`)  
**Working tree at scout time:** clean

---

## Context chain completeness

| Artifact | Status | Notes |
|----------|--------|-------|
| Context map | Present | Consumed for Phase 0.5, 1, 4, 5 |
| Plan + packets T1–T6 | Present | §8 auditor handoff still deferred; plan **Status: Active** |
| Decision log T6 | Present | `.dev/decision-logs/T6-wet-run.md` in HEAD |
| Changelog | Present | `CHANGELOG.md` § mvp-phase1-golden-wet-run |
| Wet run log | Present | `.dev/MVP_PICKUP.md` lines 249–316 |
| Code diff T1–T6 | Present | 13 files, `f4322b9^..d448a31` |
| Tests | Run locally | `pytest tests/integration -m integration` → 25 passed; unit tests T3–T5 → 11 passed |

**Phase 0 discipline:** Cold-read findings were pinned from task statement (§1), shared contracts (§2), diffs, and tests **before** reading decision log, changelog, wet run narrative, or plan prose beyond §1–§2.

---

## Provenance log

| Check | Result |
|-------|--------|
| Context map SHA vs HEAD | **Diverged** — scout `ee870022`, audit `d448a310` |
| Diverged in-scope §File map paths | `aria/cli/commands/ingest.py`, `serve.py`, `status.py`, `pyproject.toml`, `tests/fixtures/sample_regulation.html`, `tests/integration/test_end_to_end.py`, `tests/integration/test_ingestion_pipeline.py`, `.dev/plans/mvp-phase1-golden-wet-run/context-map.md` |
| Working tree at scout | clean |
| Scout grep coverage | All patterns listed in §Coupling surfaces present in map |
| Plan artifacts in HEAD | `context-map.md`, `plan.md`, packets T1–T6, `T6-wet-run.md`, `MVP_PICKUP.md`, `CHANGELOG.md`, all code/test changes — **present-in-HEAD** |
| Plan §8 closure SHA | Not recorded (§8 deferred; plan not marked Complete) |
| Untracked local artifacts | `.dev/wet-run-t6-session.log` (decision log defers; not a plan deliverable) |

**Findings filed in Phase 0.5:** F-01 (`context-map-stale`, major)

---

## Cold-read log (Phase 0 — pinned)

| ID | Severity (guess) | Observation |
|----|------------------|-------------|
| CR-01 | major | Three unit test files (`test_serve.py`, `test_ingest_command.py`, `test_status.py`) added during T3–T5 commits; plan §2 Tests states *"No new test files created by T1–T5"*. |
| CR-02 | minor | `status.py` footer literal differs from plan T5 quoted string (`additionally` vs `also requires LLM (above)`). |
| CR-03 | minor | `ingest.py` `(none — Regulation nodes not found…)` suffix extends beyond §2 quoted contract. |
| CR-04 | observation | `serve.py` uses Pattern B (function-body `API_PORT` read); allowed by T3 kill criterion; Typer default remains literal `8080`. |
| CR-05 | observation | Wet run log claims sign-off **Y** with impact-chain and Chroma healthcheck caveats documented. |
| CR-06 | observation | Plan still **Active**; §8 auditor handoff empty despite T6 outputs present. |

---

## Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-01 | major | context-map-stale | 0.5 | — | Context map SHA diverged on 8 direct-scope files |
| F-02 | major | contract-violation | 2 | T3,T4,T5 | Unit test files added despite §2 prohibition for T1–T5 |
| F-03 | major | prediction-divergence | 1 | T3,T4,T5 | Test files in diff not listed in packet §Files to touch |
| F-04 | minor | contract-violation | 2 | T5 | Status ingest/LLM note literal differs from plan T5 spec |
| F-05 | minor | contract-violation | 2 | T4 | Regulation `(none…)` stdout suffix extends contract literal |
| F-06 | minor | contract-violation | 2 | T4 | §2 Types row says "No separate test" but `test_ingest_command.py` shipped |
| F-07 | minor | process-violation | 1 | — | Plan Status Active / §8 empty while T6 signed off and artifacts committed |
| F-08 | minor | coverage-gap | 5 | T6 | No automated replay of wet-run script or preflight-vs-ready matrix |
| F-09 | observation | — | 4 | T6 | Impact step returned 0 requirements after ingest-only sample (documented deferral) |
| F-10 | observation | — | 4 | T2 | CI dry-run exclusion of newly marked integration tests (changelog flagged) |

---

## Detailed findings (above minor)

### F-01 — Context map stale (major · context-map-stale)

**Expected:** Scout map at `ee870022` reflects pre-execution codebase.  
**Found:** HEAD is six commits ahead (`f4322b9`–`d448a31`). All T1–T6 direct-scope files in §File map have changed since scout.  
**Evidence:** `git diff ee87002..HEAD --name-only` on ingest, serve, status, fixtures, integration tests, pyproject, context-map itself.  
**Caveat:** Scout-flagged findings on those paths are stale-qualified; implementation review used current HEAD.

### F-02 — Test files violate §2 Tests contract (major · contract-violation)

**Expected:** Plan §2 Tests: *"No new test files created by T1–T5. T6 may add minimal smoke…"*  
**Found:**
- `tests/unit/test_serve.py` — commit `08280c4` (T3)
- `tests/unit/test_ingest_command.py` — commit `148de09` (T4)
- `tests/unit/test_status.py` — commit `8a09964` (T5)

**Evidence:** `git log --follow` per file; CHANGELOG acknowledges T4 tests only, not T3/T5.  
**Impact:** Beneficial coverage drift, but explicit shared contract broken without amendment subtask (§7 empty).

### F-03 — Packet files-to-touch drift (major · prediction-divergence)

**Expected:** Each subtask diff ⊆ packet §Files to touch (+ changelog).  
**Found:** T3/T4/T5 packets list only command modules; three unit test files appear in diff undocumented.  
**Evidence:** `.dev/plans/mvp-phase1-golden-wet-run/packets/T{3,4,5}.md` vs `git diff f4322b9^..d448a31 --name-only`.

---

## Detailed findings (minor — listed for pass conditions)

### F-04 — Status note literal drift (minor · contract-violation)

**Contract (T5 spec):** `"Note: aria ingest also requires LLM (above). aria status exits 0 if only LLM is unavailable."`  
**Shipped (`status.py`):** `"Note: aria ingest additionally requires LLM. aria status exits 0 even when LLM is unavailable."`  
User-visible; semantics preserved.

### F-05 — Regulation none-message suffix (minor · contract-violation)

**Contract §2 Logging:** `"  regulation_ids: (none — Regulation nodes not found)"`  
**Shipped (`ingest.py` L108–110):** adds `; use seed_graph.py IDs or check entity extractor)`.  
Positive case `"  regulation_ids: <comma-separated>"` matches; wet run observed comma-separated IDs.

### F-06 — T4 round-trip test row stale (minor · contract-violation)

§2 Types/interfaces row for regulation ID line says *"No separate test; wet run (T6) observes output live"* — contradicted by five unit tests in `test_ingest_command.py`. Tests are meaningful (Cypher string, stdout branches).

### F-07 — Plan closure incomplete (minor · process-violation)

T6 wet run log signed off **Y**; decision log and changelog committed; plan §8 still *"Deferred"* and **Status: Active**. Orchestrator closure step not performed.

---

## Adversarial test log

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Chroma :8000 vs `aria serve` default | Serve binds 8080; `API_PORT` overrides | `serve.py` L13–17; `test_serve.py` 4 cases | **passes** |
| `pytest tests/integration -m integration` collects ≥1 | ≥1 test after T2 | 25 collected, 25 passed (audit run) | **passes** |
| `seed_corpus.py` bypasses full wiring | T6 must not use as primary ingest | Decision log + wet run used `aria ingest tests/fixtures/…` | **passes** |
| Regulation node property key `id` for T4 Cypher | `MATCH (r:Regulation) RETURN r.id` returns IDs | `aria/contracts/regulation.py` L68; `aria/graph/builder.py` L159; wet run printed `reg-gdpr, …` | **passes** |
| Scratch orchestration import breaks collection | `pytest --collect-only tests/integration/` succeeds | 25 collected; no import errors | **passes** (suspected coupling ruled out) |
| Ingest preflight requires LLM; status tolerates LLM fail | ingest exit 1; status exit 0; `/ready` 200 `llm:false` | Documented in wet run log L293–298, decision log §Preflight vs readiness | **passes** (manual evidence; no automated test) |
| Invalid `API_PORT` (non-integer) | Undefined; changelog defers | `int(os.getenv(...))` would raise `ValueError` at serve startup | **unknown** (deferred per changelog) |
| Neo4j `execute_read` failure during ID fetch | Should not crash ingest success path | No test; exception would propagate from `_fetch_regulation_ids` | **unknown** (deferred per changelog) |
| `ARIA_PLACEHOLDER_API=false` during integration pytest | Tests expect placeholder mode | Wet run log L301–302: 2 failures when env leaked | **passes** (documented operator hazard) |

---

## Coverage gap list (prioritized)

| Priority | Gap | Owner | Rationale |
|----------|-----|-------|-----------|
| High | Automated wet-run / preflight-vs-ready replay | T6 deferral | Kill criteria (a–d) verified manually only; changelog explicitly deferred |
| Medium | Invalid `API_PORT` startup error | T3 deferral | Changelog deferred; no unit test |
| Medium | `_fetch_regulation_ids` Neo4j read failure | T4 deferral | Changelog deferred |
| Medium | Flag 6 — CliRunner live-path suites | Non-goal | Plan §1 non-goal; decision log deferred |
| Low | Marker lint for new `tests/integration/` classes | T2 deferral | Changelog notes CI maintainer risk |
| Low | `ingest`/`status`/`serve` CLI symbols — scout `none_found` | Pre-existing | Partially closed by new unit tests (F-02) |

---

## Intent traceability (Phase 1 summary)

| Layer | Verdict |
|-------|---------|
| Task statement → T1–T6 scopes | **Aligned** — five blockers + wet run map cleanly |
| Subtask scopes → code | **Mostly aligned** — F-02/F-03 scope widening via unit tests |
| Non-goals respected | **Yes** — no scratch refactor, no Phase 2–6, no HTTP ingest changes |
| T6 outputs | **Met** — wet run log filled, decision log present, preflight vs `/ready` evidenced, sign-off Y |
| Map → plan §4 files | T1–T5 direct files match; test files absent from plan §4 |
| Narrative vs cold read | CHANGELOG partial acknowledgment of CR-01 (T4 only); T3/T5 test files not narrated → mild **narrative-concealment** on CR-01 for T3/T5 (observation-level; folded into F-02/F-03) |

---

## Decision log audit (Phase 3)

| Check | Result |
|-------|--------|
| Chosen approach implemented | **Yes** — full command sequence executed per log |
| Rejected alternatives avoided | **Yes** — no seed_corpus primary path; live mode enforced |
| Assumptions valid | **Yes** — OpenAI fallback when Ollama slow; integration tests use placeholder |
| Deferred items deferred | **Yes** — Chroma healthcheck, Flag 6, wet-run replay script not silently shipped |
| Stale prose | **No** — log matches wet run log and HEAD behavior |

---

## Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1: ingest preflight stricter than `/ready` | confirmed coupling | **verified** | — |
| Surface 2: placeholder default masks live failures | confirmed coupling | **verified** (wet run used `false`; pytest uses default) | — |
| Surface 3: strict connect error messages | confirmed coupling | **verified** (wet run preflight lines) | — |
| Surface 5: Chroma port 8000 | confirmed coupling | **verified** | — |
| Surface 6: serve default 8000 collision | suspected | **verified then resolved** | T3 changed default to 8080 |
| Surface 7: regulation ID discovery | confirmed coupling | **verified** | T4 + wet run IDs |
| Surface 8: seed_corpus bypass | confirmed coupling | **verified** | T6 avoided |
| Surface 9: integration marker location | suspected | **verified then resolved** | T2 markers; 25 tests |
| Flag 1: pytest command mismatch | ambiguity_flag | **verified** | Resolved by T2 |
| Flag 2: missing ingest sample path | ambiguity_flag | **verified** | Resolved by T1 |
| Flag 3: regulation ID discovery | ambiguity_flag | **verified** | Resolved by T4 |
| Flag 4: seed_corpus equivalence | ambiguity_flag | **verified** | Documented in T6 |
| Flag 5: status vs ingest LLM gate | ambiguity_flag | **verified** | Resolved by T5 + T6 evidence |
| Flag 6: CLI live-path coverage | ambiguity_flag | **not-tested** (deferred non-goal) | F-08 |
| Suspected: Regulation `id` key name | suspected coupling | **ruled-out** | `regulation.py` + `graph/builder.py` |
| Suspected: scratch import collection failure | suspected coupling | **ruled-out** | collect-only 25 tests |
| `ingest`/`serve`/`status` suspect_modified, test_file none_found | suspect_modified | **prediction-divergence** | Unit tests added (F-02) |

---

## Verdict

**fail**

Phase 1 golden-path **intent and runtime behavior are sound**: wet run sign-off **Y**, integration command passes (25/25), preflight-vs-readiness evidenced, T1–T5 blockers resolved. No **critical** defects. Audit fails on **major** contract/process findings that must be reconciled before merge-closure.

**Must resolve:**
1. **F-02 / F-03** — Amend plan §2 Tests and/or add §7 amendment documenting `tests/unit/test_serve.py`, `test_ingest_command.py`, `test_status.py` (added in T3–T5 commits but forbidden by §2 and absent from packet §Files to touch). Revert tests only if amendment is rejected (not recommended — tests pass and add signal).
2. **F-07** — Mark plan **Complete**; populate §8 auditor handoff (tree SHA `d448a310`, artifact chain, link to this audit).

**Should resolve (minor, non-blocking for re-audit pass):**
3. **F-04 / F-05 / F-06** — Align §2 literal quotes with shipped stdout strings, or change code to match frozen contract text.
4. **F-01** — Re-scout context map if further Phase 1 work continues on stale paths.
5. **F-08** — Track wet-run replay automation as a follow-up (explicitly deferred in changelog/decision log).

---

*Auditor: post-execution review v0.4 · no fixes applied in this pass.*
