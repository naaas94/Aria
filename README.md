# ARIA — Automated Regulatory Impact Agent

GraphRAG-powered multi-agent system for regulatory compliance analysis. Ingests regulatory documents, builds a Neo4j knowledge graph, answers multi-hop compliance queries, and routes remediation tasks through a stateful orchestration layer.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Regulatory  │────▶│  Ingestion   │────▶│  Knowledge   │
│  Documents   │     │  Pipeline    │     │  Graph (Neo4j)│
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                     ┌──────────────┐     ┌──────▼───────┐
                     │  ChromaDB    │◀───▶│   GraphRAG   │
                     │  Vectors     │     │  Retrieval   │
                     └──────────────┘     └──────┬───────┘
                                                 │
                     ┌──────────────┐     ┌──────▼───────┐
                     │   FastAPI    │◀────│  Multi-Agent  │
                     │   Interface  │     │  Orchestrator │
                     └──────────────┘     └──────────────┘
```

## Quickstart

```bash
# 1. Clone and install
git clone <repo-url> && cd aria
pip install -e ".[dev]"
# Reproducible env (optional): uv sync && uv run pytest

# 2. Copy environment template
cp .env.example .env

# 3. Start infrastructure
docker compose up -d neo4j chromadb

# 4. Seed sample data
python scripts/seed_graph.py

# 5. Run the API
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

# 6. Run tests
pytest
```

## Key Concepts

| Concept | Location | Documentation |
|---------|----------|---------------|
| Knowledge Graph | `aria/graph/` | `docs/01_knowledge_graphs.md` |
| GraphRAG | `aria/retrieval/` | `docs/03_graphrag_vs_vector_rag.md` |
| Scratch Orchestration | `aria/orchestration/scratch/` | `docs/08_stateful_graphs_from_scratch.md` |
| MCP Protocol | `aria/protocols/mcp/` | `docs/05_mcp_protocol.md` |
| A2A Protocol | `aria/protocols/a2a/` | `docs/06_a2a_protocol.md` |
| LangGraph Reference | `aria/orchestration/langgraph_reference/` | `docs/09_langgraph_reference.md` |

## Tech Stack

- **Graph DB**: Neo4j 5 (local Docker)
- **Vector Store**: ChromaDB
- **LLM**: Ollama + LiteLLM abstraction
- **Orchestration**: Custom stateful graph + LangGraph reference
- **Protocols**: MCP (tool access) + A2A (agent delegation)
- **API**: FastAPI
- **Contracts**: Pydantic v2

## Portfolio defaults vs production checklist

This repo is a local / portfolio artifact but is structured with production-style boundaries:

- **Regression suite**: [`tests/eval/test_edge_cases.py`](tests/eval/test_edge_cases.py) covers ingestion limits, Unicode, orchestration guards, LLM JSON parsing, impact contracts, and HTTP edge cases. Run: `pytest tests/eval/test_edge_cases.py -v`.
- **Orchestration**: The scratch engine rejects non-`ARIAState` node returns and sets `error` instead of crashing.
- **LLM**: `complete_structured` strips nested markdown fences and can extract a balanced JSON object/array when the model adds prose or broken wrappers.
- **Impact**: `ImpactReport` aligns `total_requirements` with reported gaps when upstream sends inconsistent zeros, and `risk_level` uses a bounded denominator.
- **API**: Request bodies for `/ingest/text` and `/query` use `extra="forbid"` (unknown JSON keys → 422). Empty `regulation_id` is normalized to `null`. POSTs under `/ingest` are rejected with **413** when `Content-Length` exceeds `ARIA_MAX_INGEST_BODY_BYTES` (default 12 MiB).
- **HTTP contracts**: `GET /health` is liveness only. `GET /ready` probes Neo4j and Chroma via env (see `api/readiness.py`) and returns `200` when both succeed, else `503` with `status: degraded`. With `ARIA_PLACEHOLDER_API=true` (default), `GET /impact` and `POST /query` return documented placeholders and set `X-ARIA-Mode: placeholder`. Set `ARIA_PLACEHOLDER_API=false` to run `ImpactAnalyzerAgent` against Neo4j and hybrid/vector retrieval plus an LLM; missing dependencies yield `503` with `missing_dependencies`. The HTTP impact payload remains `ImpactSummaryResponse` (a summary DTO); the full analyzer contract is `ImpactReport` in `aria.contracts.impact`.
- **Schema versions**: Contracts carry `SCHEMA_VERSION` defaults. Runtime enforcement is opt-in via `ARIA_STRICT_SCHEMA_VERSION` (see `aria.contracts._strict`).
- **MCP**: `list_tools` exposes `input_schema` and a documented `output_schema` envelope (`ToolResult`) for every tool.
- **Agent registry**: `connect_app_dependencies` registers every entry in `AGENT_CARDS` into `AgentRegistry`; `GET /agents` reads that registry (slug lookups for `GET /agents/{name}` still use `AGENT_CARDS` keys).
- **Security (portfolio discipline)**: Set `API_KEY` or `ARIA_API_KEY` to require `X-API-Key` or `Authorization: Bearer` on all routes except `GET /health`. Set `A2A_SHARED_SECRET` so agent routers require `X-A2A-Secret` on `/a2a/card` and `/a2a/tasks` (`/a2a/health` stays open for probes). CORS is driven by `CORS_ORIGINS` or `CORS_ALLOW_ORIGINS` (defaults to local dev URLs; use `*` only for local experimentation—wildcard disables credentialed cookies). `DEPLOYMENT_ENV=production` disables `/docs` and the OpenAPI JSON export. Multipart `/ingest/file` enforces `INGEST_MAX_BYTES` and allows `text/*` or `application/octet-stream`. MCP tool failures and A2A task failures return generic messages to callers; stack traces stay in logs. Non-local LLM endpoints require a real `LLM_API_KEY` (Ollama + loopback URLs keep the placeholder key).
- **Not enforced by default**: Strict `Content-Type` requirements for JSON routes (many clients omit it; Starlette may still parse the body). Tighten at a reverse proxy if needed.

## Data handling

Regulatory text may contain sensitive or personal information. This codebase does **not** perform PII detection, redaction, or retention management. Do not upload real personal data unless your deployment adds external controls (classification, encryption, access logging, and data processing agreements as required).

## Reverse proxy note

For production-style deployments, enforce a maximum request body size at nginx, Traefik, or your cloud load balancer in addition to `ARIA_MAX_INGEST_BODY_BYTES` and `INGEST_MAX_BYTES`.
