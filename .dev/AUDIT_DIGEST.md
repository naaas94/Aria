# Audit digest — validated findings and action plan

**Date:** 2026-04-09 (updated 2026-04-10)  
**Source reports:** `api-contracts-errors-auth-audit.md`, `telemetry-audit.md`, `evaluation_ci_audit.md`, `product-architecture-audit.md`, `infrastructure-data-dependencies-audit.md`  
**Validation:** All P0/P1 findings were confirmed against the codebase at audit time (code-level cross-reference, not just report claims).

---

## Open and partial items

| Open | Item | Notes |
|------|------|--------|
| Open | **#2** Medium-tier retrieval goldens | All five `tests/eval/golden_set/cases/retrieval/*.yaml` still use `retrieved_context: ""`. The retrieval lens keyword-checks `expected_components` against that string — zero hits, guaranteed failure. Nightly “Golden set (all tiers)” uses `--golden-tier=slow` (includes `medium`). *Fix options:* populate synthetic `retrieved_context`, `expect.replay` fixtures, or skip/quarantine until wired to real retrieval. |
| Open | **#8** `requires_multi_hop` is a no-op | `run_retrieval_check` in `tests/eval/golden_set/runner.py` only sets `multi_hop_declared` when the flag is true; there is no validation of multi-hop retrieval (trace metadata, hop count, etc.). *Fix:* implement a real check or remove/rename the flag. |
| Partial | **#9** GraphRAG vs vector benchmark | `scripts/benchmark_retrieval.py` uses hardcoded strings and lexical scoring — not live retrieval quality. Docstring mentions “simulated contexts”; audit asked for an explicit **methodology stub** label in the header so nobody treats output as production evidence. *Follow-up:* stronger header disclaimer and/or wire to real retrievers behind a flag; use `tests/eval/e2e/` with a seeded graph for real decisions. |
| Open | **#18** CI step says “includes replay” | `.github/workflows/ci.yml` still labels the golden step as including replay while `replay/` has no real fixtures and no YAML uses `expect.replay`. *Fix:* rename the step or add a minimal replay golden. |
| Open | **#19** Nightly Python version gap | `.github/workflows/nightly.yml` pins Python 3.12; PR CI matrix runs 3.12 and 3.13. *Fix:* add 3.13 to nightly or document accepting the gap. |
| Open | **#20** LangGraph reference | `aria/orchestration/langgraph_reference/` uses stub nodes (`_NoopTools`); no tests import `build_langgraph()`. *Fix:* optional smoke test with `pytest.mark.skipif` or a short doc note that the package is illustrative only. |
| Partial | **#16** HTTP `/ingest/*` vs full pipeline | **Docs fixed:** module docstring on `api/routers/ingest.py`, README table, and “How to load documents” spell out that routes are chunking/metrics only — not Neo4j/Chroma/entity pipeline. **Still open (product):** optional wiring of full `ingest_document()` behind a flag, dry-run, or rename — only if product asks. |

---

## Cross-cutting themes (still relevant)

1. **Golden suite structure** — empty retrieval context (#2), misleading multi-hop flag (#8), and replay label drift (#18) are the main evaluation/CI honesty gaps.
2. **Benchmarks vs live quality** — synthetic lexical benchmarks (#9) are fine for smoke if labeled; GraphRAG “quality” claims belong on e2e + seeded data.
3. **CI parity** — nightly should either match PR Python coverage (#19) or the gap should be explicit in ops docs.

---

## Recommended execution order (remaining work)

| Priority | Item | Effort | Notes |
|----------|------|--------|--------|
| P0 | **#2** Retrieval goldens | S | Unblocks honest green runs for medium/slow tiers. |
| P1 | **#8** `requires_multi_hop` | S | Implement check or rename to avoid false confidence. |
| P2 | **#18**, **#19**, **#20** | XS–S | CI label, nightly matrix, LangGraph clarity. |
| P2 | **#9** Benchmark header | XS | Disclaimer / stub labeling only. |

---

## Fixed (resolved)

Summarized for history; details live in repo root `CHANGELOG.md` and code.

### P0

| # | Finding | Resolution |
|---|---------|------------|
| **1** | OpenAPI path set missing `/metrics`, `/telemetry` | Expected paths updated in security audit test, golden `openapi_paths.yaml`, and `tests/eval/expected_api_paths.py` (SSOT). |

### P1

| # | Finding | Resolution |
|---|---------|------------|
| **3** | `NEO4J_PASSWORD` default mismatch (`connections` vs `readiness`) | Same default as dev/docker (e.g. `aria_dev_password`) when unset; production should set explicitly. |
| **4** | `A2AClient` omitted `X-A2A-Secret` | Client sends header when `A2A_SHARED_SECRET` is set; tests cover 401/200 paths. |
| **5** | `/metrics` and `/telemetry` unauthenticated with API key | Routes use `require_api_key_for_observability`; `ARIA_OBSERVABILITY_PUBLIC` opt-out documented and tested. |
| **6** | Docs claimed only `/health` was public | `.env.example` and README list `/health` and `/ready` as unauthenticated; observability routes gated unless public flag. |
| **7** | Nightly ran goldens twice, overwrote reports | `pytest tests/eval/` uses `--ignore=tests/eval/golden_set` after the dedicated golden step. |

### P2

| # | Finding | Resolution |
|---|---------|------------|
| **10** | Silent `except` on telemetry / agent paths | Warning logs (type only) + `aria_telemetry_write_errors_total` by source. |
| **11** | No telemetry SQLite retention | `prune_older_than`, config env vars, background prune in lifespan, tests. |
| **12** | 413/422 JSON inconsistency | Middleware 413 includes `code`; `http_exception_handler` maps 413/422; telemetry 422 uses validation-shaped body. |
| **13** | Multi-worker story undocumented | README section on workers, dedup, SQLite telemetry fragmentation. |
| **14** | `/ready` opened new connections per request | Reuses app lifespan connections / `health_check()` on existing clients. |
| **15** | Unbounded `list_complete_content_hashes` | Replaced with targeted checks + paginated `iter_complete_content_hashes` for exports. |
| **17** | Scratch orchestration not in telemetry | `OrchestrationGraph.execute` records `agent_executions` + Prometheus as `orchestration.scratch`; unit tests. |
| **21** | Stale `docs/security_audit_report.md` hint in test failure | Assertion message points at golden YAML / `expected_api_paths` SSOT. |

### P3 (audit items 22–30)

| # | Finding | Resolution |
|---|---------|------------|
| **22** | Two ingest limits (middleware vs app) misaligned | `DEFAULT_INGEST_MAX_BYTES` (12 MiB) shared default; `.env.example` documents both vars. |
| **23** | `StepTrace.error` repeated after first failure | Error attached only on transition into error state. |
| **24** | Prometheus label cardinality | Documented in `aria/observability/metrics.py` module docstring. |
| **25** | `complete_structured` repair → two `llm_calls` rows | Documented on `LLMClient.complete_structured` (no schema change). |
| **26** | Eval JSONL without scrub | Central `tests/eval/scrub.py`; golden report and recorder use it; EvalRecord warns no secrets in YAML. |
| **27** | Duplicate OpenAPI path expectations | `EXPECTED_OPENAPI_PATHS` in `tests/eval/expected_api_paths.py`; golden YAML test matches SSOT. |
| **28** | Named-query RETURN tests only for `impact_by_regulation` | Additional contract tests for other stable named queries. |
| **29** | `--golden-tier=slow` / `tier: slow` confusing | Conftest help documents max tier, default `slow`, reserved slow tier. |
| **30** | 500 responses opaque | `request_id` on `ErrorBody`, `X-Request-ID` on 500 JSON response; middleware sets `request.state.request_id`; contract test. |

---

## Historical detail (optional)

The sections below preserve the original audit narrative for items that are now fixed. Use the **Fixed (resolved)** tables above as the source of truth for status.

<details>
<summary>Original P0 / P1 / P2 / P3 write-ups (archived)</summary>

### P0 — CI

**1. OpenAPI path expectations** — Fixed: `/metrics` and `/telemetry` in expected sets and SSOT.

**2. Medium-tier retrieval goldens** — See open table.

### P1

**3–7.** Fixed per tables above.

**8–9.** See open table.

### P2

**10–15, 21.** Fixed per tables above.

**16.** Partial — see open table (#16).

**17.** Fixed — scratch orchestration telemetry.

**18–20.** See open table.

### P3

Items 22–30 — all addressed per P3 fixed table.

</details>
