# Audit — mvp-phase6-mvp-plus

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-30  
**Auditor focus areas:** Integration seams (CLI/API → `run_orchestrated_query` → `build_mcp_adapter` → `OrchestrationGraph.execute` → telemetry); failure paths (placeholder gate, missing Neo4j/Chroma). Rationale: Phase 6 is almost entirely cross-module wiring; cold read and context-map §Coupling surfaces center on those seams.

---

## 1. Audit metadata

| Field | Value |
|-------|--------|
| Task name | mvp-phase6-mvp-plus |
| Plan version | 1.1 (`Active — §8 handoff invalid`) |
| Implementation HEAD | `e2aadc61f98bceb045fd9bf680ee0063d9c59be2` |
| Branch | `dev` (ahead of `origin/dev` by 5 commits for phase 6: `a387091` T1 → `b2ff729` T3 → `e2c725a` T4 → `2248f92` T5 → `e2aadc6` T2 remediation) |
| Context map | `.dev/plans/mvp-phase6-mvp-plus/context-map.md` — readiness **CONDITIONAL** at scout time |
| Provenance (scout SHA) | `ee87002297a495389b9bc79a510966dd30ab23f7` — **diverged** from audit HEAD (expected: phase implemented) |
| Scout working tree | dirty (`?? .dev/plans/`) at exploration; **clean** at audit time |
| Phase 0 discipline | Completed before reading CHANGELOG narrative, decision log body, plan §4+ / §8 prose beyond §1 task statement + §2 contracts |
| Re-audit | No prior audit revision for this plan |

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|-------|--------|
| Context map path | Present — `.dev/plans/mvp-phase6-mvp-plus/context-map.md` |
| SHA comparison | **diverged** — scout `ee87002` ≠ HEAD `e2aadc6`. All §File map `direct` source paths touched by phase 6 differ on HEAD: `aria/protocols/mcp/server.py`, `aria/orchestration/scratch/graph.py`, `aria/cli/commands/query.py`, `api/routers/query.py`, `aria/services/compliance_query.py`, plus new `aria/services/orchestrated_query.py`. |
| Working tree at audit | **clean** |
| Working tree at scout | dirty (`?? .dev/plans/`) — in-scope source was clean; plans now tracked |
| Scout grep coverage | §Coupling surfaces records `orchestration.scratch`, `MCPToolPortsAdapter`, `ComplianceQueryRequest`, `record_agent_execution`, `CANONICAL_SCRATCH_*`, MCP tool names — aligns with orchestrator §5.4 vocabulary. No `scout-incomplete`. |
| Plan §8 closure SHA | Plan records `2248f92` with **invalid** handoff; **superseded** by `e2aadc6` (T2 landed) but plan §8 **not updated** on HEAD — see F-02 |

### Plan-artifact provenance (`git show HEAD:<path>`)

| Artifact | Status |
|----------|--------|
| `.dev/plans/mvp-phase6-mvp-plus/context-map.md` | present-in-HEAD |
| `.dev/plans/mvp-phase6-mvp-plus/plan.md` | present-in-HEAD (§8 still describes pre-`e2aadc6` state) |
| `.dev/plans/mvp-phase6-mvp-plus/packets/T{1..5}.md` | present-in-HEAD |
| `.dev/decision-logs/T2-mcp-adapter-wiring.md` | present-in-HEAD (`e2aadc6`) |
| `aria/services/orchestrated_query.py` | present-in-HEAD (`e2aadc6`) |
| `tests/unit/test_mcp_adapter.py` | present-in-HEAD (`e2aadc6`) |
| `aria/protocols/mcp/server.py` (`index_vectors` → `index_chunks`) | present-in-HEAD (`e2aadc6`) |
| `aria/services/compliance_query.py` (T1 DTOs) | present-in-HEAD (`a387091`) |
| `aria/orchestration/scratch/graph.py` (T3 per-step rows) | present-in-HEAD (`b2ff729`) |
| `aria/cli/commands/query.py`, `api/routers/query.py` | present-in-HEAD (`e2c725a`) |
| `.dev/demo/aria-mvp-demo.sh`, README `## Demo`, MVP_PICKUP Phase 6 | present-in-HEAD (`2248f92`) |
| `.dev/demo/aria-mvp-demo.cast` | absent-from-disk (optional per plan — OK) |
| Prerequisite plans (T1 KC3) | present — phase 1–4 + phase 5 **Complete** |

### Findings filed in Phase 0.5

| ID | Severity | Type | Summary |
|----|----------|------|---------|
| F-01 | major | context-map-stale | Scout SHA `ee87002` ≠ HEAD `e2aadc6` on all direct §File map implementation paths (implementation expected; stale-qualified scout predictions below). |

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|----------|----------|--------|
| Context map | Yes | Stale SHA; direct files all changed on HEAD |
| Plan §1 + §2 | Yes (Phase 0) | Full plan §4–§8 read after Phase 0 pin |
| Packets T1–T5 | Yes | |
| Decision log T2 | Yes | |
| CHANGELOG `mvp-phase6-mvp-plus` | Yes | |
| Code / diff | Yes — `a387091^..e2aadc6` + HEAD reads | |
| Tests | Yes — `pytest tests/unit -q` (128 pass), trajectory eval (38 pass) | No live-stack wet run |

Phase 0 completed before narrative artifacts except §1 task statement and §2 contracts (read from plan header during initial open).

---

## 4. Cold-read log (Phase 0 — pinned)

1. **`test_mcp_adapter_construction`** builds `MCPToolPortsAdapter(mcp_server=...)` directly; does not invoke **`build_mcp_adapter`**, while §2 ties that test name to factory round-trip.
2. **`run_orchestrated_query`** always returns **`sources=[]`** and **`aria_mode="live"`** in `ComplianceQuerySuccess`; API uses **`X-ARIA-Mode: orchestrated-live`** only on the HTTP response — CLI `--json` consumers see `aria_mode: live` on orchestrated success.
3. No unit test runs **`run_orchestrated_query`** success path (graph mocked or live).
4. Commit **`e2aadc6`** (`mvp phase 6`) includes files outside any T1–T5 packet scope (four retrospective markdown files, `.dev/demo-openapi-browser-adjunct.md`) alongside T2 code.
5. At HEAD, **`aria/services/orchestrated_query.py`** exists and **`pytest tests/unit`** passes, but **plan §8** still states T2 is uncommitted and handoff is invalid — narrative/code mismatch at same SHA.

---

## 5. Findings table

| ID | Sev | Type | Phase | Subtask | One-line description |
|----|-----|------|-------|---------|----------------------|
| F-01 | major | context-map-stale | 0.5 | — | Scout commit `ee87002` diverged from HEAD on all direct implementation paths |
| F-02 | major | decision-log-stale | 1 | plan §8 | §8.1–§8.3 assert T2 missing / invalid handoff at `2248f92`; HEAD `e2aadc6` contains full T2 |
| F-03 | minor | process-violation | 1 | T2 | `e2aadc6` bundles phase 4/5 retrospectives + OpenAPI adjunct doc with T2 artifacts |
| F-04 | minor | contract-violation | 2 | T2 | `test_mcp_adapter_construction` does not exercise `build_mcp_adapter` |
| F-05 | minor | contract-violation | 2 | T4 | `api/routers/query.py` docstring still claims `ARIA_PLACEHOLDER_API=true` is default (G8 flip) |
| F-06 | minor | coverage-gap | 5 | T4 | No unit test for API HTTP 400 when `orchestrated=true` + placeholder (CHANGELOG deferred) |
| F-07 | minor | coverage-gap | 5 | T2 | No `run_orchestrated_query` success-path unit test (CHANGELOG deferred) |
| F-08 | observation | — | 1 | T5 | No committed `aria-mvp-demo.cast` (optional per plan) |
| F-09 | observation | — | 1 | — | Plan **Status** still **Active**; should advance after §8 refresh |

---

## 6. Detailed findings (above minor)

### F-01 — context-map-stale (major)

**Expected:** Context map provenance matches HEAD or plan §0 documents acceptable staleness for unchanged surfaces.  
**Found:** Scout at `ee87002`; HEAD `e2aadc6`. Every `direct` implementation file in §File map differs. Plan §0 pre-acknowledged orchestration/MCP surfaces would change; staleness does not invalidate code review but **downgrades** scout-only predictions on those paths.  
**Evidence:** `git diff ee87002..HEAD --name-only` on direct paths listed in §2 provenance.

### F-02 — decision-log-stale (major)

**Expected:** Plan §8 closure tree matches HEAD artifacts and verification results.  
**Found:** Plan lines 4, 307–323, 331–336, 371 still describe **T2 absent**, **invalid handoff**, clean checkout **pytest failure** at `2248f92`, and `index_vectors` **stub at HEAD**. At **`e2aadc6`**, `aria/services/orchestrated_query.py`, `tests/unit/test_mcp_adapter.py`, decision log, and real `index_vectors` are committed; `pytest tests/unit -q` → **128 passed**.  
**Evidence:** `git show HEAD:aria/services/orchestrated_query.py`; plan `.dev/plans/mvp-phase6-mvp-plus/plan.md` §8.1–§8.3; cold-read item 5.

**Action:** Refresh §8.1 closure SHA to `e2aadc6`, update artifact table rows 4/6/7/8, set **Status: Complete**, record binding `pytest` result. Do not merge-archive plan with §8 contradicting HEAD.

---

## 7. Adversarial test log (Phase 4)

**Focus 1 — Integration seam: orchestrated routing (required)**  
| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| CLI live + `--orchestrated` | `run_orchestrated_query` after `connect_app_dependencies(strict=True)` | `aria/cli/commands/query.py:91-92` | **pass** |
| API `orchestrated=true` live | Same service entry | `api/routers/query.py:57-58` | **pass** |
| Factory wiring | `build_mcp_adapter(conns)` → `MCPServer(neo4j, vector_store)` | `orchestrated_query.py:17-19` | **pass** |
| Graph execution | `build_default_graph().execute(state, adapter)` | `orchestrated_query.py:45-46` | **pass** (no success-path test) |
| `execution_trace` on response | `result.to_trace_dict()` when success | `orchestrated_query.py:62` | **pass** (structure untested E2E) |

**Focus 2 — Failure paths: placeholder + missing deps**  
| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| CLI placeholder + orchestrated | Exit 1; frozen stderr | `query.py:78-83`; `test_orchestrated_cli_smoke_placeholder_blocked` | **pass** |
| API placeholder + orchestrated | HTTP 400; frozen `detail` | `query.py:46-54` — byte-equal to §2 | **pass** (no automated API test — F-06) |
| Missing Neo4j/Chroma | `ComplianceQueryUnavailable` + deps list | `orchestrated_query.py:31-35`; `test_run_orchestrated_query_missing_deps_returns_unavailable` | **pass** |
| Graph/node failure | Unavailable with `state.error` | `orchestrated_query.py:49-53` | **unknown** (no test) |

**Focus 3 — Coupling surfaces (from context map)**  
| Surface | Scout | Check | Result |
|---------|-------|-------|--------|
| 1 ToolPorts ↔ MCPToolPortsAdapter | confirmed | async methods align; unit graph tests pass | **pass** |
| 7 hybrid vs vector-only | suspected | `free_query_node` still vector-only; Flag 1 non-goal | **ruled-out** (by design) |
| 8 Placeholder gate | confirmed | frozen literals in CLI/API | **pass** |
| 9 X-ARIA-Mode | confirmed | `orchestrated-live` when orchestrated; no eval enum test | **pass** |
| 10 index_vectors stub | suspected | `index_chunks` + `test_index_vectors_delegates_to_vector_store_index_chunks` | **verified** |

**Regression:** `pytest tests/eval/test_trajectory_eval.py` — **38 passed** (T4 kill criterion).

---

## 8. Coverage gap list (Phase 5)

| Priority | Gap | Subtask | Notes |
|----------|-----|---------|-------|
| Medium | API placeholder + `orchestrated=true` → 400 | T4 | Deferred in CHANGELOG; CLI smoke only |
| Medium | `run_orchestrated_query` success with mocked graph | T2/T4 | Deferred in CHANGELOG |
| Low | `build_mcp_adapter` via named contract test | T2 | F-04; construction path covered in production code |
| Low | Per-step telemetry partial write failure (N of N+1) | T3 | Deferred in CHANGELOG |
| Low | Demo script / shellcheck / asciicast | T5 | Manual per plan |
| Low | DTO field round-trip without routing | T1 | Deferred to T4 path |

Kill criteria with explicit CHANGELOG deferrals are **not** escalated to process-violation (orchestrator documented the tradeoff).

---

## 9. Intent traceability (Phase 1 summary)

| Layer | Assessment |
|-------|------------|
| Task statement → code | **Met** — MCP adapter factory, orchestrated CLI/API routing, per-step telemetry, demo script + README + pickup checkboxes |
| Non-goals | **Respected** — no GraphRAG parity in scratch graph, no new route, no SQLite schema change |
| Packet files vs diff | T1–T5 core files match packets; **extra** files only in `e2aadc6` (F-03) |
| §2 contracts | **Mostly met**; F-04/F-05/F-06 gaps as above |
| Cold read vs narrative | **F-02** — plan §8 conceals post-`e2aadc6` reality; CHANGELOG T2 bullet matches code |
| Prerequisite gate (Flag 6) | Phases 1–4 plans **Complete** at audit time |

---

## 10. Decision log audit (Phase 3)

**T2-mcp-adapter-wiring.md** — Chosen approach (factory module, lazy `build_default_graph`, `index_chunks`) **matches** implementation. Deferred items (T3/T4 routing, success E2E) **landed** in later commits. No rejected alternative partially implemented.

**Stale prose:** Plan §8 and appendix `documented_mess_up_to_cover_for_in_retro_method` remain as **historical** record of the T2 commit ordering incident; must not be read as current HEAD state without F-02 banner update.

---

## 11. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| ToolPorts ↔ MCPToolPortsAdapter signature drift | confirmed coupling | verified | — |
| Per-step `orchestration.scratch/{node}` naming | ambiguity Flag 3 | verified | T3 |
| Factory in `orchestrated_query.py` | ambiguity Flag 2 | verified | T2 |
| `orchestrated` body field on DTO | ambiguity Flag 5 | verified | T1/T4 |
| MCPToolPortsAdapter untested | ambiguity Flag 4 | verified | `test_mcp_adapter.py` |
| Semantic parity GraphRAG vs vector-only | ambiguity Flag 1 | ruled-out | intentional per §0 |
| `index_vectors` stub | Surface 10 suspected | verified | `index_chunks` |
| Placeholder gate undefined | Surface 8 | verified | T4 |
| X-ARIA-Mode enum break | Surface 9 suspected | ruled-out | grep: no closed enum in eval tests |
| hybrid_retrieve unused in scratch | Surface 7 suspected | ruled-out | Flag 1 decision |
| Prerequisite phases green | Flag 6 | verified | plan statuses |
| Demo artifact path | Flag 7 | verified | `.dev/demo/aria-mvp-demo.sh` |
| AppConnections strict non-None | §5.2 #1 | not-tested | wet-run only |
| Phase 4 exact key equality on `_success_payload` | §5.4 #5 suspected | verified | placeholder JSON test passes |

---

## 12. Verdict

**`pass-with-conditions`**

Implementation at **`e2aadc6`** satisfies Phase 6 intent: orchestrated routing, live MCP adapter wiring, per-step telemetry, demo artifacts, and **128** unit tests + **38** trajectory eval tests pass. No critical or blocking code defects found on cold read.

**Conditions before treating the plan as closed:**

1. **F-02 (required):** Update plan §8 to closure SHA `e2aadc6`, valid handoff, and **Status: Complete**; strike or banner-supersede stale “T2 missing” rows.
2. **F-05 (recommended):** Fix API `compliance_query` docstring default for `ARIA_PLACEHOLDER_API` to match G8 (`false` default).
3. **F-04 / F-06 / F-07 (optional):** Tighten `test_mcp_adapter_construction` to call `build_mcp_adapter`; add API placeholder 400 test if deferral is no longer acceptable.
4. **F-03 (process):** Note in methodology retro that `e2aadc6` mixed T2 with unrelated retrospective/adjunct docs — prefer T2-only commit or separate docs commit.

**Not merge-blocking:** F-01 (expected map staleness), deferred coverage gaps documented in CHANGELOG, missing optional asciicast.

---

## 13. Finding status vs prior revision

N/A — initial audit.
