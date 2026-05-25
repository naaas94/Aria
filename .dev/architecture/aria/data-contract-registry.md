Section:      data-contract-registry
Version:      1.0.0
Last updated: 2026-05-24

```
Contract:       ExtractedEntities
Module:         aria/contracts/regulation
Serialization:  Pydantic model
Version:        0.1.0 (SCHEMA_VERSION constant; unversioned — tracked by git blame)
Purpose:        Canonical output of entity extraction — all entities found in one document
Fields:
  - schema_version: str — contract version gate (optional strict via ARIA_STRICT_SCHEMA_VERSION)
  - source_document_hash: str — content hash for idempotency
  - regulations: list[Regulation] — nested articles, requirements, deadlines
  - jurisdictions: list[Jurisdiction]
  - teams: list[Team]
  - policy_documents: list[PolicyDocument]
  - internal_systems: list[InternalSystem]
Validators:     strict schema_version when ARIA_STRICT_SCHEMA_VERSION set
Consumers:      aria/agents/entity_extractor, aria/graph/builder, aria/ingestion/pipeline, aria/orchestration/scratch/state
Last changed:   2026-05-24
```

```
Contract:       GraphWritePayload
Module:         aria/contracts/graph_entities
Serialization:  Pydantic model
Version:        0.1.0
Purpose:        Batch of nodes and edges committed in one Neo4j transaction
Fields:
  - schema_version: str
  - nodes: list[GraphNode] — label + properties (must include id merge key)
  - edges: list[GraphEdge] — source/target labels and ids, edge_type, optional properties
Validators:     edge validity checked in builder against VALID_EDGES; strict schema_version optional
Consumers:      aria/graph/builder, aria/agents/graph_builder, MCP graph writes
Last changed:   2026-05-24
```

```
Contract:       GraphWriteStatus
Module:         aria/contracts/graph_entities
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Result counts and errors from a graph write operation
Fields:
  - nodes_created, nodes_merged, edges_created, edges_merged: int
  - errors: list[str]
Validators:     success property true when errors empty
Consumers:      graph builder, orchestration state, ingestion pipeline
Last changed:   2026-05-24
```

```
Contract:       GraphQueryResult
Module:         aria/contracts/graph_entities
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Typed wrapper for allow-listed Cypher query result sets
Fields:
  - columns: list[str]
  - rows: list[dict]
  - query_time_ms: float
Validators:     none
Consumers:      aria/graph/queries, MCP graph_query tool
Last changed:   2026-05-24
```

```
Contract:       ImpactReport
Module:         aria/contracts/impact
Serialization:  Pydantic model
Version:        0.1.0
Purpose:        Full regulatory impact analysis for one regulation
Fields:
  - schema_version: str
  - regulation_id, regulation_title: str
  - total_requirements: int
  - affected_systems: list[AffectedAsset]
  - remediation_tasks: list[RemediationTask]
  - coverage_summary: dict[CoverageStatus, int]
Validators:     aligns total_requirements with gap count when upstream omitted; risk_level derived property
Consumers:      impact analyzer, report generator, impact_report service, orchestration state
Last changed:   2026-05-24
```

```
Contract:       AgentMessage
Module:         aria/contracts/agent_messages
Serialization:  Pydantic model
Version:        0.1.0
Purpose:        Envelope for inter-agent communication in orchestration and A2A
Fields:
  - schema_version, message_id, timestamp, message_type, source_agent, target_agent: metadata
  - payload: dict — task-specific body
  - correlation_id: str | None — trace linkage
Validators:     strict schema_version optional
Consumers:      orchestration (future), A2A layer
Last changed:   2026-05-24
```

```
Contract:       TaskEnvelope
Module:         aria/contracts/agent_messages
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Delegated task wrapper for A2A HTTP endpoints
Fields:
  - task_id, status, created_at, updated_at, source_agent, target_agent, task_type: metadata
  - input_payload, output_payload: dict
  - error_detail: str | None
Validators:     mark_in_progress / mark_completed / mark_failed state transitions
Consumers:      aria/protocols/a2a/server, aria/protocols/a2a/client
Last changed:   2026-05-24
```

```
Contract:       ARIAState
Module:         aria/orchestration/scratch/state
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Shared mutable state flowing through scratch and LangGraph orchestration graphs
Fields:
  - regulation_id, raw_document, document_hash, query: optional inputs
  - extracted_entities, graph_write_status, impact_report: pipeline artifacts
  - final_report: str | None — human-readable output
  - error: str | None
  - current_node, history: execution trace
Validators:     is_ingestion_request / is_impact_query / is_free_query derived routing flags
Consumers:      scratch graph engine, langgraph_reference, tests/eval trajectory checks
Last changed:   2026-05-24
```

```
Contract:       ComplianceQueryRequest / ComplianceQueryResponse
Module:         aria/services/compliance_query
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        HTTP/CLI compliance question input and structured answer with open trace dict
Fields:
  - Request: question, regulation_id?, use_graph_rag, top_k
  - Response: answer, sources, retrieval_strategy, trace
Validators:     regulation_id empty string coerced to None; top_k bounded 1–50
Consumers:      api/routers/query, aria/cli/commands/query
Last changed:   2026-05-24
```

```
Contract:       DocumentChunk
Module:         aria/ingestion/chunker
Serialization:  dataclass
Version:        unversioned — tracked by git blame
Purpose:        Text chunk with id, source hash, metadata for vector indexing
Fields:
  - chunk_id, text, source_document_hash, metadata: dict
Validators:     none
Consumers:      chunker, vector store, ingestion pipeline, API chunk-only ingest
Last changed:   2026-05-24
```

```
Contract:       IngestionResult
Module:         aria/ingestion/pipeline
Serialization:  dataclass
Version:        unversioned — tracked by git blame
Purpose:        End-to-end ingest status for CLI and ops visibility
Fields:
  - status: IngestionStatus enum
  - document_hash, chunks_produced, entities_extracted, graph_written, vector_indexed: bool/int flags
  - errors: list[str]
Validators:     none
Consumers:      CLI ingest, integration tests
Last changed:   2026-05-24
```

```
Contract:       AgentCard
Module:         aria/protocols/a2a/agent_card
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        A2A discovery descriptor for agent capabilities and schemas
Fields:
  - agent_id, name, version, description, capabilities, input_schema, output_schema, endpoint, protocol_version
Validators:     supports_capability helper
Consumers:      A2A registry, GET /agents API
Last changed:   2026-05-24
```

```
Contract:       ToolResult
Module:         aria/protocols/mcp/tools
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Standard MCP tool call result envelope
Fields:
  - tool_name, success, data, error, error_code
Validators:     none
Consumers:      MCP server, MCPToolPortsAdapter
Last changed:   2026-05-24
```

```
Contract:       DependencyReport
Module:         aria/health/assessment
Serialization:  dataclass
Version:        unversioned — tracked by git blame
Purpose:        Neo4j/Chroma/LLM readiness booleans plus per-component error messages
Fields:
  - neo4j_ok, chroma_ok, llm_ok: bool
  - errors: dict[str, str]
Validators:     none
Consumers:      GET /ready, aria status, ingest preflight
Last changed:   2026-05-24
```
