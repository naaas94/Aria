Section:      open-questions
Version:      1.1.0
Last updated: 2026-05-24

```
Question:     Should API /ingest/* remain chunk-only, or converge with CLI full ingest (parse → extract → graph → vector)?
Impact:       api/routers/ingest, aria/ingestion/pipeline, aria/ingestion/wiring, operator docs
Code evidence: Unresolved by design. /ingest/* = chunk+hash+metrics only (router docstring). aria ingest = full pipeline via ingest_document(). No shared service; wiring.py states HTTP stays chunking-only.
Closes when:  product decision documented and one code path declared canonical for HTTP ingest
```

```
Question:     Is LangGraph reference a long-term parity target or disposable demo?
Impact:       aria/orchestration/langgraph_reference, optional langgraph extra, eval scope
Code evidence: Leans disposable/reference. Optional extra; _NoopTools stubs; entity_extractor/free_query stubbed; zero tests call build_langgraph(); not on api/ or cli/ paths.
Closes when:  module marked deprecated in module-map or parity tests added and production path declared
```

```
Question:     Will A2A move from in-process registry to cross-process HTTP delegation in production scope?
Impact:       aria/protocols/a2a, docker-compose profiles, A2A_SHARED_SECRET
Code evidence: A2AClient/A2AServer + httpx implemented and tested; main app does not mount A2A router; A2AClient only used in tests. Cards exposed via GET /agents only.
Closes when:  deployment architecture states in-process-only vs multi-container agent mesh; A2A router mounted or explicitly out of scope
```

```
Question:     Telemetry retention — in-process prune (ARIA_TELEMETRY_RETENTION_DAYS) vs external-only for production?
Impact:       api/main lifespan, observability ops, SQLite growth
Code evidence: Prune loop runs only when ARIA_TELEMETRY_RETENTION_DAYS is positive int; unset = no automatic prune (telemetry_store.py doc).
Closes when:  production runbook specifies one retention mechanism
```

```
Question:     When does scratch orchestration + MCP become the production runtime?
Impact:       aria/orchestration/scratch, aria/protocols/mcp, api/main.py, aria/cli, architectural-patterns production call graph
Code evidence: Scratch orchestration, MCP, and LangGraph are real tested subsystems but not connected to api/main.py or CLI. Production today is a parallel, simpler call graph (services + direct clients). Query path resolved: POST /query and aria query use run_compliance_query(), not scratch free_query_node.
Closes when:  explicit decision to wire orchestration/MCP into production entry points, or to demote them to test/eval-only permanently
```

## Resolved (2026-05-24)

**Query path: orchestration vs services** — Resolved in practice: **services**. Both POST /query and `aria query` call `run_compliance_query()` (HybridRetriever + LLM). Scratch `free_query_node` is vector-only snippet listing with different behavior; not used in production.

## Resolved (2026-05-30)

**Placeholder API default (G8)** — `ARIA_PLACEHOLDER_API` code default flipped from `"true"` to `"false"` in `api/config.py` on `dev`. Live mode is the baseline; operators set `ARIA_PLACEHOLDER_API=true` for synthetic placeholder responses without backends. See `.dev/decision-logs/T1-g8-placeholder-default.md`.
