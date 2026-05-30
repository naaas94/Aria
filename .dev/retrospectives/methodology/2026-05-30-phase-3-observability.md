# Methodology retrospective — phase-3-observability

## 1. Task identifier

**Task:** phase-3-observability (MVP Phase 3 — G5/G6 observability: Prometheus histograms/counter, LLM G6 swallows, pipeline `INGESTION_DURATION`, store-only `cost_by_request`, Ollama docs)  
**Date:** Context map 2026-05-25 · execution/audit/closure 2026-05-30  
**Plan versions:** v1.0 → v1.1 (§8 auditor handoff, Status Complete)  
**Skills:** pre-plan-exploration v0.2, orchestrator-planning, executor-subtask-execution, auditor-review v0.4  
**One line:** Close `MVP_PICKUP.md` G5/G6 gaps with frozen §2 metrics, wire sites T2–T5, rollup T6, docs T7, unit tests T8; single-pass audit `pass-with-conditions`; no amendment wave.

---

## 2. Plan vs reality

### DAG vs execution

- **Planned:** T1 → `{T2,T3,T4,T5}` parallel → T8; `{T6,T7}` parallel off critical path (no T1 dep).
- **Actual commit order:** T1 (`a140945`) → T2/T3/T5/T4 (`cbb884b`, `139f4c0`, `c89493b`, `4f1ac58`) → T6 (`5a98ba9`) → T7 docs + changelog (`4fd0df8`, `fef97b0`) → T8 (`a247cfe`) → closure (`a6849a2`) → post-closure tip (`fae6b0c`).
- **Sequencing:** Serial executor session, not parallel agents; disjoint files — no merge conflicts. T4 landed after T5 in git but both only depend on T1 — safe.
- **Unsafe parallelization:** None observed.

### Contracts at implementation surface

| §2 surface | Enforced in code + test? | Notes |
|------------|-------------------------|-------|
| `HTTP_REQUEST_DURATION` | Yes | `TestPhase3MetricDefinitions`, middleware + `test_http_request_duration_histogram_observed` |
| `GRAPH_QUERY_DURATION` | Yes | `metrics.py` + `test_graph_client.py` / `TestGraphQueryDurationHistogram` |
| `LLM_COST_COUNTER` | Yes | Cost present/absent paths in `test_llm_telemetry.py` / `TestLLMCostCounter` |
| `TelemetryStore.cost_by_request` | Yes | Three store tests + multi-row `req-C`; **no** mixed null+non-null per `request_id` (P3-F04, CHANGELOG deferred) |
| G6 error envelope `source="llm"` | Yes | Both `record_llm_call` sites; grep zero `except Exception: pass` in `client.py` |
| HTTP observe seconds | Partial | Code uses `latency_ms / 1000.0`; **no** test spies unit conversion (P3-F05, CHANGELOG deferred) |
| T7 docs (README + `.env.example`) | Yes (manual) | No automated doc-sync test — plan-acceptable for `trivial` tier |
| Decision log paths | N/A | No architectural tier — correct |

No hollow-contract window comparable to phase-2’s “unit file exists but CI never runs it”: Phase 3 tests ride existing PR pytest surfaces; 56 passed at audit HEAD.

### §2 / narrative vs later subtasks

- **No decision logs** — nothing to drift.
- **§0 flag resolutions** (HTTP labels, store-only rollup, Flag 4 G6 tests) survived in packets and landed code; T5 packet carried `fmt.value` verbatim — highest re-plan risk did not misfire.
- **Plan §4 T8 “no new test files”** vs **T4 commit** adding `tests/unit/test_graph_client.py` — prediction drift; plan §8.4 and audit P3-F02 document it; not repaired by renaming, correctly treated as equivalent coverage.
- **CHANGELOG T2/T5 “deferred to T8”** — honest staging; T8 closed G6 and pipeline histogram gaps. Not stale narrative after T8.

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T7 | trivial | OK — docs-only |
| T1–T6, T8 | standard | OK — production wiring + tests; none needed `architectural` given frozen §2 |
| (none) | architectural | Correctly absent — no decision-log requirement |

### Closure vs committed reality

- **Implementation SHA (T1–T8 code):** `a247cfe` — ancestor of HEAD; pytest 56 passed per plan §8.1 and audit.
- **Closure commit:** `a6849a2` — plan v1.1 + §8 + context-map §Post-execution; **is** ancestor of current HEAD (`fae6b0c`).
- **Audit HEAD:** `a6849a2` at initial audit — matches closure commit; working tree clean — **no** phase-2-style F-01 “§8 on disk but not in HEAD”.
- **§8.1 dual-SHA pattern:** Implementation vs closure split is explicit and correct; auditor verified code at `a247cfe`, artifacts at closure `a6849a2`.
- **Post-closure:** `fae6b0c` (“mvp phase 3 completedn”) is one commit after closure — plan/audit not re-run; hygiene only.
- **Context map scout SHA** `ee870022` stale vs HEAD — expected (P3-F01); §Post-execution stale-qualified; audit used HEAD + §8.3, not scout inventory.
- **MVP_PICKUP.md G5/G6 checkboxes** still `[ ]` at audit — deferred in plan §8.4 / CHANGELOG (P3-F03); latent until Phase 5 hygiene.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Count: 0** formal HALTs in commits, changelogs, or packet Landed sections.

| Situation | HALT? | Assessment |
|-----------|-------|------------|
| T2 grep for `except Exception: pass` (§5.2 #1) | No | Correct — pattern-based edit, both sites replaced |
| T5 timer placement (§5.3) | No | Correct — completion-only observe; SKIPPED_DUPLICATE test passes |
| T8 importability of T1–T6 | No | Correct — full test surface green |
| T4 added `test_graph_client.py` while T8 packet says three files only | No | **Prediction divergence**, not HALT — should have been flagged in T4 changelog/plan §6 as forward split |
| G6 tests deferred T2→T8 | No | **Documented deferral** in CHANGELOG per tiered changelog norm — not silent improvisation |
| MVP_PICKUP checkbox sync at closure | No | **Explicit deferral** — audit condition, not kill-criteria violation |

**HALT-shaped improvisation:** None material. Deferred tests were named in CHANGELOG before T8 landed.

### Amendment cycles

**Count: 0** — plan §7 empty; audit `pass-with-conditions` without T7-shaped amendment subtasks.

- **First audit pass** sufficient for substantive intent; conditions are minor (roadmap checkboxes, optional tests).
- **No re-audit** recorded; not required for merge per audit §13.
- **Architectural-tier task with zero amendments:** First pass genuinely clean on code/contracts; audit signal caught doc/checkbox hygiene only.

---

## 4. Adversarial pass calibration

### Rejected alternatives that mattered later

- **Merge T2–T5 (Alt A):** Rejected — parallel file split worked; no partial-edit commit observed.
- **Merge T6 into T8 (Alt B):** Rejected — T6 production diff reviewable alone; correct.
- **Expose rollup via `/telemetry` JSON (Alt C):** Rejected — store-only shipped; no endpoint contract churn; validated in audit seams.

### Load-bearing assumptions

| Assumption | Held? |
|------------|-------|
| LLM swallow sites findable by grep, not line numbers | Yes |
| `INGESTION_DURATION` labels still `["format"]` | Yes |
| `query_name` read/write alignment counter ↔ histogram | Yes |
| `TelemetryStore._conn` / `_lock` | Yes |
| Import-order registration for new metrics | Yes (middleware import) |
| Float `Counter.inc(cost)` | Yes — `TestLLMCostCounter` |
| T8 TestClient vs `_SKIP_PATHS` | Yes — dedicated skip-path test |

### Highest re-plan risk (§5.3: T5)

- **Predicted:** Ambiguous timer placement across four exit paths; wrong label if Flag 1 misread.
- **Actual:** Landed cleanly in one commit (`c89493b`); no re-plan, no HALT. Technical risk did not materialize.
- **Trouble elsewhere:** Test-file split (T4 vs T8 plan wording) and roadmap checkbox deferral — process/documentation, not T5 structure.

---

## 5. Methodology gaps surfaced

### Orchestrator should have prompted for…

- **Align T4 and T8 file-touch lists** when graph histogram tests logically belong in a dedicated module — avoids §4 “no new test files” vs T4 `test_graph_client.py` contradiction (P3-F02).
- **MVP_PICKUP sync** as explicit closure subtask or kill criterion when task statement cites §189–195 — deferral is fine if named upfront in §1 closure criteria, not only post-audit.
- **Optional §2 row for “deferred test” staging** when T2 ships before T8 — phase 3 used CHANGELOG well; a §2 footnote could make the hollow window visible to auditors without reading tiered changelog.

### Executor should have blocked or escalated…

- nothing notable — execution matched packets; grep-driven T2/T5 matched kill criteria discipline.

### Contracts schema missing or vestigial

- **§4 T8 “no new test files”** vestigial when T3/T4 already extend `test_middleware_telemetry.py` / create `test_graph_client.py` — “no new test files” read as “no *additional* files beyond extensions” but T4 created one; schema should say “prefer extending existing files; new file only when domain split justified (record path in changelog).”
- **Implementation SHA vs closure SHA** in §8 — worked well here; worth standardizing in orchestrator template after phase-2 F-11 pain.

*Do not edit skills from this file.*

---

## 6. Single sentence verdict

**Yes, with minor leaks:** The DAG, frozen §2 contracts, packet kill criteria, tiered changelog deferrals, clean closure commit before audit, and single-pass `pass-with-conditions` audit held up; methodology leaked only on predictable hygiene (unchecked `MVP_PICKUP` boxes) and a T4/T8 test-file plan contradiction that was caught and accepted, not hidden.
