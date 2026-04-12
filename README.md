# ARIA — Automated Regulatory Impact Agent

Multi-agent system that ingests regulatory documents, builds a Neo4j knowledge graph, answers multi-hop compliance queries via GraphRAG retrieval, and produces impact/gap analysis against an organisation's internal systems and policies — all orchestrated through a stateful agent graph and exposed over FastAPI.

**Status:** End-to-end pipeline functional with CI and nightly runs. Placeholder mode is the default for safe exploration; live mode requires Neo4j + Chroma + LLM.

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

# 4. Populate the graph (pick one)
# Full pipeline from a file — apply Neo4j schema, then ingest (needs Neo4j + Chroma + LLM):
aria init
aria ingest path/to/document.pdf
# Quick structured sample only (no file pipeline):
# python scripts/seed_graph.py

# 5. Run the API
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
# Or: aria serve

# 6. Run tests
pytest
```

Full-stack Docker (API + DBs): `docker compose --profile full up -d`.

## CLI (`aria`)

After `pip install -e .`, the **`aria`** console script is available. It loads `.env` (via `python-dotenv`) before each subcommand, same as a typical local API process.

| Command | Purpose |
|---------|---------|
| **`aria init`** | Connect to Neo4j (`NEO4J_URI`, …) and run `initialize_schema()`. On a fresh database, run **`aria init`** before **`aria ingest`** (or let the first **`aria ingest`** apply schema unless you pass **`--skip-schema`** after init). |
| **`aria ingest <file>`** | End-to-end ingestion (parse → chunk → entity extraction → Neo4j + Chroma). **Preflight** requires Neo4j, Chroma, **and** LLM to pass; stderr lists `missing: neo4j|chroma|llm: …` on failure. Uses `initialize_schema()` unless **`--skip-schema`** (e.g. after **`aria init`**). |
| **`aria serve`** | Run **`uvicorn api.main:app`** (host, port, reload). |
| **`aria status`** | Probes dependencies (`--json` optional); exit **1** if Neo4j or Chroma checks fail (aligned with **`GET /ready`** data-plane gates). |
| **`aria query`** / **`aria impact`** | Call the same services as **`POST /query`** / **`GET /impact`** in-process (placeholder vs live follows **`ARIA_PLACEHOLDER_API`**). |
| **`aria telemetry`** | Rolling window or **`--since`** — same data idea as **`GET /telemetry`**. |
| **`aria eval`** | Runs the golden eval module (forwards extra args to **pytest**). |

**Readiness (`GET /ready`)** — JSON includes **`neo4j`**, **`chroma`**, and **`llm`** booleans (and optional **`errors`**). **HTTP 200 vs 503** reflects the **data plane only** (Neo4j + Chroma both OK). An LLM failure does **not** force 503, but **`aria ingest`** still requires a healthy LLM in its preflight. The **`llm`** field uses a **cached** minimal LiteLLM probe (default **300s** TTL, `ARIA_READY_LLM_CACHE_TTL_SECONDS`; **`aria status`** and ingest preflight use a fresh probe each run).

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

## HTTP Surface & Operational Behaviour

### Modes

`ARIA_PLACEHOLDER_API=true` (default): `/impact` and `/query` return documented placeholders with `X-ARIA-Mode: placeholder` — no live infrastructure required.
Set to `false` to run against Neo4j, Chroma, and an LLM; missing dependencies yield `503` with `missing_dependencies`.

### Endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | Liveness probe |
| `/ready` | GET | Readiness — JSON includes `neo4j`, `chroma`, `llm`; HTTP `200` vs `503` is **Neo4j + Chroma** only (see [CLI](#cli-aria)) |
| `/ingest/text` | POST | **Chunking smoke path** — hash + in-memory chunks + metrics; **does not** load the knowledge base (see below) |
| `/ingest/file` | POST | Same as `/ingest/text` for multipart uploads (`text/*`, `application/octet-stream`) |
| `/query` | POST | Compliance question → grounded answer with sources |
| `/impact` | GET | Impact / gap summary (placeholder or live) |
| `/agents` | GET | List registered agent cards |
| `/agents/{name}` | GET | Single agent card by slug |
| `/a2a/*` | — | A2A protocol surface (card, tasks, health) |

### How to load documents (developer / offline)

The HTTP `/ingest/*` routes are **not** the full ingestion pipeline: they do not write Neo4j, Chroma, or run entity extraction. They exist to validate request sizing, exercise chunking, and emit metrics.

To actually populate graph + vectors (or exercise the pipeline in code), use **developer-side** paths:

| Path | Role |
|------|------|
| **`aria ingest <file>`** (CLI) | Operator wrapper around the same full pipeline: run **`aria init`** on a fresh DB before first ingest, or let ingest apply schema (skip with **`--skip-schema`** if already initialized). |
| `aria/ingestion/pipeline.py` — `ingest_document()` | End-to-end orchestrator for **files on disk** (PDF/HTML): parse → chunk → optional entity extraction, graph write, vector indexing, optional Neo4j-backed dedup (`IngestionRecord`). Pass injectables for extract/graph/vector; without them, behavior reduces to parse + chunk. |
| `scripts/seed_corpus.py` | Writes sample HTML regulations to a temp dir and calls `ingest_document()` (demo / local runs). |
| `scripts/seed_graph.py` | Inserts **structured sample** `ExtractedEntities` directly into Neo4j (quick graph for dev; not file-based pipeline ingestion). |
| `tests/integration/test_ingestion_pipeline.py` | Integration tests for `ingest_document` with real files and mocked Neo4j dedup. |

Live **`POST /query`** (`ARIA_PLACEHOLDER_API=false`) expects an already-populated Neo4j + Chroma; filling them is **not** done by `POST /ingest/text` or `POST /ingest/file` today.

### Hardening

- **Auth** — set `API_KEY` / `ARIA_API_KEY` to gate all routes except `/health` and `/ready` via `X-API-Key` or `Authorization: Bearer`. `/metrics` and `/telemetry` are also gated unless `ARIA_OBSERVABILITY_PUBLIC=true`. `A2A_SHARED_SECRET` protects `/a2a/card` and `/a2a/tasks`.
- **Body limits** — `ARIA_MAX_INGEST_BODY_BYTES` (default 12 MiB) enforced at middleware; `INGEST_MAX_BYTES` for multipart uploads. Reverse-proxy enforcement recommended in addition.
- **CORS** — `CORS_ORIGINS` / `CORS_ALLOW_ORIGINS` (defaults to local dev URLs).
- **Production mode** — `DEPLOYMENT_ENV=production` disables `/docs` and OpenAPI JSON export.
- **Contracts** — request bodies use `extra="forbid"` (unknown keys → 422). Contracts carry `SCHEMA_VERSION`; runtime enforcement opt-in via `ARIA_STRICT_SCHEMA_VERSION`.
- **Error handling** — MCP/A2A failures return generic messages to callers; stack traces stay in server logs. `complete_structured` strips nested markdown fences and recovers balanced JSON from malformed LLM output.
- **MCP tools** — `list_tools` exposes `input_schema` and `output_schema` (`ToolResult` envelope) for every tool; no arbitrary Cypher from callers.

### Multi-worker and multi-instance deployment

Scaling the API (multiple Uvicorn workers, several containers, or several hosts) is supported for **stateless** request handling, but ingestion deduplication and the default telemetry store are not magically shared across processes.

- **Full ingestion pipeline** — `ingest_document` (`aria/ingestion/pipeline.py`) keeps a per-process in-memory set (`_ingested_hashes`). Without Neo4j-backed state, each worker only knows what it has seen locally, so duplicate documents can be processed more than once. **Pass `neo4j_dedup`** (a `Neo4jClient`) into `ingest_document` so completed content hashes live in Neo4j (`IngestionRecord` nodes) and are loaded on startup; that gives durable idempotency across workers and restarts for a shared graph. (The HTTP `/ingest/text` and `/ingest/file` routes currently chunk only; they do not run this full pipeline.)

- **Telemetry** — HTTP telemetry is persisted to **SQLite** by default (`ARIA_TELEMETRY_DB` in `.env.example`). SQLite uses WAL mode with a per-process connection; concurrent writers from many processes increase lock contention and retries (not a multi-writer log store). If every replica uses its **own local path**, `GET /telemetry` only sees that instance’s file — **fragmented** operational data. For coherent JSON telemetry, prefer a **single writer** (one replica handling telemetry, or one process), **one database file on a shared volume** mounted at the same path for all instances (accepting SQLite’s concurrency limits), or rely on **`GET /metrics` (Prometheus)** / an **external** metrics or log store for high-availability analytics.

## Data Handling

Regulatory text may contain sensitive or personal information. This codebase does **not** perform PII detection, redaction, or retention management. Do not ingest real personal data without external controls (classification, encryption, access logging, data-processing agreements).
