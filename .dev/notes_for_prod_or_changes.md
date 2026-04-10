# Audit findings 22–30 — rationale and file references

Brief **why** for maintainers and ops. The **what** is in [CHANGELOG.md](CHANGELOG.md) (`2026_04_10`) and the code/tests cited below.

---

## Two ingest env vars (`ARIA_MAX_INGEST_BODY_BYTES` vs `INGEST_MAX_BYTES`)

**Logic:** Middleware can reject an oversized `Content-Length` before the body is streamed; the ingest router enforces limits when reading `/ingest/text` and `/ingest/file`. Those layers are configurable independently (e.g. tests, reverse proxies). **Defaults are aligned** when env is unset so behavior matches expectations without coupling the two knobs in code.

**Files:** [`api/limits.py`](../api/limits.py) (`DEFAULT_INGEST_MAX_BYTES`, `MAX_INGEST_BODY_BYTES`), [`api/routers/ingest.py`](../api/routers/ingest.py) (`_ingest_max_bytes`), [`api/middleware_body_limit.py`](../api/middleware_body_limit.py), [`.env.example`](../.env.example).

---

## `StepTrace.error` only on the step that first sets `state.error`

**Logic:** After the first failure, `state.error` stays set; repeating the same string on every subsequent `StepTrace` adds noise. The useful signal is **where** the run first failed, not that it **remained** failed.

**Files:** [`aria/orchestration/scratch/graph.py`](../aria/orchestration/scratch/graph.py) (`OrchestrationGraph.execute`).

---

## Prometheus label cardinality (documentation only)

**Tradeoff:** `model`, `agent_name`, `tool_name`, and `query_name` labels reflect real runtime values. **Allowlisting or bucketing** would add branching and maintenance; for this pass we **document** cardinality risk so operators can monitor series growth or use recording rules.

**Files:** [`aria/observability/metrics.py`](../aria/observability/metrics.py).

---

## `complete_structured` → two `llm_calls` rows for one HTTP `request_id`

**Logic:** Each successful [`LLMClient.complete()`](../aria/llm/client.py) records one telemetry row. A **repair** after a failed JSON parse is a **second** completion. Analysts should not treat duplicate `request_id` as a duplicate insert bug unless a future **`phase`** column (or similar) is added.

**Files:** [`aria/llm/client.py`](../aria/llm/client.py) (`complete_structured` docstring), [`aria/observability/telemetry_store.py`](../aria/observability/telemetry_store.py) (`record_llm_call`).

---

## Eval JSONL scrub (`--emit-eval-store`)

**Logic:** Shared [`scrub_dict`](../tests/eval/scrub.py) redacts obvious secret/PII-like **strings** in emitted records. Scrub is **best-effort**, not a security boundary — policy remains: **do not put secrets in golden YAML**.

**Files:** [`tests/eval/scrub.py`](../tests/eval/scrub.py), [`tests/eval/golden_set/recorder.py`](../tests/eval/golden_set/recorder.py), [`tests/eval/golden_set/report.py`](../tests/eval/golden_set/report.py) (`_write_eval_record`), [`tests/eval/eval_store.py`](../tests/eval/eval_store.py) (`EvalRecord`).

---

## OpenAPI paths single source of truth

**Logic:** One frozen set for the documented HTTP path surface avoids drift between the security audit test and the golden `openapi_paths` case.

**Files:** [`tests/eval/expected_api_paths.py`](../tests/eval/expected_api_paths.py), [`tests/eval/test_security_audit.py`](../tests/eval/test_security_audit.py), [`tests/eval/golden_set/cases/security/openapi_paths.yaml`](../tests/eval/golden_set/cases/security/openapi_paths.yaml).

---

## Named Cypher query `RETURN` alias tests

**Logic:** Named queries in [`aria/graph/queries.py`](../aria/graph/queries.py) are the safe surface for MCP / tools; **column aliases** are the stable contract for consumers. Tests lock `AS …` names for selected queries beyond `impact_by_regulation`.

**Files:** [`tests/eval/test_api_contracts.py`](../tests/eval/test_api_contracts.py) (`TestAdditionalNamedQueryReturnAliases`, `TestImpactReportVsImpactByRegulationQuery`), [`aria/graph/queries.py`](../aria/graph/queries.py).

---

## `--golden-tier` CLI semantics

**Logic:** The option is the **maximum** tier to **include** (`fast` < `medium` < `slow`). Default **`slow`** runs **all** cases defined today. A case with **`tier: slow`** is reserved for future expensive scenarios — the name can read like “run only slow tests,” hence the explicit help text.

**Files:** [`tests/eval/golden_set/conftest.py`](../tests/eval/golden_set/conftest.py).

---

## 500 JSON `request_id` and `X-Request-ID` on the error response

**Logic:** `request.state.request_id` is set in middleware so handlers do not rely on structlog context (unbound in middleware `finally` before exception handlers run). **`X-Request-ID`** is also set on the **500 `JSONResponse`** because unhandled exceptions may not receive the middleware’s usual “attach header after `call_next`” path the same way as normal responses.

**Files:** [`api/middleware_request_id.py`](../api/middleware_request_id.py), [`api/errors.py`](../api/errors.py) (`ErrorBody`), [`api/main.py`](../api/main.py) (`unhandled_exception_handler`), [`tests/eval/test_api_contracts.py`](../tests/eval/test_api_contracts.py) (`TestInternalErrorResponse`).
