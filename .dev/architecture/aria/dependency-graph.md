Section:      dependency-graph
Version:      1.0.1
Last updated: 2026-05-24

## Internal dependencies

| Dependent | Depends on | Nature of coupling | Risk if changed independently |
|-----------|-----------|--------------------|------------------------------|
| `aria/agents/*` | `aria/contracts/*` | All agent I/O typed against shared Pydantic schemas | Schema drift breaks extraction, graph writes, and A2A envelopes |
| `aria/graph/builder` | `aria/contracts/regulation`, `aria/contracts/graph_entities` | Domain-to-graph mapping assumes NodeLabel/EdgeType alignment with `schema.VALID_EDGES` | Invalid edges rejected at write time; silent graph shape drift if enums diverge |
| `aria/graph/queries` | Neo4j label/property conventions | Cypher strings embed literal labels matching contract enums | Renamed labels break all named queries and MCP graph_query |
| `aria/retrieval/hybrid_retriever` | `vector_store`, `graph_retriever`, `reranker` | Fusion scoring assumes RetrievedChunk metadata keys and GraphContext shape | Retrieval quality regressions without coordinated contract update |
| `aria/orchestration/scratch/nodes` | `ToolPorts` protocol | Nodes call tool methods by name; MCP adapter exists but unused in production | New node tools require parallel MCP tool + adapter method |
| `aria/orchestration/scratch/paths` | `scratch/edges.EDGE_MAP`, `scratch/graph.build_default_graph` | Canonical path constants must match edge routing and default graph topology | Eval trajectory tests fail on orchestration refactors |
| `aria/services/compliance_query` | `aria/retrieval/*`, `aria/llm/client` | **Production query path** — bypasses scratch orchestration and MCP | HTTP/CLI query behavior diverges from scratch free_query_node semantics |
| `aria/services/impact_report` | `aria/agents/impact_analyzer` | Service wraps agent for shared HTTP/CLI surface | Agent interface change breaks API without service update |
| `api` | `aria/services`, `aria/health`, `aria/ingestion` | Shared-service pattern for query/impact only | Duplicate logic if new entry points skip services layer |
| `aria/cli` | `api.config`, `api.connections` | CLI reuses API config and connection wiring (package inversion) | CLI breaks if api module layout changes |
| `aria/ingestion/wiring` | `EntityExtractorAgent`, `GraphBuilderAgent`, `VectorStore`, `Neo4jClient` | Full ingest callables for CLI only; HTTP /ingest/* chunk-only by design | API and CLI ingest intentionally diverge |
| `api/connections` | `AGENT_CARDS`, `Neo4jClient`, `VectorStore` | Lifespan populates AppConnections on app.state | Routers assume connections object shape |
| `aria/protocols/mcp/server` | `aria/graph/queries.QUERIES` | Tool input restricted to registered query names; not on production call graph | Adding queries requires tools.py + queries.py sync |
| `aria/protocols/a2a/*` | `httpx`, `AgentCard` registry | Implemented and tested; A2AServer not mounted on api/main.py | Dead code path until router mounted |
| `aria/observability/*` | multiple writers (LLM, agents, HTTP middleware) | Shared SQLite schema with threading lock | Schema migration affects all telemetry consumers |
| `aria/llm/client` | LiteLLM, telemetry_store, metrics | Default max_retries=3, timeout=120s; complete_structured repair is separate call | Retry/timeout changes affect all LLM-dependent features |

## External dependencies

| Dependency | Version pinned | Role in project | Sensitivity |
|------------|---------------|-----------------|-------------|
| Python | >=3.11 (pyproject) | runtime | low |
| FastAPI | >=0.115 | REST API framework | medium |
| Pydantic | >=2.10 | contracts, tool schemas, service DTOs | medium |
| pydantic-settings | >=2.7 | **declared but unused** — no BaseSettings in codebase; all config via os.getenv | low (dead dependency) |
| neo4j (driver) | >=5.27 | async Bolt client to knowledge graph | medium |
| chromadb | >=1.5.6,<2 | vector store HTTP client | high — major version capped |
| litellm | >=1.60 | unified LLM provider interface | high — structured output parsing sensitive |
| pdfplumber | >=0.11 | PDF text extraction | medium |
| beautifulsoup4 | >=4.12 | HTML parsing | low |
| lxml | >=5.3 | HTML parser backend | low |
| httpx | >=0.28 | HTTP client (A2A client; tests) | low |
| prometheus-client | >=0.21 | /metrics exposition | low |
| structlog | >=24.4 | JSON structured logging | low |
| typer | >=0.12 | CLI framework | low |
| uvicorn | >=0.34 | ASGI server | low |
| langgraph | >=0.2 (optional) | reference orchestration only; no production or test imports of build_langgraph | medium — optional, isolated |
| Neo4j (Docker) | 5.26.2-community | graph database service | medium |
| Chroma (Docker) | 1.5.6 | vector database service | high — pinned to match client constraint |
| Ollama / remote LLM | unversioned | local-first LLM via LiteLLM | high — model output format affects extraction |
