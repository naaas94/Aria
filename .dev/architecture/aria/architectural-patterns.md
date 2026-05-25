Section:      architectural-patterns
Version:      1.1.0
Last updated: 2026-05-24

These are **partially enforced conventions**, not uniform contracts. Several are README-stated but **falsified by current production wiring** (see falsifier notes).

```
Pattern:      contracts-first
Description:  Pydantic v2 models in aria/contracts/* are canonical schemas for agent I/O, graph payloads, impact reports, and A2A envelopes. SCHEMA_VERSION = "0.1.0" in all four contract modules; optional enforcement via ARIA_STRICT_SCHEMA_VERSION.
Falsifier:    grep for BaseModel defined outside aria/contracts/ used as cross-boundary I/O — hits ComplianceQueryRequest (aria/services/compliance_query.py), ImpactSummaryResponse (aria/services/impact_report.py), ARIAState (orchestration). Tests: tests/unit/test_contract_strict.py, tests/eval/test_serialization.py, golden contract lens in tests/eval/golden_set/runner.py. Grade: strong for ingestion/graph/A2A core; weak for API-facing DTOs.
```

```
Pattern:      named-queries-only (graph reads)
Description:  All graph reads go through execute_named_query() in aria/graph/queries.py (10 registered queries). MCP graph_query tool and GraphRetriever comply. Writes use dynamic Cypher in builder.py and ingestion_record.py — intentional exception.
Falsifier:    grep execute_read( callers outside queries.py resolution path — allowed exceptions: ingestion_record.py (dedup), tests. No production caller passes user-supplied Cypher for reads. Tests: tests/unit/test_graph_queries.py, tests/eval/test_security_audit.py (parametrized over QUERIES.keys()).
```

```
Pattern:      shared-services (query and impact)
Description:  API and CLI share run_compliance_query and run_impact_report from aria/services/.
Falsifier:    grep from aria.services in api/routers/{query,impact}.py and aria/cli/commands/{query,impact}.py — both present. Ingestion does NOT use a shared service: aria ingest → ingest_document() + build_full_ingest_wiring(); HTTP /ingest/* is separate chunk-only path. Tests: tests/unit/test_services_compliance_query.py, tests/unit/test_services_impact_report.py.
```

```
Pattern:      scratch-before-framework
Description:  Primary orchestration design is aria/orchestration/scratch/; LangGraph is a comparison artifact. Production runtime does not execute the scratch graph.
Falsifier:    grep build_langgraph / langgraph imports in api/, aria/cli/ → zero. grep build_default_graph outside tests/ and aria/orchestration/ → zero in production code. Scratch orchestration is well-tested but not wired to api/main.py or CLI. Grade: design intent only; production is agent + service direct calls.
```

```
Pattern:      mcp-for-tools
Description:  Tools exposed via in-process MCPServer / MCPToolPortsAdapter; agents program against ToolPorts protocol.
Falsifier:    grep MCPServer( / MCPToolPortsAdapter in non-test code → only aria/protocols/mcp/server.py; adapter never imported elsewhere. Production calls HybridRetriever, VectorStore, agents directly. Tests: tests/eval/test_security_audit.py, golden MCP checks.
```

```
Pattern:      a2a-for-agents
Description:  Agent delegation via A2A cards, registry, client, and server.
Falsifier:    grep A2AClient in non-test code → only aria/protocols/a2a/client.py. A2AServer not mounted in api/main.py (routers: ingest, query, impact, agents, telemetry only). Cards exposed via GET /agents only. README may reference /a2a/* but main app does not include it.
```

```
Pattern:      extra-forbid on public request bodies
Description:  Public HTTP bodies reject unknown JSON keys where ConfigDict(extra="forbid") is applied.
Falsifier:    grep ConfigDict(extra="forbid") — present on api/routers/ingest.py models and ComplianceQueryRequest only; not on impact path models.
```

```
Pattern:      env-based config via os.getenv
Description:  Configuration read from environment variables at call sites (not centralized settings module).
Falsifier:    grep BaseSettings / pydantic_settings / SettingsConfigDict across *.py → zero matches despite pydantic-settings in pyproject.toml.
```

```
Pattern:      base-agent lifecycle and telemetry
Description:  All agents inherit BaseAgent.run() (initialize → process → finalize) with Prometheus and SQLite telemetry hooks.
Falsifier:    agents inherit BaseAgent; metrics covered in tests/unit/test_metrics.py. Scratch graph uses synthetic agent name orchestration.scratch for aggregate telemetry instead of per-node BaseAgent runs.
```

```
Pattern:      generic external error responses
Description:  MCP, A2A, and API 500 handlers return sanitized errors without internal detail leakage.
Falsifier:    tests/eval/test_security_audit.py (MCP error disclosure, API 500 shape).
```

```
Pattern:      readiness data-plane gate
Description:  GET /ready returns HTTP 503 when Neo4j or Chroma fail; LLM status is informational only and does not flip 503.
Falsifier:    api/readiness.py, aria/health/assessment.py; tests/unit/test_health_assessment.py.
```

## Production call graph (actual runtime)

```
HTTP/CLI → aria/services (query, impact)
         → ingestion.pipeline + agents (CLI ingest only)
         → direct Neo4j / Chroma / LLM clients
```

Scratch orchestration, MCP, and LangGraph reference are real, tested subsystems but **not connected** to api/main.py or CLI today.
