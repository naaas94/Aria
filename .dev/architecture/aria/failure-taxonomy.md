Section:      failure-taxonomy
Version:      1.1.0
Last updated: 2026-05-24

## Layer framework

Project-specific layer definitions (override skill defaults):

```
L0  External runtime / infra — Neo4j, Chroma, LLM providers, env misconfiguration
L2  Persistence & schema — graph labels, Chroma collection, SQLite telemetry, IngestionRecord
L3  Domain logic — ingestion pipeline, agents, retrieval, services, orchestration
L5  Surfaces — FastAPI, CLI, protocol routers
```

## Cause classes

```
Taxonomy version: 1.1.0
Last updated:     2026-05-24
```

Only classes with confirmed test coverage or explicit enum/handling in production code.

| Class | Layer | Description | Evidence |
|-------|-------|-------------|----------|
| `L0.neo4j_connect_failure` | L0 | Neo4jClient.connect() raises on unreachable Bolt | test_neo4j_unreachable_connect_fails_fast |
| `L0.chroma_unreachable` | L0 | VectorStore.health_check() → False; gates /ready 503 | readiness + health assessment tests |
| `L0.llm_unreachable_retries_exhausted` | L0 | LLMClient.complete retries (default 3) then raises; probe fails independently of /ready 200 | LLMClient max_retries=3, timeout=120s |
| `L0.llm_missing_api_key` | L0 | _require_non_placeholder_api_key raises at LLMClient init for cloud models | llm/client.py |
| `L2.neo4j_runtime_read_failure` | L2 | health_check() catches query errors, returns False | test_neo4j_health_check_degrades_to_false |
| `L2.graph_write_transaction_rollback` | L2 | Batch write in single tx; mid-batch failure aborts all | test_graph_batch_write_transaction_rolls_back_on_mid_batch_failure |
| `L2.vector_index_failure_partial_ingest` | L2 | IngestionStatus.PARTIAL_FAILURE; hash not committed to skip set | test_chroma_vector_failure_partial_ingestion_not_committed_to_hash_set |
| `L2.ingestion_record_persistence_failure` | L2 | Upsert failure logged; dedup/progress may be stale | pipeline.py upsert catch |
| `L2.sqlite_telemetry_write_failure` | L2 | Swallowed in hot paths; TELEMETRY_WRITE_ERRORS_COUNTER incremented | telemetry_store, agents, LLM client |
| `L3.document_parse_error` | L3 | Unsupported format or parse failure → IngestionStatus.PARSE_ERROR | ingestion/pipeline.py |
| `L3.entity_extraction_failure` | L3 | Extraction step failure → IngestionStatus.EXTRACTION_ERROR | ingestion/pipeline.py |
| `L3.llm_structured_output_invalid` | L3 | ValidationError from complete_structured; repair pass then re-raise | llm/client.py |
| `L3.graph_write_partial_failure` | L3 | GraphWriteStatus.success=False → IngestionStatus.PARTIAL_FAILURE | pipeline + builder |
| `L3.duplicate_content_hash_skipped` | L3 | Idempotent skip → IngestionStatus.SKIPPED_DUPLICATE (not an error) | pipeline dedup |
| `L3.orchestration_node_error` | L3 | state.error set on node failure, invalid return, or max steps exceeded | tests/eval/test_trajectory_eval.py, test_edge_cases.py |
| `L3.mcp_unknown_tool` | L3 | Unknown MCP tool name returned to caller | MCP error codes |
| `L3.mcp_tool_execution_failed` | L3 | MCP tool handler exception sanitized | MCP server |
| `L3.a2a_task_handler_exception` | L3 | TaskStatus.FAILED with sanitized message | a2a/server.py |
| `L3.live_backend_unavailable` | L3 | ComplianceQueryUnavailable / ImpactReportUnavailable → HTTP 503 when ARIA_PLACEHOLDER_API=false | services + routers |
| `L5.http_validation_unknown_keys` | L5 | 422 on extra="forbid" models | ingest router, ComplianceQueryRequest |
| `L5.ingest_body_too_large` | L5 | Middleware 413 (ARIA_MAX_INGEST_BODY_BYTES) or router 413 (INGEST_MAX_BYTES) | middleware_body_limit, routers/ingest |
| `L5.auth_failure` | L5 | 401 on missing/wrong API key or A2A secret | deps.py, a2a/server.py |
| `L5.ready_degraded` | L5 | /ready returns 503 while process alive (Neo4j or Chroma down) | api/readiness.py |
| `L5.unhandled_exception` | L5 | Generic 500 internal_error | api/main.py |

### Anticipated (concrete, not fully production-tested)

| Class | Layer | Description |
|-------|-------|-------------|
| `L5.ready_ok_llm_down_query_fails` | L5 | /ready returns 200 with LLM down; live POST /query fails at runtime — by design per assessment.py |
