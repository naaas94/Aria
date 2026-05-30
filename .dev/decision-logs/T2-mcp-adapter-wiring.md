# Decision log — T2: Live MCP adapter wiring

**Subtask:** T2 (mvp-phase6-mvp-plus)  
**Date:** 2026-05-30  
**Status:** Landed

## Chosen approach

- **`build_mcp_adapter` / `run_orchestrated_query`** live in `aria/services/orchestrated_query.py`, mirroring `run_compliance_query` placement and taking `AppConnections` from `api.connections`.
- **`build_default_graph`** is imported lazily inside `run_orchestrated_query` to avoid import-order coupling between services and orchestration.
- **`index_vectors`** maps orchestration `dict` chunks to `DocumentChunk` and calls `VectorStore.index_chunks` (not a no-op stub).

## Alternatives rejected

1. **Monolith in `compliance_query.py`** — rejected to keep orchestration imports and graph wiring out of the default query module; T4 fans in routing.
2. **Separate HTTP route for orchestrated mode** — rejected; Phase 6 uses `orchestrated: true` on existing `POST /query` and `--orchestrated` on CLI (T4).
3. **Separate telemetry table for per-step traces** — deferred to T3; T2 only surfaces `execution_trace` on the response via `ExecutionResult.to_trace_dict()`.

## Assumptions

- `ToolPorts` methods in `aria/orchestration/scratch/nodes.py` are all `async`; `MCPToolPortsAdapter` matches (verified — kill T2-KC1 not fired).
- `VectorStore.index_chunks` is the correct public indexing API (verified in `aria/retrieval/vector_store.py`; kill T2-KC2 not fired).
- Ingestion-style chunk dicts use `chunk_id`, `text`, and optional `metadata` / `source_document_hash` keys (aligned with `IngestionAgent` output).
- Graph failures set `ARIAState.error`; `run_orchestrated_query` maps those to `ComplianceQueryUnavailable` with empty `missing_dependencies`.

## Items deferred

- CLI/API routing to `run_orchestrated_query` (T4).
- Per-step `agent_executions` rows with `orchestration.scratch/{node_name}` (T3).
- End-to-end orchestrated query success test with live Neo4j/Chroma (T4 smoke).
- `index_vectors` unit test for `RuntimeError` when vector store is unset but chunks are non-empty (covered indirectly by MCP server pattern; explicit test optional in T4).
