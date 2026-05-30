# Methodology retrospective — mvp-phase6-mvp-plus

## 1. Task identifier

**Task:** mvp-phase6-mvp-plus (MVP Phase 6 — orchestrated CLI/API routing, live MCP adapter wiring, per-step telemetry, demo script)  
**Date:** Planning / context map 2026-05-30 · execution same session · audit 2026-05-30  
**Plan version:** 1.1 (`orchestrator-planning` v0.6; context map promoted from `_pending/`)  
**Skills:** pre-plan-exploration v0.2, orchestrator-planning v0.6, executor-subtask-execution, auditor-review (initial audit, untracked)  
**One line:** Wire `--orchestrated` / `orchestrated: true` through `run_orchestrated_query` and `build_mcp_adapter`, persist per-node `agent_executions` rows, ship `.dev/demo/aria-mvp-demo.sh` and pickup checkboxes.

**Related artifacts reviewed:** `.dev/plans/mvp-phase6-mvp-plus/{plan.md,context-map.md,packets/T1–T5.md}`, `.dev/decision-logs/T2-mcp-adapter-wiring.md`, `.dev/audits/2026-05-30-mvp-phase6-mvp-plus.md`, `CHANGELOG.md` § `mvp-phase6-mvp-plus — 2026-05-30`, phase commits on `dev`, plan appendix `documented_mess_up_to_cover_for_in_retro_method`.

---

## 2. Plan vs reality

### DAG vs execution

- **Planned:** T1 → parallel `{T2, T3}` → T2 → T4; T3 + T4 → T5.
- **Actual commit order:** T1 (`a387091`) → T3 (`b2ff729`) → T4 (`e2c725a`) → T5 (`2248f92`) → T2 remediation (`e2aadc6`, message `mvp phase 6`). No concurrent executor agents; T2 and T3 were not committed in parallel—T2 **code never landed** until after T4/T5.
- **Hard dependency violated:** T4 imports `run_orchestrated_query` from `aria.services.orchestrated_query` (T2 output). At `2248f92`, clean-checkout `pytest tests/unit -q` fails with `ModuleNotFoundError` on that import—plan §8.1 documents this correctly for that SHA.
- **Unsafe parallelization (planned):** File-disjoint `{T2, T3}` was safe on paper; in practice **shared `CHANGELOG.md` header** and overlapping working tree made parallel *sessions* risky (see §3 / plan appendix).
- **T5 kill criterion 1** (“T4 complete”) was satisfied by **presence of `--orchestrated` in source**, not by a green clean-tree import graph—methodology gap.

### Contracts at implementation surface

| §2 surface | Enforced at `e2aadc6`? | Notes |
|------------|-------------------------|-------|
| `ComplianceQueryRequest.orchestrated` | Yes | `a387091`; T4 smoke covers placeholder gate, not DTO round-trip alone |
| `ComplianceQueryResponse.execution_trace` | Yes | Conditional `_success_payload` / API body; Phase 4 JSON test still passes |
| `build_mcp_adapter` | Partial | Factory in production path; **`test_mcp_adapter_construction` constructs adapter directly**, not via factory (audit F-04) |
| `run_orchestrated_query` | Partial | Missing-deps test yes; **no success-path unit test** (CHANGELOG deferred; audit F-07) |
| `ORCHESTRATION_SCRATCH_AGENT_NAME/{node}` | Yes | T3 + `TestOrchestrationTelemetry` |
| Error envelope — CLI placeholder | Yes | `test_orchestrated_cli_smoke_placeholder_blocked` |
| Error envelope — API placeholder | Partial | Code matches frozen `detail`; **no unit test** (F-06) |
| Error envelope — missing deps | Yes | `test_run_orchestrated_query_missing_deps_returns_unavailable` |
| `index_vectors` → `index_chunks` | Yes | `test_index_vectors_delegates_to_vector_store_index_chunks` at `e2aadc6` |
| `X-ARIA-Mode: orchestrated-live` | Yes (runtime) | No eval enum assertion; §5.4 #3 ruled out correctly |
| Decision log T2 | Yes | Present at `e2aadc6`; deferred items in log body **did** land in later commits |

No `getattr` hollow contracts on the hot path; gaps are **deferred coverage** and **one misnamed construction test**, not dropped §2 keys.

### §2 / decision-log narrative vs later subtasks

- **CHANGELOG T2 bullet** existed at HEAD before T2 code (`2248f92`)—narrative/code drift until `e2aadc6`.
- **Plan §8** (invalid handoff, closure SHA `2248f92`, “T2 absent”, stub `index_vectors`) was authored at handoff time and **committed inside `e2aadc6` without refresh**—at same SHA as full T2 code, §8 still says invalid / T2 missing (audit F-02). Historical appendix `documented_mess_up_to_cover_for_in_retro_method` is accurate for T3 changelog incident but must not be read as current HEAD without banner.
- **T2 decision log** “deferred to T3/T4” items are **closed** in code; log status “Landed” is correct—no stale rejected-alternative implementation.

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T1 | standard | OK — DTO-only |
| T2 | architectural | OK — new service module, MCP seam, decision log; deserved tier |
| T3 | standard | OK |
| T4 | standard | OK — cross-cutting routing; could argue architectural for API mode header, but standard is fine |
| T5 | standard | OK — docs/demo |

### Closure vs committed reality

| SHA | Role |
|-----|------|
| `2248f92` | Plan §8 “closure” — **broken tree** (T4/T5 without T2) |
| `e2aadc6` | T2 code + decision log + `index_vectors` + plan §8/appendix — **128 unit tests pass** on clean tree |
| HEAD `e2aadc6` | Plan **Status** still `Active — §8 handoff invalid`; §8.1 still pins `2248f92` |

- **First audit** (`.dev/audits/2026-05-30-mvp-phase6-mvp-plus.md`, **untracked**): `pass-with-conditions` at `e2aadc6`; requires §8 refresh (F-02). No re-audit recorded after plan edit.
- **Context map** scout `ee87002` vs `e2aadc6`: expected divergence (F-01); §0 pre-acknowledged surface staleness for unchanged *scout* predictions on orchestration files that were about to change.
- **Closure SHA vs first commit containing all artifacts:** Plan’s valid closure should be **`e2aadc6`**, not `2248f92`. The “first commit with all §2 code paths” was **not** the same as the first commit claiming phase complete.
- **Audit file** not in `HEAD`—closure chain for audit discipline is incomplete until committed.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Formal HALTs fired:** 0 (no executor stop-and-escalate narrative in packets, CHANGELOG, or commits).

| Situation | HALT per packet? | What happened |
|-----------|------------------|---------------|
| T4-KC1: `ImportError` for `run_orchestrated_query` | **Yes** | **Not fired** — T4 committed at `e2c725a` while module existed only in dirty tree or was assumed from parallel work |
| T5-KC1: T4 `--orchestrated` present | File check only | Passed; did not require importable module at commit time |
| T2-KC1 async ToolPorts | No | Verified; working-tree tests green |
| T2-KC2 VectorStore API | No | `index_chunks` found |
| T1-KC3 Phase 1–4 Complete | No | Prerequisites met |
| T3 changelog cross-staging | No explicit KC | **Improvised** — delete peer T2 bullet, amend/reset; recovered commit scope, damaged shared audit trail (plan appendix) |

**HALT-shaped silent improvisation:** T4 and T5 landed on `dev` with an **import-broken** clean checkout. Kill criteria treated “routing code merged” as done without **commit-level DAG enforcement** or clean-tree `pytest`. Supplementary “128 passed on dirty tree” in plan §8.1 is explicit that this was known and non-binding—good honesty, bad process if handoff had stopped there.

### Amendment cycles

- **§7 amendment subtasks:** None (empty at v1.0; stayed empty).
- **Remediation:** Single `e2aadc6` (`mvp phase 6`) — not a scoped T7 “audit amendment” packet. Bundled T2 code, decision log, MCP fix, **plan §8 + retro appendix**, four methodology/learning retrospectives, and `.dev/demo-openapi-browser-adjunct.md` (audit F-03).
- **Audit:** Initial pass-with-conditions; **F-02 (plan §8 refresh) not applied** on HEAD—plan still contradicts `e2aadc6`.
- **Architectural tier without amendment pass:** First “closure” at `2248f92` would have failed any cold audit; sharper first pass on **commit order** would have caught T2 absence before T4 message landed.

---

## 4. Adversarial pass calibration

- **Rejected alternatives:** Semantic parity redesign, separate `/orchestrated-query` route, per-step SQLite table, monolith single executor—**none resurfaced**; implementation matches rejections.
- **§5.2 load-bearing assumptions:** #2 ToolPorts async, #3 `extra="forbid"`, #4 prerequisite plans, #5 conditional `execution_trace` — **held**. #1 strict `AppConnections` non-None — **not tested** in CI (wet-run only; audit treat-as-prediction).
- **§5.3 highest re-plan risk (T2):** Predicted VectorStore API / circular-import failure. **Actual trouble:** process—T2 never committed before T4/T5, not API absence. Secondary risk (README concurrent edit with Phase 5) did not bite; T5 demo section landed cleanly.
- **§5.4 couplings:** #1 async boundary closed; #2 trajectory eval closed (`38 passed`); #3 X-ARIA-Mode ruled out; #4 placeholder gate closed; #5 Phase 4 key equality closed; #6 `index_vectors` closed at `e2aadc6`. Flag 1 vector-only vs GraphRAG — intentional non-goal.

---

## 5. Methodology gaps surfaced

**Orchestrator skill should have prompted for:**

- Explicit **commit-order gate**: “T4 must not merge until `git show HEAD:aria/services/orchestrated_query.py` succeeds and clean-tree `pytest tests/unit -q` passes.”
- **Shared CHANGELOG policy** under one dated header when `{T2,T3}` parallelize—`git add -p` or per-subtask HTML anchors / fan-in-only changelog writes (retro prompts in plan appendix).
- §8 handoff template: distinguish **implementation SHA** vs **closure SHA**; require closure commit to update §8 in the **same** commit as last code artifact (phase-5 retro had similar one-SHA-stale class).

**Executor skill should have blocked:**

- T4 commit when T2 import is missing at **index/HEAD** (T4-KC1 spirit).
- Editing another subtask’s CHANGELOG bullets when “fixing” staging scope—reset index only.
- `git commit --amend` with unrelated staged paths without verifying `git diff --cached --name-only` against packet `files to touch`.

**Contracts schema:**

- §2 row tying `test_mcp_adapter_construction` to `build_mcp_adapter` **over-specified** the test body—allowed hollow factory coverage (F-04).
- No vestigial §2 rows; deferred tests are documented in CHANGELOG, not silent.

**Do not edit skills here** — patterns to watch across more retros: DAG commit gates, CHANGELOG isolation, closure §8 sync.

---

## 6. Single sentence verdict

**Partially** — the orchestrator decomposition and packets held up for intent and file boundaries, but the methodology **leaked on commit DAG enforcement, shared CHANGELOG hygiene, and closure narrative**: T4/T5 merged with a broken clean tree, T2 remediated in a mixed-scope commit, and plan §8 still invalid at the same SHA as green tests until F-02 is applied.
