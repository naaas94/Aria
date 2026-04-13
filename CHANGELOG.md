# Changelog

All notable changes tracked in this folder are listed here (see repo root changelog if the project adds one later).

## 2026_04_12

### Ingestion

- **`ingest_document` injectable types (`aria/ingestion/pipeline.py`):** Replaced `entity_extractor`, `graph_writer`, and `vector_indexer: Any | None` with explicit async-callable aliases — **`EntityExtractorFn`**, **`GraphWriterFn`**, **`VectorIndexerFn`** — using **`Callable[[...], Awaitable[...]]`** over **`ExtractedEntities`**, **`GraphWriteStatus`**, and **`list[DocumentChunk]`**, matching the existing docstring contracts.
- **Rationale:** Aligns the public DI surface with **mypy strict** and editor tooling so call sites are checked against the same shapes the pipeline already assumes at runtime, without changing behavior.

### HTTP (API)

- **`api/main.py` — `_build_fastapi` typing:** The **`FastAPI(...)`** kwargs map is now **`dict[str, Any]`** (with **`from typing import Any`**) instead of an untyped **`dict`**, matching **mypy**-strict style used elsewhere.
- **Rationale:** Documents the real key/value shapes passed into **`FastAPI`** (strings, optional **`None`** OpenAPI URLs, **`lifespan`**) so static analysis and editors treat **`kwargs`** like the rest of the API package.
- **Imports:** **Ruff/isort** reordered first-party **`api.*`** imports; removed unused **`os`** and imports that were not referenced in this module (**`AppConnections`**, **`get_app_connections`**).
- **`lifespan`:** Annotated as **`AsyncIterator[None]`** ( **`AsyncContextManager`** / **`@asynccontextmanager`** ) for explicit async-context typing under strict **mypy**.
- **`RequestValidationError` handler:** **`validation_error_payload`** is called with **`cast(list[dict[str, Any]], exc.errors())`** so the handler matches the payload helper’s type without changing runtime behavior (**Pydantic** already returns JSON-serializable structures).
- **Middleware (`api/middleware_*.py`):** **`BaseHTTPMiddleware.dispatch`** overrides now type **`call_next`** as **`Callable[[Request], Awaitable[Response]]`** and annotate **`response: Response`** where needed so middleware matches **Starlette**’s contract under **mypy** strict.

### Tooling

- **`pyproject.toml` — mypy scope (`[tool.mypy]`):** Added **`files = ["aria", "api", "tests"]`** and **`exclude = ["scripts/"]`** so `mypy` (no arguments) only checks library and test code.
- **Rationale:** `scripts/` has no `__init__.py`; mypy resolved `seed_graph.py` as both a top-level module and `scripts.seed_graph`, causing a duplicate-module crash. Scoping with `files` makes the check deterministic; `exclude` is a belt-and-suspenders backstop.
- **`[[tool.mypy.overrides]]` for `module = "tests.*"`:** Sets **`disallow_untyped_defs`**, **`disallow_untyped_decorators`**, and **`disallow_incomplete_defs`** to **`false`** for the test tree while keeping the rest of **`strict`**.
- **Rationale:** Tests previously accounted for most **mypy** noise (fixtures, bare **`dict`**, missing **`-> None`**). Relaxing only those flags keeps production code strict and lets you tighten or exclude modules incrementally (e.g. unit tests first, then eval, then integration).
- **`[[tool.mypy.overrides]]` — third-party imports:** **`chromadb.*`**, **`langgraph.*`**, **`litellm.*`**, **`neo4j.*`**, **`pdfplumber.*`**, **`structlog.*`** use **`ignore_missing_imports = true`**.
- **Rationale:** Those packages often ship without complete inline types or published stubs; without the override, **mypy** reports missing-import noise that does not reflect bugs in **aria**/**api**. **`langgraph.*`** is also listed because **`langgraph`** is an optional extra (**`aria[langgraph]`**), so default **`pip install -e ".[dev]"`** (e.g. in CI) does not install it; **`langgraph_reference`** imports are runtime-guarded. You can replace or narrow overrides later with **`types-*`** wheels or tighter per-module settings.

### CI

- **Type check step:** Runs **`mypy aria api`** after **`pip install -e ".[dev]"`**.
- **Rationale:** CI enforces typing on **`aria`** and **`api`** without blocking merges on the full test package; local **`mypy`** (no args) still follows **`pyproject`** and can include **`tests`** with the override above. Aligns pipeline cost with “ship-quality” library/API code first.

### Core (`aria` — typing and small behavior)

- **`aria/contracts/graph_entities.py` — `GraphNode.merge_key`:** Returns **`str`** even when **`properties["id"]`** is not inferred as a string (coerce via **`isinstance`** / **`str()`**).
- **`aria/agents/impact_analyzer.py`:** **`coverage_summary`** is explicitly **`dict[CoverageStatus, int]`** to satisfy **`var-annotated`** under strict **mypy**.
- **`aria/llm/client.py`:** Defaults use **`os.getenv(...) or "<default>"`** so empty env strings do not override intentional defaults (and types line up with **Optional**-from-**getenv** patterns).
- **`aria/observability/logger.py`:** **`log_level`** narrowed when **`level`** is **`None`**; **`get_logger`** **`cast`** to **`structlog.stdlib.BoundLogger`** for a precise return type.
- **`aria/orchestration/langgraph_reference/`:** Node/state helpers use **`ARIAStateDict`** (**`TypedDict`**) and **`cast`** where **Pydantic** **`model_dump()`** is merged back into graph state; aligns LangGraph stubs with strict typing.
- **`aria/orchestration/scratch/nodes.py` — `ToolPorts`:** Return and parameter **`dict`** / **`list`** types use **`dict[str, Any]`** / **`list[dict[str, Any]]`** instead of bare generics.
- **`aria/protocols/mcp/server.py` — `MCPToolPortsAdapter`:** **`cast`** on tool **`result.data`** and LLM paths so list/str returns match declared types.
- **`aria/retrieval/reranker.py`:** Removed unused **`graph_texts`**; **`_extract_nested`** takes **`dict[str, object]`** for clearer key navigation typing.
- **`aria/retrieval/vector_store.py`:** Chroma client/collection fields use **`Any`** where third-party stubs are imprecise; **getenv** defaults match the LLM pattern; **`metadata`** / **`count()`** use **`cast`** where the HTTP client returns loosely typed values.

## 2026_04_11

### Documentation

- **Updated** **`README.md`** — Quickstart uses **`aria init`** / **`aria ingest`** for the full file pipeline; new **CLI (`aria`)** section lists subcommands and documents **`GET /ready`** ( **`neo4j` / `chroma` / `llm`**, HTTP status vs ingest preflight, and **`ARIA_READY_LLM_CACHE_TTL_SECONDS`** for **`/ready`** LLM probe caching). Developer ingest table references **`aria ingest`**. **`.env.example`** — LLM block notes readiness and ingest preflight; documents **`ARIA_READY_LLM_CACHE_TTL_SECONDS`**; short **`aria`** workflow comment.

### Health & readiness

- **Shared dependency assessment:** New package **`aria.health`** (`aria/health/assessment.py`) — **`DependencyReport`** (`neo4j_ok`, `chroma_ok`, `llm_ok`, **`errors`**), **`DependencyConnections`** (protocol aligned with **`api.connections.AppConnections`**), **`assess_app_connections`**, and **`probe_llm_reachable`**. Neo4j/Chroma checks match prior behavior (optional connections, **`health_check`**); LLM uses a minimal **`litellm.acompletion`** with **`LLM_MODEL` / `LLM_BASE_URL` / `LLM_API_KEY`** (short timeout, **`max_tokens=1`**) and **does not** go through **`LLMClient.complete()`**, avoiding telemetry/Prometheus noise on probes. Module docstring documents **/ready policy:** HTTP **200 vs 503** follows **Neo4j + Chroma** only; **`llm`** is always present in JSON; LLM failure does not force 503. **`full_ingest_dependencies_satisfied(report)`** returns true only when all three of Neo4j, Chroma, and LLM pass — used by **`aria ingest`** preflight, not by **`/ready`**.
- **`GET /ready` LLM probe caching (implementation + rationale):**
  - **Changes:** **`assess_app_connections`** accepts optional **`llm_probe`** (defaults to **`probe_llm_reachable`**). **`LlmReadyProbeCache`** (exported from **`aria.health`**) memoizes the last LLM probe result for a configurable TTL; **`api/readiness.py`** attaches one cache per app (**`app.state._llm_ready_probe_cache`**) and passes **`llm_probe=cache.probe`**. TTL from **`ARIA_READY_LLM_CACHE_TTL_SECONDS`** (default **300**); **`0`** disables caching (fresh probe every request). **`api/main.py`** **`/ready`** docstring notes cached probe.
  - **Rationale:** Previously every **`GET /ready`** ran a real LiteLLM completion (up to **12s** timeout). Frequent Kubernetes readiness probes (often **10–30s**) imposed avoidable provider cost, rate-limit risk, and tail latency, even though **HTTP 200 vs 503** depends only on Neo4j + Chroma. Caching the LLM leg preserves informational **`llm`** in JSON while keeping Neo4j/Chroma checks on every request. **`aria status`** and **`aria ingest`** preflight still call **`assess_app_connections`** without a custom **`llm_probe`** so operators get a **fresh** LLM result on each run.
- **`GET /ready` response:** **`api/readiness.py`** returns **`neo4j`**, **`chroma`**, **`llm`**, and optional **`errors`**. **`tests/unit/test_health_assessment.py`** covers **`llm_probe`**, **`LlmReadyProbeCache`**, and existing assessment cases; **`tests/eval/test_api_contracts.py`** and **`tests/fixtures/api_requests.py`** expect **`llm`** on the response.

### Application services (API + CLI)

- **Shared query and impact logic:** New package **`aria.services`** — **`compliance_query`** (`run_compliance_query`, **`ComplianceQueryRequest`** / **`ComplianceQueryResponse`**, success vs missing-deps outcomes) and **`impact_report`** (`run_impact_report`, **`ImpactSummaryResponse`**, same). Core behavior is unchanged: hybrid / vector-only paths, **`RETRIEVAL_*`** metrics, **`ImpactAnalyzerAgent`** + **`execute_named_query`**. **`api/routers/query.py`** and **`api/routers/impact.py`** parse or route params, call **`placeholder_api_enabled()`**, invoke the service, set **`X-ARIA-Mode`**, and map dependency gaps to **503** + **`ServiceUnavailableBody`** only in the HTTP layer.
- **Rationale:** One implementation for REST and future CLI (no drift); services take **`use_placeholder`** and connection **Protocols** structurally compatible with **`AppConnections`** so **`aria`** does not import **`api.*`**, and the CLI can avoid Starlette/FastAPI exceptions by handling outcome dataclasses instead.

### CLI

- **Typer entry point:** Added dependency **`typer>=0.12`**, package **`aria.cli`** (`aria/cli/main.py` — `typer.Typer` with root callback that loads **`.env`** via **`load_dotenv()`**, **`main()`** invokes the app), and **`[project.scripts]`** console script **`aria`** → **`aria.cli.main:main`**. `aria --help` exercises packaging after **`pip install -e .`**.

- **Operational subcommands (`aria/cli/commands/`):** **`serve`** runs **`uvicorn`** against **`api.main:app`** (host, port, reload). **`init`** connects with **`Neo4jClient`** and runs **`initialize_schema()`**; exits with a clear message if **`NEO4J_URI`** is missing or Bolt fails. **`status`** uses **`asyncio.run`**: **`connect_app_dependencies(strict=True)`**, **`assess_app_connections`**, optional **`--json`**; process exit code **1** if Neo4j or Chroma checks fail (data-plane alignment with **`/ready`**). **`telemetry`** prints the same rolling or **`since`** window as **`GET /telemetry`** (`--hours`, **`--since`**). **`eval`** runs **`pytest`** on **`tests/eval/golden_set/test_goldens.py`** and forwards extra arguments to pytest. **`query`** and **`impact`** (in-process services) are described in the next bullet. **Rationale:** operational workflows (server, schema init, dependency checks, telemetry inspection, golden eval); **`status`** reuses TASK 2 assessment instead of duplicating probes.

- **Full pipeline ingest (`aria ingest <file>`):** **`aria/ingestion/wiring.py`** — **`build_full_ingest_wiring`** builds async callables for **`ingest_document`**: **`EntityExtractorAgent.process`** → **`ExtractedEntities`**, **`GraphBuilderAgent(neo4j).process`** → **`GraphWriteStatus`**, and **`vector_indexer`** wrapping **`VectorStore.index_chunks`** via **`asyncio.to_thread`** (sync Chroma client off the event loop). **`aria/cli/commands/ingest.py`** — **Preflight:** **`full_ingest_dependencies_satisfied`** (in **`aria/health/assessment.py`**) requires **Neo4j, Chroma, and LLM** all OK (stricter than **`aria status`** exit rules or HTTP **`/ready`**, which do not require LLM for “green” data plane); if any component fails, stderr lists lines of the form **`missing: neo4j|chroma|llm: …`** and the process exits **1** without calling **`ingest_document`**. **Success path:** runs **`await neo4j.initialize_schema()`** before ingest unless **`--skip-schema`** (for DBs already initialized via **`aria init`**); then **`ingest_document(..., entity_extractor, graph_writer, vector_indexer, neo4j_dedup=neo, force=--force)`**. **Rationale:** gives operators a single command for the same full pipeline as scripts/tests (`ingest_document`), addresses path-to-release risk that HTTP **`/ingest/*`** is chunk-only; fail-fast avoids silent partial runs and LLM timeouts after wasted setup; optional schema application reduces MERGE failures when uniqueness constraints were never applied.

- **In-process query and impact (`aria query`, `aria impact`):** **`aria/cli/commands/query.py`** — positional **`question`**; **`--regulation-id` / `-r`**; **`--graph-rag` / `--no-graph-rag`** and **`--top-k`** aligned with **`ComplianceQueryRequest`** / **`POST /query`**. **`aria/cli/commands/impact.py`** — positional **`regulation_id`**; **`--json`** on both commands. **Placeholder** (default **`ARIA_PLACEHOLDER_API=true`**): no **`connect_app_dependencies`** call; invokes **`run_compliance_query`** / **`run_impact_report`** with empty **`AppConnections`** so demos work without Neo4j/Chroma. **Live** (**`ARIA_PLACEHOLDER_API=false`**): **`asyncio.run`** after **`connect_app_dependencies(strict=True)`** + **`disconnect_app_dependencies`** in a **`finally`** block; dependency gaps use the same outcomes as **`aria.services`** (exit **1**, body aligned with **`ServiceUnavailableBody`**: **`detail`**, **`code: service_unavailable`**, **`missing_dependencies`** when **`--json`**; stderr summary otherwise). Success prints answer + sources (query) or summary fields (impact), or full JSON including **`aria_mode`**. Module docstrings note aligning process env with the API (**`ARIA_PLACEHOLDER_API`**, **`NEO4J_*`**, Chroma). **`aria/cli/main.py`** registers both subcommands. **Rationale:** same services as the HTTP layer (TASK 3) without Starlette/FastAPI or HTTP (D2); avoids env drift between “CLI vs API” by documenting shared variables and reusing strict connect for live paths.

- **Strict connect for `aria status`:** **`api.connections.connect_app_dependencies`** accepts **`strict=`** (default **`False`** for API lifespan). When **`strict=True`**, Bolt or Chroma connection failures populate **`AppConnections.connection_errors`** instead of only logging. **`aria.health.assessment.merge_strict_connection_errors`** merges those hints into **`DependencyReport.errors`** so generic **`not configured`** lines become concrete failure messages. **Rationale:** lifespan wiring intentionally swallows infra errors so the process can start without Neo4j/Chroma; operators running **`aria status`** need to see whether a backend was **attempted and failed** versus never configured, without forking **`assess_app_connections`** for API vs CLI.

### Observability

- **Shared `since` parsing:** **`aria/observability/since_parse.py`** defines **`parse_since_iso_utc`** (raises **`ValueError`**; no FastAPI dependency). **`api/routers/telemetry.py`** wraps validation errors as **422**; **`aria telemetry`** prints to stderr and exits **2** on invalid **`--since`**. **Rationale:** one datetime rule for HTTP query params and the CLI.

### Testing

- **CLI-related units:** **`tests/unit/test_since_parse.py`**, **`tests/unit/test_connections_strict.py`**, and **`merge_strict_connection_errors`** / **`full_ingest_dependencies_satisfied`** / custom **`llm_probe`** / **`LlmReadyProbeCache`** (TTL hit and **`ttl=0`**) in **`tests/unit/test_health_assessment.py`**. **`tests/unit/test_ingestion_wiring.py`** exercises **`build_full_ingest_wiring`** (vector indexer threading and mocked agent closures).

- **Services + contracts (TASK 7):** **`tests/unit/test_services_compliance_query.py`** — placeholder paths, live **503-style** missing-deps outcomes (**`ComplianceQueryUnavailable`**), and live success with **`HybridRetriever.retrieve`** / **`LLMClient.complete`** mocked (graphrag + vector-only). **`tests/unit/test_services_impact_report.py`** — placeholder, missing Neo4j, and live success with **`ImpactAnalyzerAgent.process`** mocked. **`tests/unit/test_cli_entry.py`** — **`typer.testing.CliRunner`** smoke tests for **`aria --help`** and **`aria query --help`** (packaging / wiring without backends). **`tests/eval/test_security_audit.py`** **`test_health_and_ready_skip_api_key_when_configured`** also asserts **`llm`** is present and boolean on **`GET /ready`**, matching **`tests/eval/test_api_contracts.py`** and keeping security eval honest when the readiness JSON shape changes. **Rationale:** lock in shared **`aria.services`** behavior independent of FastAPI routers; CLI help regressions are caught in CI; **`/ready`** body is asserted in both contract and security suites.

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
