Section:      known-coupling-surfaces
Version:      1.1.0
Last updated: 2026-05-24

Import-graph invisible string, config, and schema couplings (confirmed from code):

```
Surface:      SCHEMA_VERSION = "0.1.0" duplicated across contract modules
Shared by:    aria/contracts/regulation ↔ graph_entities ↔ impact ↔ agent_messages ↔ ARIA_STRICT_SCHEMA_VERSION env
Failure mode: strict mode rejects payloads; mixed versions cause runtime validation failures
Confirmed:    yes — source: aria/contracts/*.py, _strict.py
```

```
Surface:      NodeLabel / EdgeType enum string values
Shared by:    aria/contracts/graph_entities ↔ schema.VALID_EDGES ↔ graph/builder MERGE templates ↔ literal :Regulation, :Article in queries.py
Failure mode: renamed enum breaks constraints, builder validation, or all named queries
Confirmed:    yes — source: graph_entities.py, schema.py, queries.py
```

```
Surface:      10 named query registry keys (get_regulation_by_id, impact_by_regulation, …)
Shared by:    aria/graph/queries.QUERIES ↔ MCP CypherQueryInput description ↔ golden/contract tests
Failure mode: renamed query breaks MCP, impact analyzer, and eval contract tests
Confirmed:    yes — source: queries.py, mcp/tools.py, tests/eval/*
```

```
Surface:      IngestionRecord label and properties (content_hash, pipeline_complete, graph_indexed, vector_indexed)
Shared by:    aria/graph/schema constraint DDL ↔ aria/graph/ingestion_record ↔ aria/ingestion/pipeline dedup
Failure mode: re-ingest duplicates or wrong skip behavior if label/property names diverge
Confirmed:    yes — source: schema.py, ingestion_record.py
```

```
Surface:      DEFAULT_COLLECTION = "aria_regulatory_chunks"
Shared by:    aria/retrieval/vector_store ↔ seed scripts ↔ external indexing jobs
Failure mode: search returns empty if chunks indexed under different collection name
Confirmed:    yes — source: vector_store.py
```

```
Surface:      Chunk ID algorithm md5(f"{doc_hash}:{index}")[:16]
Shared by:    aria/ingestion/chunker ↔ Chroma upsert ids in vector_store.index_chunks
Failure mode: re-chunking with changed algorithm orphans or duplicates vector entries
Confirmed:    yes — source: chunker.py, vector_store.py
```

```
Surface:      Environment variable sprawl (NEO4J_*, CHROMA_*, LLM_*, ARIA_PLACEHOLDER_API default true, API_KEY/ARIA_API_KEY, A2A_SHARED_SECRET, telemetry vars)
Shared by:    api/config, api/connections, aria/llm/client, aria/retrieval/vector_store, aria/health/assessment, .env.example
Failure mode: misconfigured deployment; placeholder mode mistaken for live data
Confirmed:    yes — source: grep os.getenv across aria/ and api/
```

```
Surface:      Dual ingest size limits ARIA_MAX_INGEST_BODY_BYTES vs INGEST_MAX_BYTES
Shared by:    api/middleware_body_limit ↔ api/limits ↔ api/routers/ingest
Failure mode: middleware 413 vs router 413 at different thresholds; comment says "keep in sync" but different env keys
Confirmed:    yes — source: limits.py, routers/ingest.py, .env.example
```

```
Surface:      AGENT_CARDS dict keys
Shared by:    aria/protocols/a2a/agent_card ↔ api/connections registry seed ↔ GET /agents/{name} slug resolution
Failure mode: agent not discoverable if key/slug diverges from card agent_id
Confirmed:    yes — source: agent_card.py, connections.py, routers/agents.py
```

```
Surface:      node_label_hint = "Article" default
Shared by:    aria/services/compliance_query ↔ MCP HybridRetrievalInput default
Failure mode: graph expansion misses nodes if Neo4j label strings change
Confirmed:    yes — source: compliance_query.py, mcp/tools.py
```

```
Surface:      Merge key "id" for all node types (NODE_MERGE_KEYS)
Shared by:    aria/graph/schema ↔ aria/graph/builder MERGE templates
Failure mode: duplicate nodes or failed merges if merge key property renamed for one label only
Confirmed:    yes — source: schema.py, builder.py
```

```
Surface:      Prometheus metric names and label vocab (aria_* counters; strategy, tool_name, model labels)
Shared by:    aria/observability/metrics ↔ api/routers/telemetry GET /metrics ↔ dashboards
Failure mode: broken dashboards/alerts if metric or label renamed without migration
Confirmed:    yes — source: metrics.py
```

```
Surface:      SQLite table names llm_calls, requests, agent_executions
Shared by:    aria/observability/telemetry_store ↔ GET /telemetry JSON ↔ external prune scripts (.env.example)
Failure mode: external cron prune targets wrong table or incompatible timestamp format
Confirmed:    yes — source: telemetry_store.py
```

```
Surface:      CLI → API package imports (api.config, api.connections)
Shared by:    aria/cli/commands/{query,impact,ingest,status} ↔ api layer
Failure mode: package dependency inversion; CLI breaks if api module layout or config helpers change
Confirmed:    yes — source: aria/cli/commands/*.py
```

```
Surface:      ORCHESTRATION_SCRATCH_AGENT_NAME = "orchestration.scratch"
Shared by:    aria/orchestration/scratch/graph ↔ Prometheus AGENT_EXECUTION_* ↔ telemetry_store
Failure mode: scratch graph runs invisible in dashboards if label changes
Confirmed:    yes — source: scratch/graph.py
```

```
Surface:      CANONICAL_SCRATCH_*_PATH node name sequences
Shared by:    aria/orchestration/scratch/paths ↔ edges.EDGE_MAP ↔ graph.build_default_graph ↔ tests/eval trajectory checks
Failure mode: orchestration refactor passes unit tests but fails golden trajectory evals
Confirmed:    yes — source: paths.py, tests/eval/*
```

```
Surface:      ToolPorts method names (extract_entities, write_to_graph, query_graph, …)
Shared by:    aria/orchestration/scratch/nodes ↔ MCPToolPortsAdapter in mcp/server.py
Failure mode: orchestration nodes call tools adapter does not implement
Confirmed:    yes — source: nodes.py, mcp/server.py (adapter unused in production today)
```

```
Surface:      HTTP header X-ARIA-Mode (placeholder | live)
Shared by:    api/routers/query ↔ api/routers/impact ↔ eval contract tests
Failure mode: clients cannot distinguish demo vs production responses
Confirmed:    yes — source: query.py, impact.py, tests/eval/test_api_contracts.py
```

```
Surface:      LLMClient defaults max_retries=3, timeout=120.0
Shared by:    aria/llm/client ↔ tests overriding max_retries=1 ↔ eval timeout bounds
Failure mode: production timeout/retry behavior diverges from test assumptions
Confirmed:    yes — source: llm/client.py, tests/eval/test_safety_reliability.py
```
