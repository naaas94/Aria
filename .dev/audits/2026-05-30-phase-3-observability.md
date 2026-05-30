# Audit: phase-3-observability

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-30  
**Auditor:** Composer (auditor-review v0.4)  
**Plan:** `.dev/plans/phase-3-observability/plan.md` v1.1 · Status Complete  
**Closure HEAD:** `a6849a2267bb7d023dc3f98fe2284e4827651d08`  
**Implementation SHA (T1–T8 code):** `a247cfeedd76a74c9b27cb20cc03e171f283861e2`

---

## 1. Audit metadata

| Field | Value |
|-------|--------|
| Task name | phase-3-observability (MVP Phase 3 — G5/G6 observability) |
| Context map | `.dev/plans/phase-3-observability/context-map.md` — **present** |
| Readiness at planning | CONDITIONAL (resolved in plan §0) |
| Phase 0 discipline | Completed before narrative artifacts (plan prose beyond §1/§2, changelog, §8 narrative, decision logs) |
| Pytest (auditor run at HEAD) | `pytest tests/unit/test_metrics.py tests/test_llm_telemetry.py tests/test_middleware_telemetry.py tests/test_telemetry_store.py tests/unit/test_graph_client.py -q` → **56 passed** |

**Adversarial focus (2 areas):**

1. **Integration seams** (mandatory) — seeded from context map §Coupling surfaces (six surfaces); verifies G6 `source="llm"`, shared `INGESTION_DURATION`, cost NULL vs Prometheus counter, `request_id` rollup, import registration.
2. **Failure paths** — SQLite write failure on LLM paths; Neo4j session failure before histogram observe; telemetry middleware try-block behavior.

**Integration seams waiver:** Not applicable — six confirmed/suspected couplings in the context map.

---

## 2. Provenance log

| Check | Result |
|-------|--------|
| Context map path | `.dev/plans/phase-3-observability/context-map.md` |
| Scout SHA (map header) | `ee87002297a495389b9bc79a510966dd30ab23f7` |
| Audit-time HEAD | `a6849a2267bb7d023dc3f98fe2284e4827651d08` |
| SHA comparison | **diverged** (expected post-T1–T8) |
| Diverged §File map `direct` rows | `aria/llm/client.py`, `aria/observability/metrics.py`, `api/middleware_telemetry.py`, `aria/graph/client.py`, `aria/ingestion/pipeline.py`, `aria/observability/telemetry_store.py`, `README.md`, `.env.example`, `tests/unit/test_metrics.py`, `tests/test_llm_telemetry.py`, `tests/test_middleware_telemetry.py`, `tests/test_telemetry_store.py` |
| Working tree at audit | **clean** |
| Scout-time dirty paths | `?? .dev/plans/` only (no in-scope app files) — no `dirty-state caveat` on implementation findings |
| Scout grep coverage | Patterns in map §Coupling surfaces cover plan §5.4 vocabulary — **no `scout-incomplete`** |
| Plan §8 closure SHA vs HEAD | Plan §8.1 cites closure at HEAD when v1.1 Complete; implementation code at `a247cfe` (parent of closure commit `a6849a2`) |

### Plan-artifact provenance (`git show HEAD:<path>`)

| Artifact | Status |
|----------|--------|
| `context-map.md` | present-in-HEAD |
| `plan.md` (v1.1 + §8) | present-in-HEAD |
| `packets/T1.md` … `T8.md` | present-in-HEAD |
| `CHANGELOG.md` § phase-3-observability | present-in-HEAD |
| All §8.2 implementation paths | present-in-HEAD |
| `tests/unit/test_graph_client.py` | present-in-HEAD (not in T8 packet file list; see P3-F02) |

**Provenance findings filed here:** P3-F01 (`context-map-stale`, major, expected at closure).

---

## 3. Context chain completeness

| Artifact | Provided | Notes |
|----------|----------|-------|
| Context map | Yes | §Post-execution marks scout predictions stale-qualified |
| Plan §1–§8 | Yes | v1.1 Complete with auditor handoff |
| Packets T1–T8 | Yes | All in HEAD |
| Shared contracts §2 | Yes | Verified against code |
| Decision logs | N/A | Plan §2: no architectural tier — correct |
| CHANGELOG | Yes | `CHANGELOG.md` § phase-3-observability |
| Code / diff | Yes | `84f117b..HEAD` (11 commits T1–closure) |
| Tests | Yes | 56 passed at HEAD |
| Pre-plan / roadmap | Via `MVP_PICKUP.md` §189–195 | Checkboxes still open (P3-F03) |

---

## 4. Cold-read log (Phase 0 — pinned)

Conducted against task statement + §2 contracts + `84f117b..HEAD` diff/tests only.

| ID | Severity (guess) | Item |
|----|------------------|------|
| CR-1 | minor | T8 landed `tests/unit/test_graph_client.py` while plan §4 T8 says “no new test files” |
| CR-2 | minor | `test_skipped_duplicate_does_not_record_duration` — must confirm early `SKIPPED_DUPLICATE` return skips observe (verified in Phase 4: **passes**) |
| CR-3 | observation | `LLM_COST_COUNTER._name` in tests is `aria_llm_cost_usd` (Prometheus strips `_total`); registry key is `aria_llm_cost_usd_total` — consistent |
| CR-4 | minor | No test spies `latency_ms / 1000.0` on HTTP histogram |
| CR-5 | observation | Parse-error returns occur before `_ingest_start` — no `INGESTION_DURATION` on parse failure (matches T5 kill criteria) |
| CR-6 | observation | G6 warning string in `llm/client.py` matches §2; middleware retains distinct string (`telemetry middleware write failed`) — pre-existing, out of T2 scope |

**Narrative reconciliation (Phase 1):** Plan §8.4 and CHANGELOG acknowledge CR-1, CR-4, and MVP_PICKUP gap — no `narrative-concealment`.

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| P3-F01 | major | context-map-stale | 0.5 | — | Scout SHA `ee870022` ≠ HEAD; all direct file-map rows diverged (expected after T1–T8) |
| P3-F02 | minor | prediction-divergence | 1 | T8 | Extra test file `tests/unit/test_graph_client.py` not in packet/plan §4 T8 file list; coverage equivalent to planned graph histogram tests |
| P3-F03 | minor | intent-drift | 1 | closure | `MVP_PICKUP.md` §191–192 G5/G6 checkboxes still `[ ]` despite shipped code; plan §8.4 defers to Phase 5 hygiene |
| P3-F04 | minor | coverage-gap | 5 | T8/T6 | No test for mixed null + non-null `cost_usd` rows per `request_id` for `cost_by_request` (CHANGELOG deferred) |
| P3-F05 | minor | coverage-gap | 5 | T3/T8 | No assertion that HTTP histogram `observe` receives seconds (`latency_ms / 1000.0`) — CHANGELOG deferred |

---

## 6. Detailed findings (above minor)

### P3-F01 — context-map-stale (major)

**Expected:** Context map reflects pre-implementation state at scout SHA for planning.  
**Found:** HEAD `a6849a2` is 11 commits ahead of scout `ee870022` on every `direct` file-map row.  
**Evidence:** `git diff ee870022 HEAD` on all direct paths non-empty.  
**Impact:** Scout §Interface inventory rows describing “planned symbols not present” are obsolete. Plan §Post-execution and §8 instruct auditors to verify at closure/implementation SHA.  
**Action:** Re-scout only if orchestrator needs fresh prediction set; **does not block merge** when verification used HEAD + plan §8.3 evidence (this audit did).

---

## 7. Adversarial test log

### Integration seams (context map §Coupling surfaces)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Surface 1: `TELEMETRY_WRITE_ERRORS` `source="llm"` | Exact label; warning + counter on SQLite failure | `aria/llm/client.py` both `record_llm_call` sites; tests `test_sqlite_write_failure_*` | **passes** |
| Surface 2: `INGESTION_DURATION` shared histogram | Pipeline uses `pdf`/`html`; HTTP uses `text`/`file`; no unification | `pipeline.py` observes `fmt.value`; `ingest.py` untouched per non-goals | **passes** |
| Surface 3: NULL `cost_usd` vs counter | Counter not incremented when cost absent; docs explain Ollama | `if cost is not None: LLM_COST_COUNTER...`; README + `.env.example` | **passes** |
| Surface 4: `request_id` correlation | `cost_by_request` uses same `request_id` string as `record_llm_call` | SQL `WHERE request_id = ?`; multi-row sum test `req-C` | **passes** |
| Surface 5: HTTP histogram without `path` | `method` + `status_code` only | `HTTP_REQUEST_DURATION` labels match §2 | **passes** (suspected coupling ruled out) |
| Surface 6: Prometheus import registration | Metrics registered before scrape | `middleware_telemetry` imports `HTTP_REQUEST_DURATION`; `telemetry.py` F401 import of `metrics` | **passes** |

### Failure paths

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| LLM SQLite failure on success path | Completion returns; G6 counter + warning; LLM Prometheus metrics still increment | Code order: except G6 → then `LLM_CALL_COUNTER` / `LLM_COST_COUNTER` outside try | **passes** |
| LLM SQLite failure on final error path | Exception propagates; G6 counter incremented | `test_sqlite_write_failure_on_error_path_increments_error_counter` | **passes** |
| Neo4j `session()` raises before observe | Exception propagates; no silent swallow | `observe` after `async with session` | **passes** |
| HTTP telemetry store write fails | Counter error `http_middleware`; duration not observed (same try) | Existing middleware pattern unchanged for duration placement | **passes** |

---

## 8. Coverage gap list (prioritized)

| Priority | Gap | Kill criterion / flag | Mitigation |
|----------|-----|----------------------|------------|
| Low | Mixed null/non-null `cost_usd` per `request_id` | CHANGELOG T8 deferral | Add one `test_telemetry_store` row when SQL semantics need lock-in |
| Low | HTTP histogram unit conversion | CHANGELOG T3/T8 deferral | Spy `observe` args or golden sample value band |
| Low | `MVP_PICKUP.md` checkbox sync | Plan §8.4 open item | Phase 5 hygiene PR |
| — | G6 `TELEMETRY_WRITE_ERRORS` for llm | Scout Flag 4 | **Closed** by T8 tests |

All plan §4 kill criteria for T1–T8 have corresponding automated or grep evidence at HEAD.

---

## 9. Intent traceability (Phase 1 summary)

| Layer | Assessment |
|-------|------------|
| Task statement → code | G5 metrics defined and wired at middleware, graph, pipeline, LLM; G6 swallows removed (`grep`: zero `except Exception: pass` in `client.py`); `cost_by_request` store-only; Ollama docs in README + `.env.example` |
| Non-goals | `/telemetry` JSON unchanged; `ingest.py` untouched; no `path` label; no agent/retrieval/MCP new metrics |
| Packet files-to-touch → diff | T1–T7 match; T8 adds `test_graph_client.py` (P3-F02) |
| §2 contracts | Metric names, buckets, labels, G6 envelope, `cost_by_request` signature match shipped code |
| §5 adversarial items | Plan §8.4 marks all §5.2/§5.3/§5.4 items **closed** — verified at HEAD |

---

## 10. Contract compliance (Phase 2 summary)

| Contract row | Status |
|--------------|--------|
| `HTTP_REQUEST_DURATION` | Frozen definition in `metrics.py:105-109`; wired `middleware_telemetry.py:62-65` |
| `GRAPH_QUERY_DURATION` | `metrics.py:112-116`; `graph/client.py` read/write |
| `LLM_COST_COUNTER` | `metrics.py:119-122`; increment when `cost is not None` |
| `TelemetryStore.cost_by_request` | `telemetry_store.py:291-302`; four store tests |
| G6 error envelope | `source="llm"`, warning `"telemetry store write failed: %s"` + `type(exc).__name__` |
| Literal-string parity | Prometheus names byte-equal to §2; G6 warning string byte-equal in `llm/client.py` |
| Tests policy | Delta helpers; unit/mock only; 56 passed |

---

## 11. Decision log audit (Phase 3)

No architectural-tier subtasks; no decision logs required. **No process finding.**

---

## 12. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Missing `HTTP_REQUEST_DURATION` / graph / LLM cost metrics | suspect_modified | verified | — |
| `TELEMETRY_WRITE_ERRORS` not used in `llm/client.py` | suspect_modified | verified (fixed) | — |
| `INGESTION_DURATION` not observed in `pipeline.py` | suspect_modified | verified (fixed) | — |
| Silent `except Exception: pass` in `llm/client.py` | ambiguity / coupling | verified (removed) | — |
| Optional `cost_by_request` | ambiguity Flag 3 | verified | — |
| `TELEMETRY_WRITE_ERRORS` no llm tests | ambiguity Flag 4 | verified (T8) | — |
| Ollama docs README **or** `.env.example` | ambiguity Flag 5 | verified (both) | — |
| HTTP `path` label cardinality | suspected coupling | ruled-out | plan chose method+status_code |
| T8 “no new test files” | plan spec | prediction-divergence | P3-F02 |

---

## 13. Verdict

**`pass-with-conditions`**

Implementation matches plan §1 intent and §2 contracts. G5/G6 gaps from `MVP_PICKUP.md` are closed in code and tests at HEAD. No critical or major **code** defects.

**Conditions (minor — fix or explicitly accept before Phase 5 sign-off):**

1. **P3-F03:** Sync `MVP_PICKUP.md` §191–192 checkboxes (or add cross-link in plan closure that audit accepted deferral).
2. **P3-F04 / P3-F05:** Optional follow-up tests if you want CHANGELOG-deferred gaps closed in CI rather than documented-only.

**Does not block merge:** P3-F01 (stale context map is expected; verification used HEAD + §8.3). P3-F02 (documented test-file split with equivalent coverage).

---

## 14. Finding status vs prior revision

N/A — initial audit.
