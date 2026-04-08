# ARIA — Automated Regulatory Impact Agent

Multi-agent system that ingests regulatory documents, builds a Neo4j knowledge graph, answers multi-hop compliance queries via GraphRAG retrieval, and produces impact/gap analysis against an organisation's internal systems and policies — all orchestrated through a stateful agent graph and exposed over FastAPI.

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
┌──────────────┐     ┌──────────────┐     ┌──────▼───────┐
│  MCP / A2A   │◀───▶│   FastAPI    │◀────│  Multi-Agent  │
│  Protocols   │     │   Interface  │     │  Orchestrator │
└──────────────┘     └──────────────┘     └──────────────┘
```

**Data path** — Documents (PDF, HTML, plain text) enter the ingestion pipeline, get chunked, optionally entity-extracted, then written to Neo4j as a typed graph (regulations, articles, requirements, systems, teams, jurisdictions, deadlines) and indexed in ChromaDB as vector embeddings. Queries hit a hybrid retriever (vector anchors → graph expansion → fusion/reranking) that feeds context to an LLM for grounded answers with source tracing.

**Orchestration** — A custom stateful graph engine (`aria.orchestration.scratch`) drives an `ARIAState` through named nodes (supervisor, ingestion chain, entity extraction, graph builder, impact analyser). Nodes must return `ARIAState`; invalid returns set `error` instead of crashing. A LangGraph reference implementation exists under `aria.orchestration.langgraph_reference` for comparison.

**Agents** — Supervisor classifies intent and delegates to specialised agents: `EntityExtractorAgent`, `GraphBuilderAgent`, `IngestionAgent`, `ImpactAnalyzerAgent`, `ReportGeneratorAgent`, each built on a shared `BaseAgent`.

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

Full-stack Docker (API + DBs): `docker compose --profile full up -d`.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python ≥ 3.11 (CI matrix: 3.12 / 3.13) |
| **Graph DB** | Neo4j 5 (community, APOC plugin) |
| **Vector store** | ChromaDB |
| **LLM** | LiteLLM abstraction (local-first via Ollama) |
| **Orchestration** | Custom stateful graph engine; optional LangGraph |
| **Protocols** | MCP (tool access) · A2A (agent delegation) |
| **API** | FastAPI + Uvicorn |
| **Contracts** | Pydantic v2 (strict mode, schema versioning) |
| **Document parsing** | pdfplumber · BeautifulSoup4 / lxml |
| **Observability** | structlog · prometheus-client |
| **Build / lock** | hatchling · uv |
| **Lint / type-check** | ruff · mypy (strict + Pydantic plugin) |

## Evaluation & Testing

ARIA ships with a layered test and evaluation suite — unit, integration, golden-set regression, E2E, security audits, and a human-review eval store.

| Layer | Location | What it covers |
|-------|----------|----------------|
| **Unit** | `tests/unit/` | Contracts, graph queries, orchestration, LLM structured output, entity extraction, hybrid retrieval |
| **Integration** | `tests/integration/` | End-to-end pipeline with live Neo4j + Chroma |
| **Golden set** | `tests/eval/golden_set/` | YAML cases (retrieval, trace, contract, edge, security) with tiered runs (`fast` / `medium` / `slow`), multi-lens runner, JUnit + JSON reports |
| **E2E** | `tests/eval/e2e/` | `POST /query` against the running app; placeholder by default, live hybrid path in nightly |
| **Security** | `tests/eval/test_security_audit.py` | Auth, CORS, body-limit, header, and protocol surface checks |
| **Eval store** | `tests/eval/eval_store.py` | Append-only JSONL log of eval runs for offline human review |
| **Trajectory** | `tests/eval/test_trajectory_eval.py` | Agent trace and step-sequence analysis |

**CI** (`.github/workflows/ci.yml`) — matrix across Python 3.12/3.13; runs unit, eval subsets, golden fast tier, API contract, and security tests on every push.

**Nightly** (`.github/workflows/nightly.yml`) — spins up Neo4j + Chroma services, seeds the graph, runs full integration + golden slow tier + eval store, and uploads reports and eval artifacts.

## HTTP Surface & Operational Behaviour

### Modes

`ARIA_PLACEHOLDER_API=true` (default): `/impact` and `/query` return documented placeholders with `X-ARIA-Mode: placeholder` — no live infrastructure required.
Set to `false` to run against Neo4j, Chroma, and an LLM; missing dependencies yield `503` with `missing_dependencies`.

### Endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | Liveness probe |
| `/ready` | GET | Readiness — probes Neo4j + Chroma; `200` or `503 degraded` |
| `/ingest/text` | POST | Ingest plain-text regulatory content |
| `/ingest/file` | POST | Multipart file upload (`text/*`, `application/octet-stream`) |
| `/query` | POST | Compliance question → grounded answer with sources |
| `/impact` | GET | Impact / gap summary (placeholder or live) |
| `/agents` | GET | List registered agent cards |
| `/agents/{name}` | GET | Single agent card by slug |
| `/a2a/*` | — | A2A protocol surface (card, tasks, health) |

### Hardening

- **Auth** — set `API_KEY` / `ARIA_API_KEY` to gate all routes (except `/health`) via `X-API-Key` or `Authorization: Bearer`. `A2A_SHARED_SECRET` protects `/a2a/card` and `/a2a/tasks`.
- **Body limits** — `ARIA_MAX_INGEST_BODY_BYTES` (default 12 MiB) enforced at middleware; `INGEST_MAX_BYTES` for multipart uploads. Reverse-proxy enforcement recommended in addition.
- **CORS** — `CORS_ORIGINS` / `CORS_ALLOW_ORIGINS` (defaults to local dev URLs).
- **Production mode** — `DEPLOYMENT_ENV=production` disables `/docs` and OpenAPI JSON export.
- **Contracts** — request bodies use `extra="forbid"` (unknown keys → 422). Contracts carry `SCHEMA_VERSION`; runtime enforcement opt-in via `ARIA_STRICT_SCHEMA_VERSION`.
- **Error handling** — MCP/A2A failures return generic messages to callers; stack traces stay in server logs. `complete_structured` strips nested markdown fences and recovers balanced JSON from malformed LLM output.
- **MCP tools** — `list_tools` exposes `input_schema` and `output_schema` (`ToolResult` envelope) for every tool; no arbitrary Cypher from callers.

## Data Handling

Regulatory text may contain sensitive or personal information. This codebase does **not** perform PII detection, redaction, or retention management. Do not ingest real personal data without external controls (classification, encryption, access logging, data-processing agreements).
