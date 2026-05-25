Section:      integration-seams
Version:      1.0.0
Last updated: 2026-05-24

```
Seam:          Neo4j knowledge graph
Direction:     bidirectional
Protocol:      Bolt (neo4j Python driver)
Auth:          username/password via NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
Data sent:     MERGE nodes/edges, ingestion progress records, constraint DDL
Data received: query result rows from allow-listed Cypher
Error modes:   connection refused, auth failure, health check timeout, Cypher constraint violations
Retry policy:  none at driver: driver connect once per lifespan; ingest records partial progress
Owner module:  aria/graph/client, aria/graph/builder, aria/graph/queries
```

```
Seam:          ChromaDB vector store
Direction:     bidirectional
Protocol:      HTTP (chromadb.HttpClient)
Auth:          none (local Docker default)
Data sent:     chunk upserts (ids, documents, metadatas) to collection aria_regulatory_chunks
Data received: semantic search hits with distances and metadata
Error modes:   connection refused, collection missing, dimension mismatch on re-index
Retry policy:  none
Owner module:  aria/retrieval/vector_store
```

```
Seam:          LLM provider (Ollama default, any LiteLLM-supported backend)
Direction:     outbound
Protocol:      HTTP via LiteLLM (chat completions)
Auth:          LLM_API_KEY (placeholder allowed for local Ollama)
Data sent:     prompts for entity extraction, report generation, compliance answers
Data received: text / JSON structured outputs
Error modes:   timeout, invalid JSON, markdown fence wrapping, model refusal, auth errors
Retry policy:  LLMClient internal retry with backoff [needs confirmation on max attempts]
Owner module:  aria/llm/client, aria/health/assessment (readiness probe)
```

```
Seam:          FastAPI HTTP clients (A2A delegation)
Direction:     outbound
Protocol:      HTTP/JSON
Auth:          optional X-A2A-Secret header when A2A_SHARED_SECRET set
Data sent:     TaskEnvelope payloads to peer agent endpoints
Data received: task status and output_payload
Error modes:   401 on missing secret, network errors, task failure status
Retry policy:  none (caller handles TaskStatus.FAILED)
Owner module:  aria/protocols/a2a/client
```

```
Seam:          FastAPI HTTP server (A2A inbound)
Direction:     inbound
Protocol:      HTTP/JSON (FastAPI router mounted on main app)
Auth:          X-A2A-Secret when A2A_SHARED_SECRET configured
Data sent:     agent cards, task responses
Data received: delegated TaskEnvelope requests
Error modes:   401 unauthorized, validation errors, agent not found
Retry policy:  none
Owner module:  aria/protocols/a2a/server, api/main (router mount)
```

```
Seam:          SQLite telemetry database
Direction:     bidirectional
Protocol:      local file (sqlite3)
Auth:          filesystem permissions
Data sent:     llm_calls, requests, agent_executions rows
Data received: aggregated stats for GET /telemetry
Error modes:   disk full, lock contention, write failures (logged; metrics counter incremented)
Retry policy:  none; prune via ARIA_TELEMETRY_RETENTION_DAYS in-process loop or external cron
Owner module:  aria/observability/telemetry_store
```

```
Seam:          Prometheus scraper
Direction:     outbound (metrics exposition)
Protocol:      HTTP GET /metrics (text exposition format)
Auth:          same API key as data routes unless ARIA_OBSERVABILITY_PUBLIC=true
Data sent:     none
Data received: counter/histogram metrics (LLM, MCP, retrieval, agent execution)
Error modes:   401 when key required and missing
Retry policy:  none (scraper-side)
Owner module:  api/routers/telemetry, aria/observability/metrics
```

```
Seam:          Regulatory document filesystem
Direction:     inbound
Protocol:      local file read (PDF, HTML)
Auth:          OS filesystem ACLs
Data sent:     none
Data received: raw document bytes → parsed text
Error modes:   file not found, unsupported suffix, parse failures, oversized upload
Retry policy:  none
Owner module:  aria/ingestion/parsers, aria/ingestion/pipeline, api/routers/ingest
```
