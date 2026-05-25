Section:      module-map
Version:      1.0.1
Last updated: 2026-05-24

| Module path | Role | Key files | Stability |
|-------------|------|-----------|-----------|
| `aria/contracts` | Pydantic v2 schemas — canonical for agent/graph/A2A I/O (API DTOs partially outside) | `regulation.py`, `graph_entities.py`, `impact.py`, `agent_messages.py`, `_strict.py` | stable |
| `aria/graph` | Neo4j schema DDL, async driver, allow-listed Cypher queries, idempotent graph builder, ingestion dedup records | `schema.py`, `client.py`, `queries.py`, `builder.py`, `ingestion_record.py` | stable |
| `aria/ingestion` | Document parse → chunk → extract → write pipeline; CLI full ingest; HTTP chunk-only | `pipeline.py`, `chunker.py`, `wiring.py`, `parsers/pdf_parser.py`, `parsers/html_parser.py` | active |
| `aria/retrieval` | GraphRAG: Chroma vector store, graph expansion, hybrid fusion, reranking | `vector_store.py`, `graph_retriever.py`, `hybrid_retriever.py`, `reranker.py` | active |
| `aria/llm` | LiteLLM wrapper: structured output, 3 retries / 120s timeout default, telemetry | `client.py`, `prompts/*.py` | active |
| `aria/agents` | Six specialized agents plus supervisor; BaseAgent lifecycle; called directly in production ingest/impact | `base.py`, `supervisor.py`, `entity_extractor.py`, `graph_builder.py`, `impact_analyzer.py`, `report_generator.py`, `ingestion_agent.py` | active |
| `aria/orchestration/scratch` | Hand-rolled stateful graph engine — mature tests, **not wired to api/ or cli/** | `state.py`, `nodes.py`, `edges.py`, `graph.py`, `paths.py` | active (code); production wiring experimental |
| `aria/orchestration/langgraph_reference` | LangGraph comparison artifact with NoopTools stubs; zero test imports of build_langgraph | `graph.py` | experimental |
| `aria/protocols/mcp` | MCP tool definitions and server adapter — **not imported by production paths** | `tools.py`, `server.py` | active (code); production wiring experimental |
| `aria/protocols/a2a` | Agent cards, registry, client/server — **A2A router not mounted on main app** | `agent_card.py`, `registry.py`, `server.py`, `client.py` | active (code); production wiring experimental |
| `aria/services` | Shared query/impact logic for HTTP and CLI (ingest intentionally excluded) | `compliance_query.py`, `impact_report.py` | stable |
| `aria/health` | Dependency readiness probes (Neo4j, Chroma, LLM) for /ready, CLI status, ingest preflight | `assessment.py` | stable |
| `aria/observability` | Structured logging, Prometheus metrics, SQLite telemetry store | `logger.py`, `metrics.py`, `telemetry_store.py`, `since_parse.py` | active |
| `aria/cli` | Typer operator CLI; imports api.config and api.connections for shared wiring | `main.py`, `commands/*.py` | active |
| `api` | FastAPI REST layer — auth, middleware, lifespan, route handlers (no A2A mount) | `main.py`, `connections.py`, `readiness.py`, `routers/*.py`, `deps.py`, `config.py` | active |
| `scripts` | Manual dev seeding/benchmarks; mypy excluded; imports tests.eval in places | `seed_graph.py`, `benchmark_retrieval.py` | experimental |
| `tests` | Unit, integration, eval, golden-set regression harness | `unit/`, `integration/`, `eval/`, `fixtures/` | active |
