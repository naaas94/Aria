Section:      public-interface-inventory
Version:      1.0.0
Last updated: 2026-05-24

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `run_compliance_query` | `aria/services/compliance_query` | function | `(ComplianceQueryRequest, ComplianceQueryConnections, *, use_placeholder) → ComplianceQueryOutcome` | `api/routers/query`, `aria/cli/commands/query` | stable |
| `run_impact_report` | `aria/services/impact_report` | function | `(regulation_id, ImpactReportConnections, *, use_placeholder) → ImpactReportOutcome` | `api/routers/impact`, `aria/cli/commands/impact` | stable |
| `ComplianceQueryRequest` | `aria/services/compliance_query` | type | Pydantic DTO: question, optional regulation_id, use_graph_rag, top_k | API, CLI | stable |
| `ComplianceQueryResponse` | `aria/services/compliance_query` | type | answer, sources, retrieval_strategy, trace | API | stable |
| `ImpactSummaryResponse` | `aria/services/impact_report` | type | regulation summary with gap_count, risk_level, details | API, CLI | stable |
| `assess_app_connections` | `aria/health/assessment` | function | `(DependencyConnections, *, llm_probe?) → DependencyReport` | `api/readiness`, `aria/cli/commands/status`, `aria/cli/commands/ingest` | stable |
| `probe_llm_reachable` | `aria/health/assessment` | function | `() → (bool, str \| None)` | readiness cache, ingest preflight | stable |
| `LlmReadyProbeCache` | `aria/health/assessment` | class | TTL-cached LLM probe for high-frequency `/ready` | `api/readiness` | stable |
| `ingest_document` | `aria/ingestion/pipeline` | function | `(path, *, extract_fn, write_fn, index_fn, neo4j?) → IngestionResult` | CLI ingest, integration tests | active |
| `build_full_ingest_wiring` | `aria/ingestion/wiring` | function | `(neo4j, vector_store) → wiring callables for full ingest | CLI ingest, tests | active |
| `parse_pdf` | `aria/ingestion/parsers/pdf_parser` | function | `(path) → ParsedDocument` | ingestion pipeline | stable |
| `parse_html` | `aria/ingestion/parsers/html_parser` | function | `(path) → ParsedHTMLDocument` | ingestion pipeline | stable |
| `chunk_text` | `aria/ingestion/chunker` | function | `(text, *, source_hash, metadata?) → list[DocumentChunk]` | pipeline, API chunk-only ingest | stable |
| `Neo4jClient` | `aria/graph/client` | class | async driver wrapper: connect, health_check, run, close | graph layer, connections, agents | stable |
| `write_payload` | `aria/graph/builder` | function | `(Neo4jClient, GraphWritePayload) → GraphWriteStatus` | graph builder agent, wiring | stable |
| `entities_to_write_payload` | `aria/graph/builder` | function | `(ExtractedEntities) → GraphWritePayload` | graph builder, tests, seed script | stable |
| `execute_named_query` | `aria/graph/queries` | function | `(Neo4jClient, query_name, params) → GraphQueryResult` | MCP server, impact analyzer, services | stable |
| `QUERIES` | `aria/graph/queries` | constant | allow-listed named Cypher query registry | MCP tools, docs | stable |
| `generate_constraint_statements` | `aria/graph/schema` | function | `() → list[str]` Cypher DDL | CLI init, schema setup | stable |
| `VectorStore` | `aria/retrieval/vector_store` | class | Chroma HTTP client: connect, index_chunks, search | retrieval, MCP, connections | stable |
| `HybridRetriever` | `aria/retrieval/hybrid_retriever` | class | fuses vector hits with graph expansion | compliance_query service | active |
| `GraphRetriever` | `aria/retrieval/graph_retriever` | class | multi-hop Cypher expansion from anchor nodes | hybrid retriever | active |
| `rerank_results` | `aria/retrieval/reranker` | function | score fusion with graph-presence boost | hybrid retriever | active |
| `LLMClient` | `aria/llm/client` | class | LiteLLM chat + structured JSON parse with telemetry | agents, compliance_query | active |
| `BaseAgent` | `aria/agents/base` | class | initialize → process → finalize lifecycle with metrics | all agents | stable |
| `SupervisorAgent` | `aria/agents/supervisor` | class | intent classification and routing metadata | orchestration nodes, tests | active |
| `EntityExtractorAgent` | `aria/agents/entity_extractor` | class | LLM entity extraction → ExtractedEntities | wiring, orchestration | active |
| `GraphBuilderAgent` | `aria/agents/graph_builder` | class | ExtractedEntities → Neo4j writes | wiring, orchestration | active |
| `ImpactAnalyzerAgent` | `aria/agents/impact_analyzer` | class | multi-hop impact graph traversal → ImpactReport | impact_report service, orchestration | active |
| `ReportGeneratorAgent` | `aria/agents/report_generator` | class | ImpactReport → markdown report + remediation tasks | orchestration | active |
| `ARIAState` | `aria/orchestration/scratch/state` | type | canonical orchestration state (Pydantic) | scratch + langgraph engines | active |
| `ToolPorts` | `aria/orchestration/scratch/nodes` | type | Protocol for MCP-shaped tool surface in nodes | scratch graph, MCP adapter | active |
| `build_default_graph` / `execute_graph` | `aria/orchestration/scratch/graph` | function | assemble and run scratch orchestration with tracing | tests, evals | active |
| `CANONICAL_SCRATCH_*_PATH` | `aria/orchestration/scratch/paths` | constant | canonical node sequences for eval alignment | tests/eval, fixtures | active |
| `TOOL_DEFINITIONS` | `aria/protocols/mcp/tools` | constant | MCP tool metadata + input schemas | MCP server | stable |
| `MCPToolServer` | `aria/protocols/mcp/server` | class | dispatches named tools to graph/vector backends | orchestration adapter | active |
| `AGENT_CARDS` | `aria/protocols/a2a/agent_card` | constant | static agent capability descriptors | A2A registry, API /agents | stable |
| `AgentRegistry` | `aria/protocols/a2a/registry` | class | in-memory agent discovery | connections, API | stable |
| `TaskEnvelope` | `aria/contracts/agent_messages` | type | A2A/orchestration delegated task wrapper | A2A server/client | stable |
| `connect_app_dependencies` | `api/connections` | function | `(**, strict?) → AppConnections` lifespan wiring | API lifespan, CLI status | stable |
| `get_app_connections` | `api/connections` | function | `(Request) → AppConnections` per-request accessor | API routers | stable |
| `placeholder_api_enabled` | `api/config` | function | reads `ARIA_PLACEHOLDER_API` (default true) | query/impact routers | stable |
| `get_telemetry_store` | `aria/observability/telemetry_store` | function | singleton SQLite telemetry writer/reader | LLM client, agents, API | active |
| `ExtractedEntities` | `aria/contracts/regulation` | type | entity extraction output schema | pipeline, agents, graph builder | stable |
| `GraphWritePayload` | `aria/contracts/graph_entities` | type | batch nodes/edges for Neo4j transaction | graph builder, MCP | stable |
| `ImpactReport` | `aria/contracts/impact` | type | full impact analysis result | impact analyzer, report generator | stable |
| `NodeLabel` / `EdgeType` | `aria/contracts/graph_entities` | type | graph label/relationship enums | schema, builder, queries | stable |
