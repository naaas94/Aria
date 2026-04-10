# Changelog

All notable changes tracked in this folder are listed here (see repo root changelog if the project adds one later).

## 2026_04_10

### Configuration

- **Ingest body limits (audit 22):** `api/limits.py` exports **`DEFAULT_INGEST_MAX_BYTES`** (12 MiB) as the shared default; `api/routers/ingest.py` uses it for **`INGEST_MAX_BYTES`** when unset, matching **`ARIA_MAX_INGEST_BODY_BYTES`** / **`MAX_INGEST_BODY_BYTES`** (middleware `Content-Length` gate for `POST /ingest*`). `.env.example` documents both variables together with aligned example values.

### HTTP & errors

- **500 JSON + request correlation (audit 30):** `api/middleware_request_id.py` sets **`request.state.request_id`**. `api/errors.py` **`ErrorBody`** includes optional **`request_id`**. `api/main.py` **`unhandled_exception_handler`** fills it from `request.state` and sets **`X-Request-ID`** on the 500 **`JSONResponse`** (middleware does not run after unhandled exceptions, so the header is applied on the error payload). Test: `TestInternalErrorResponse` in `tests/eval/test_api_contracts.py` (temporary probe route, `TestClient(..., raise_server_exceptions=False)`).

### Orchestration

- **StepTrace errors (audit 23):** `OrchestrationGraph.execute` in `aria/orchestration/scratch/graph.py` sets **`StepTrace.error`** only on the step that **first** sets `state.error` (transition into error), not on every subsequent trace while `state.error` remains set.

### Observability

- **Scratch orchestration telemetry:** `OrchestrationGraph.execute` in `aria/orchestration/scratch/graph.py` records one **`agent_executions`** row per graph run with synthetic `agent_name` **`orchestration.scratch`**, `request_id` from structlog (when set), `status` / `error` / `duration_ms` aligned with `ExecutionResult`, and the same Prometheus labels as `BaseAgent.run()` (`aria_agent_execution_total`, `aria_agent_execution_duration_seconds`). SQLite write failures increment `aria_telemetry_write_errors_total{source="orchestration"}` with a warning log. Tests: `TestOrchestrationTelemetry` in `tests/unit/test_orchestration.py`. Rationale and tradeoffs: `.dev/notes_prod_or_changes.md` (Scratch orchestration telemetry).

- **Prometheus label cardinality (audit 24):** Module docstring in `aria/observability/metrics.py` documents unbounded **`model`**, **`agent_name`**, **`tool_name`**, **`query_name`** labels and recommends monitoring series churn / recording rules.

- **`complete_structured` vs telemetry (audit 25):** Docstring on `LLMClient.complete_structured` in `aria/llm/client.py` notes that a successful **repair** after a failed JSON parse performs a **second** `complete()` call, so SQLite **`llm_calls`** can contain **two** rows for the same HTTP **`request_id`** (no schema change).

### Golden suite & evaluation

- **Eval store scrub (audit 26):** `tests/eval/scrub.py` centralizes **`scrub_str`** / **`scrub_dict`**; `tests/eval/golden_set/recorder.py` and **`GoldenReport._write_eval_record`** (`tests/eval/golden_set/report.py`) use it for `--emit-eval-store`. `EvalRecord` in `tests/eval/eval_store.py` documents that goldens must not contain secrets; scrub is best-effort.

- **OpenAPI path SSOT (audit 27):** `tests/eval/expected_api_paths.py` defines **`EXPECTED_OPENAPI_PATHS`**; `tests/eval/test_security_audit.py` uses it and adds **`test_golden_openapi_paths_yaml_matches_ssot`** against `tests/eval/golden_set/cases/security/openapi_paths.yaml`.

- **Graph query RETURN contracts (audit 28):** `tests/eval/test_api_contracts.py` adds **`TestAdditionalNamedQueryReturnAliases`** for **`uncovered_requirements`**, **`requirements_by_team`**, **`deadlines_by_regulation`**, **`connected_regulations`** (same `AS alias` pattern as `impact_by_regulation`).

- **`--golden-tier` semantics (audit 29):** `tests/eval/golden_set/conftest.py` help text clarifies **maximum** tier to include, default **`slow`** runs all cases, and **`tier: slow`** on cases is reserved for future expensive scenarios (no new YAML case).

### Documentation

- **Audit findings 22–30 — rationale and file references:** [`.dev/notes_for_prod_or_changes.md`](notes_for_prod_or_changes.md) (logic, tradeoffs, paths to code/tests). Older production notes remain in [`.dev/notes_prod_or_changes.md`](notes_prod_or_changes.md).

## 2026_04_09

### Testing

- **OpenAPI path expectations:** `tests/eval/test_security_audit.py` (`test_documented_openapi_paths_match_expected_set`) and `tests/eval/golden_set/cases/security/openapi_paths.yaml` now include `/metrics` and `/telemetry`, matching the mounted routes in `api/main.py` and `api/routers/telemetry.py`.
- **Stale failure hint:** The same test’s assertion message no longer references removed `docs/security_audit_report.md`; it points maintainers at `tests/eval/golden_set/cases/security/openapi_paths.yaml` when the API surface changes.

### Fixed

- **Ingestion Neo4j dedup — unbounded hash load:** `aria/graph/ingestion_record.py` no longer exposes `list_complete_content_hashes` (single query returning every `pipeline_complete` hash). `aria/ingestion/pipeline.py` durable dedup now calls `is_pipeline_complete(client, content_hash)` only when the hash is not already in `_ingested_hashes`, avoiding startup-scale cost and memory from large historical `IngestionRecord` sets. For full enumerations (exports/maintenance), `iter_complete_content_hashes` streams hashes in lexicographic order with cursor pagination and a configurable `batch_size` (default 5000). Integration tests patch `is_pipeline_complete` instead of the removed list helper.

- **413/422 error JSON consistency:** `api/middleware_body_limit.py` 413 responses now include `"code": "payload_too_large"` alongside `detail`, matching `HTTPException` bodies. `api/main.py` `http_exception_handler` `code_map` maps 413 → `payload_too_large` and 422 → `validation_error` (aligned with `validation_error_payload` in `api/errors.py`), using `HTTP_413_CONTENT_TOO_LARGE` / `HTTP_422_UNPROCESSABLE_CONTENT`. `api/routers/telemetry.py` invalid `since` still raises `HTTPException(422)` but `detail` is now a FastAPI-style validation error list (`type`, `loc`, `msg`, `input`) instead of a plain string.

- **Neo4j password default:** `api/connections.py` now uses `os.getenv("NEO4J_PASSWORD", "aria_dev_password")` to match `api/readiness.py`, `docker-compose.yml`, and `.env.example`. Previously the app defaulted to an empty password when `NEO4J_URI` was set but `NEO4J_PASSWORD` was unset, so `/ready` could report Neo4j healthy while the app did not obtain a driver.

- **`/ready` connection reuse:** `api/readiness.py` no longer creates a new `Neo4jClient` (Bolt connect/close) or `httpx.AsyncClient` on every probe. `readiness_payload(request)` uses `get_app_connections(request)` and probes the lifespan-wired `Neo4jClient` with `health_check()` and Chroma via `VectorStore.health_check()` (`aria/retrieval/vector_store.py` — `chromadb` client `heartbeat()` on the existing HTTP client). `api/main.py` passes `Request` into `readiness_payload`. If a dependency was not connected at startup, that check stays false (no standalone reconnect attempts per request).

- **Nightly eval duplicate goldens:** `.github/workflows/nightly.yml` “Full eval suite” now passes `--ignore=tests/eval/golden_set` so `pytest tests/eval/` does not run `golden_set/` again after the dedicated “Golden set (all tiers, with eval store)” step. The second run had been overwriting `golden_report.json` / `golden_report.xml` before artifact upload.

### Security

- **A2A outbound `X-A2A-Secret`:** `aria/protocols/a2a/client.py` `delegate_task` now sends `X-A2A-Secret` when `A2A_SHARED_SECRET` is set (non-empty after strip), matching `verify_a2a_secret_when_configured` on `aria/protocols/a2a/server.py`. Shared secret resolution lives in `_a2a_shared_secret_from_env()` so tests can stub the client without mutating the process-wide `os.getenv`. Tests in `tests/eval/test_security_audit.py`: `test_a2a_client_delegate_task_401_without_secret_header` (peer requires secret; stubbed client omits header → failed envelope with 401) and `test_a2a_client_delegate_task_200_with_secret_header` (header present → completed task).

- **`/metrics` and `/telemetry` API key:** When `API_KEY` or `ARIA_API_KEY` is set, these routes now require the same credentials as other REST routes (`X-API-Key` or `Authorization: Bearer`), via `Depends(require_api_key_for_observability)` on `telemetry.router` in `api/main.py`. Opt-out for trusted/internal scrapers: `ARIA_OBSERVABILITY_PUBLIC=true` (reads `observability_public_while_api_key_configured()` in `api/config.py`; shared key matching in `api/deps.py` through `_api_key_matches()`). Lifespan logs a warning if the public flag is enabled. Tests: `test_observability_routes_require_api_key_when_configured` and `test_observability_routes_public_flag_bypasses_api_key` in `tests/eval/test_security_audit.py`; `test_rest_routes_require_api_key_when_configured` clears `ARIA_OBSERVABILITY_PUBLIC` so order does not leak state.

### Observability

- **Telemetry SQLite retention:** `aria/observability/telemetry_store.py` adds `TelemetryStore.prune_older_than(retention_days=..., vacuum=True)` — `DELETE` from `llm_calls`, `requests`, and `agent_executions` where `ts` is older than N UTC days (same ISO cutoffs as inserts), then `VACUUM` when any rows were removed. `api/config.py` exposes `telemetry_retention_days()` / `telemetry_prune_interval_seconds()` (`ARIA_TELEMETRY_RETENTION_DAYS`, optional `ARIA_TELEMETRY_PRUNE_INTERVAL_SECONDS`, default 86400s, min 60s). When retention is set, `api/main.py` lifespan starts a background task that prunes once at startup and on each interval via `asyncio.to_thread`, and cancels it before `close_telemetry_store()`. Test: `test_prune_older_than_removes_stale_rows` in `tests/test_telemetry_store.py`.

- **Telemetry write failures:** `api/middleware_telemetry.py` and `aria/agents/base.py` no longer use bare `except Exception: pass` around telemetry store writes and HTTP/agent Prometheus updates. Failures log a **warning** with the exception **type** (no traceback) and increment **`aria_telemetry_write_errors_total`** (`source` = `http_middleware` or `agent`). Defined in `aria/observability/metrics.py`. See `.dev/notes_prod_or_changes.md` (Telemetry write failures).

### Documentation

- **`.env.example`:** API section and Telemetry block document bind/reverse-proxy/firewall notes, key gating for observability routes, `ARIA_OBSERVABILITY_PUBLIC`, and that `GET /telemetry` includes `requests.by_path`.

- **`.env.example` (telemetry DB growth):** Telemetry section documents `ARIA_TELEMETRY_RETENTION_DAYS`, `ARIA_TELEMETRY_PRUNE_INTERVAL_SECONDS`, and a Python cron example for `prune_older_than` (avoids unsafe raw `sqlite3` compares on ISO `ts` vs `datetime('now', …)`).

- **Unauthenticated routes:** `.env.example` now states that only `/health` and `/ready` skip API-key checks when a key is set; `/metrics` and `/telemetry` are gated unless `ARIA_OBSERVABILITY_PUBLIC=true`. `README.md` Auth bullet matches this behavior.

- **Multi-worker / multi-instance deployment:** `README.md` adds subsection **HTTP Surface & Operational Behaviour → Multi-worker and multi-instance deployment** — documents per-process `_ingested_hashes` in `aria/ingestion/pipeline.py`, **`neo4j_dedup`** on `ingest_document` for durable idempotency via Neo4j `IngestionRecord` nodes, and that `/ingest/text` and `/ingest/file` only chunk (no full pipeline). Documents SQLite telemetry defaults (`ARIA_TELEMETRY_DB`), fragmentation when each replica uses a local DB path, and operational options: single writer, shared-volume single file with SQLite caveats, or Prometheus `/metrics` / external stores for HA-style analytics.
