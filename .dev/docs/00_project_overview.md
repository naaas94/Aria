# ARIA — Project Overview and Learning Guide

This document is the entry point for understanding what ARIA does, why each piece exists, and how to navigate the codebase and documentation. If you only read one file, read this one.

---

## What ARIA Is

ARIA (Automated Regulatory Impact Agent) is a system that ingests regulatory documents (EU AI Act, GDPR, etc.), extracts structured entities, builds a knowledge graph, and answers multi-hop compliance questions that flat vector search cannot handle.

The question it answers:

> "Which requirements from this regulation affect our systems, have no existing policy coverage, and which teams are responsible?"

Answering that requires chaining through five entity types and their relationships — regulation to articles to requirements to systems to teams, with a policy-coverage check along the way. That is a graph traversal problem, not a similarity search problem.

---

## The Core Idea in 60 Seconds

1. A regulatory document arrives (PDF or HTML).
2. An **ingestion pipeline** parses it, chunks it, and uses an LLM to extract structured entities (regulations, articles, requirements, deadlines).
3. Those entities are written to a **Neo4j knowledge graph** as nodes and edges, and their text is embedded into **ChromaDB** as vectors.
4. When a user asks a compliance question, **GraphRAG** retrieval finds relevant chunks via vector similarity, then expands into the graph neighborhood to pull relational context that similarity alone misses.
5. A **multi-agent orchestration engine** routes the work — a supervisor classifies intent and delegates to specialized agents (ingestion, entity extraction, graph building, impact analysis, report generation).
6. Agents access the graph and vector store through **MCP** (Model Context Protocol) tool interfaces, and can delegate to each other across process boundaries via **A2A** (Agent-to-Agent) protocol.

---

## Architecture at a Glance

```
Regulatory Documents
        |
        v
┌─────────────────────────────────────────────────────┐
│  Ingestion Pipeline                                  │
│  (PDF/HTML parsing → chunking → entity extraction)   │
│  aria/ingestion/                                     │
└───────────┬────────────────────┬─────────────────────┘
            |                    |
            v                    v
    ┌──────────────┐     ┌──────────────┐
    │  Neo4j       │     │  ChromaDB    │
    │  Knowledge   │     │  Vector      │
    │  Graph       │     │  Store       │
    │  aria/graph/ │     │  aria/       │
    │              │     │  retrieval/  │
    └──────┬───────┘     └──────┬───────┘
           |                    |
           └────────┬───────────┘
                    v
          ┌──────────────────┐
          │  GraphRAG        │
          │  Hybrid Retrieval│
          │  aria/retrieval/ │
          └────────┬─────────┘
                   |
                   v
          ┌──────────────────┐       ┌─────────────────┐
          │  Orchestration   │──────>│  MCP Tool Server │
          │  Engine          │       │  aria/protocols/ │
          │  aria/           │       │  mcp/            │
          │  orchestration/  │       └─────────────────┘
          │  scratch/        │
          └────────┬─────────┘       ┌─────────────────┐
                   |            ────>│  A2A Delegation  │
                   v                 │  aria/protocols/ │
          ┌──────────────────┐       │  a2a/            │
          │  FastAPI         │       └─────────────────┘
          │  api/            │
          └──────────────────┘
```

---

## What You Will Learn

ARIA is built to teach these concepts by implementing them, not just describing them:

| Concept | What you learn | Where to start |
|---------|---------------|----------------|
| Knowledge graphs | Property graph modeling, schema design, Cypher queries | [01_knowledge_graphs.md](01_knowledge_graphs.md), [02_property_graph_schema.md](02_property_graph_schema.md) |
| GraphRAG | Why vector search alone is not enough, hybrid retrieval with graph expansion | [03_graphrag_vs_vector_rag.md](03_graphrag_vs_vector_rag.md) |
| Graph Neural Networks | GCN, GAT, GraphSAGE — context for MLE interviews, contrast with symbolic GraphRAG | [04_gnns_overview.md](04_gnns_overview.md) |
| MCP | Tool exposure protocol — how agents discover and call tools safely | [05_mcp_protocol.md](05_mcp_protocol.md) |
| A2A | Agent-to-Agent delegation — agent cards, registries, task envelopes | [06_a2a_protocol.md](06_a2a_protocol.md) |
| Agent orchestration | ReAct, Plan-Execute, Supervisor patterns — why and when | [07_agent_orchestration_patterns.md](07_agent_orchestration_patterns.md) |
| Building an engine from scratch | State, nodes, edges, execution loop — no framework needed | [08_stateful_graphs_from_scratch.md](08_stateful_graphs_from_scratch.md) |
| LangGraph | Framework comparison — same graph, framework-expressed | [09_langgraph_reference.md](09_langgraph_reference.md) |
| Evaluation | How to measure agentic system quality — trajectories, retrieval, contracts | [10_evaluation_agentic_systems.md](10_evaluation_agentic_systems.md) |
| Tradeoffs | Honest assessment of what works, what does not, what is portfolio vs production | [11_tradeoffs_and_concerns.md](11_tradeoffs_and_concerns.md) |

---

## Suggested Reading Paths

### Full walkthrough (recommended first time)

Read in order. Each doc builds on the previous one.

```
01  Knowledge Graphs       — what the data layer is
02  Property Graph Schema  — how ARIA models the domain
03  GraphRAG vs Vector RAG — how retrieval works over that graph
04  GNNs Overview          — optional: ML context for the graph layer
05  MCP Protocol           — how agents access tools
06  A2A Protocol           — how agents delegate to each other
07  Orchestration Patterns — why ARIA uses a supervisor pattern
08  Stateful Graphs        — the scratch engine that runs it
09  LangGraph Reference    — the same logic in a framework
10  Evaluation             — how to measure quality
11  Tradeoffs              — where the limits are
```

### Shortcut: "I care about retrieval"

Read 01 → 02 → 03 (optionally 04). Then look at `aria/retrieval/` and `tests/eval/graphrag_vs_vector_rag.py`.

### Shortcut: "I care about agent systems"

Read 07 → 08 → 09, then 05 → 06. Look at `aria/orchestration/scratch/` and `aria/agents/`.

### Shortcut: "I want to understand the protocols"

Read 05 → 06. Compare `aria/protocols/mcp/` (tools) with `aria/protocols/a2a/` (agents).

---

## Code Map

Here is where each concept lives in the codebase:

### Domain contracts — `aria/contracts/`

All Pydantic v2 schemas that define the shape of data flowing through the system. These are the single source of truth consumed by every other layer.

- [`regulation.py`](../aria/contracts/regulation.py) — Regulation, Article, Requirement, ExtractedEntities
- [`graph_entities.py`](../aria/contracts/graph_entities.py) — GraphNode, GraphEdge, GraphWritePayload, NodeLabel, EdgeType
- [`impact.py`](../aria/contracts/impact.py) — ImpactReport, AffectedAsset, RemediationTask
- [`agent_messages.py`](../aria/contracts/agent_messages.py) — AgentMessage, TaskEnvelope (used by A2A)

### Knowledge graph — `aria/graph/`

Neo4j schema, driver wrapper, named query library, and graph builder.

- [`schema.py`](../aria/graph/schema.py) — Constraint and index DDL, valid edge definitions
- [`client.py`](../aria/graph/client.py) — Async Neo4j driver wrapper
- [`queries.py`](../aria/graph/queries.py) — Allow-listed Cypher queries (no arbitrary execution)
- [`builder.py`](../aria/graph/builder.py) — Idempotent MERGE operations from contracts to graph

### Ingestion — `aria/ingestion/`

Document parsing, chunking, and the pipeline that ties parsing to entity extraction to graph/vector writes.

- [`parsers/pdf_parser.py`](../aria/ingestion/parsers/pdf_parser.py) — pdfplumber-based PDF extraction
- [`parsers/html_parser.py`](../aria/ingestion/parsers/html_parser.py) — BeautifulSoup HTML extraction
- [`chunker.py`](../aria/ingestion/chunker.py) — Sentence-boundary chunking with overlap
- [`pipeline.py`](../aria/ingestion/pipeline.py) — Orchestrates parse → chunk → extract → write with idempotency

### Retrieval — `aria/retrieval/`

The GraphRAG implementation: vector search, graph expansion, and fusion.

- [`vector_store.py`](../aria/retrieval/vector_store.py) — ChromaDB interface
- [`graph_retriever.py`](../aria/retrieval/graph_retriever.py) — Multi-hop Cypher expansion from anchor nodes
- [`hybrid_retriever.py`](../aria/retrieval/hybrid_retriever.py) — Fuses vector + graph results
- [`reranker.py`](../aria/retrieval/reranker.py) — Scoring with graph-presence boost

### Agents — `aria/agents/`

The agent layer: a base class and six specialized agents.

- [`base.py`](../aria/agents/base.py) — BaseAgent with initialize/process/finalize lifecycle
- [`supervisor.py`](../aria/agents/supervisor.py) — Intent classification and routing
- [`ingestion_agent.py`](../aria/agents/ingestion_agent.py) — Document processing trigger
- [`entity_extractor.py`](../aria/agents/entity_extractor.py) — LLM-powered entity extraction
- [`graph_builder.py`](../aria/agents/graph_builder.py) — Entities to graph writes
- [`impact_analyzer.py`](../aria/agents/impact_analyzer.py) — Multi-hop impact assessment
- [`report_generator.py`](../aria/agents/report_generator.py) — Markdown report + remediation tasks

### Orchestration — `aria/orchestration/`

Two implementations of the same execution graph. The scratch version is the pedagogical core; LangGraph is the framework mirror.

- [`scratch/state.py`](../aria/orchestration/scratch/state.py) — ARIAState (the canonical typed state)
- [`scratch/nodes.py`](../aria/orchestration/scratch/nodes.py) — Node functions + ToolPorts protocol
- [`scratch/edges.py`](../aria/orchestration/scratch/edges.py) — Conditional routing table
- [`scratch/graph.py`](../aria/orchestration/scratch/graph.py) — Execution engine with tracing
- [`langgraph_reference/`](../aria/orchestration/langgraph_reference/) — Same topology via LangGraph StateGraph

### Protocols — `aria/protocols/`

MCP for tool access, A2A for agent delegation. These are separate concerns: MCP answers "what can I call?", A2A answers "who can do this for me?".

- [`mcp/tools.py`](../aria/protocols/mcp/tools.py) — Tool definitions with Pydantic input schemas
- [`mcp/server.py`](../aria/protocols/mcp/server.py) — Tool server + MCPToolPortsAdapter bridge
- [`a2a/agent_card.py`](../aria/protocols/a2a/agent_card.py) — Agent capability descriptors
- [`a2a/registry.py`](../aria/protocols/a2a/registry.py) — In-memory agent discovery
- [`a2a/client.py`](../aria/protocols/a2a/client.py) — Outbound task delegation
- [`a2a/server.py`](../aria/protocols/a2a/server.py) — Inbound task reception (FastAPI router)

### API — `api/`

FastAPI REST interface exposing ingestion, queries, impact reports, and agent discovery.

- [`main.py`](../api/main.py) — App setup with health check
- [`routers/ingest.py`](../api/routers/ingest.py) — POST /ingest/text, POST /ingest/file
- [`routers/query.py`](../api/routers/query.py) — POST /query (compliance questions)
- [`routers/impact.py`](../api/routers/impact.py) — GET /impact/{regulation_id}
- [`routers/agents.py`](../api/routers/agents.py) — GET /agents (A2A registry view)

### Tests — `tests/`

Unit tests run without external services. Integration tests use the FastAPI test client. Eval tests benchmark retrieval quality and agent behavior.

- [`unit/test_graph_queries.py`](../tests/unit/test_graph_queries.py) — Query library, schema, contracts
- [`unit/test_orchestration.py`](../tests/unit/test_orchestration.py) — Edge routing, state transitions, full execution
- [`unit/test_hybrid_retrieval.py`](../tests/unit/test_hybrid_retrieval.py) — Reranker scoring
- [`eval/graphrag_vs_vector_rag.py`](../tests/eval/graphrag_vs_vector_rag.py) — Retrieval quality comparison
- [`eval/agent_trace_analysis.py`](../tests/eval/agent_trace_analysis.py) — Agent decision trace evaluation

---

## Key Design Decisions

These are the architectural choices that shape the project, with pointers to where each is explained in depth:

**Contracts first.** Every data shape is a versioned Pydantic model in `aria/contracts/`. Agents, MCP tools, A2A envelopes, and the graph builder all import from the same source. This prevents schema drift across boundaries. See [02_property_graph_schema.md](02_property_graph_schema.md).

**Named queries, not arbitrary Cypher.** The MCP `graph_query` tool does not accept raw Cypher from the LLM. It resolves named, parameterized queries from `aria/graph/queries.py`. This limits the blast radius of a bad LLM output. See [05_mcp_protocol.md](05_mcp_protocol.md).

**Scratch before framework.** The orchestration engine in `aria/orchestration/scratch/` is implemented from first principles — state, nodes, edges, and a loop. The LangGraph version in `langgraph_reference/` implements the identical graph to show what the framework buys you (and what it hides). See [08_stateful_graphs_from_scratch.md](08_stateful_graphs_from_scratch.md) and [09_langgraph_reference.md](09_langgraph_reference.md).

**MCP for tools, A2A for agents.** These are not interchangeable. MCP is the boundary for "what operations can I perform?" (query the graph, search vectors). A2A is the boundary for "which agent can handle this task?" (delegate impact analysis to a separate process). See [05_mcp_protocol.md](05_mcp_protocol.md) and [06_a2a_protocol.md](06_a2a_protocol.md).

**Idempotent ingestion.** Documents are identified by content hash. Re-ingesting the same document is a no-op. Graph writes use MERGE (create-or-update). This makes the pipeline safe to replay after partial failures. See [02_property_graph_schema.md](02_property_graph_schema.md).

**Early evaluation.** Retrieval quality is measured from the start with a fixed question set and scoring rubric, not bolted on at the end. See [10_evaluation_agentic_systems.md](10_evaluation_agentic_systems.md).

---

## What This Project Is Not

This is a personal implementation of production patterns, not an enterprise system. Some honest scope boundaries:

- **Local infrastructure** — Neo4j via Docker, ChromaDB, Ollama. Not managed cloud services.
- **Sample corpus** — Synthetic regulatory excerpts, not live compliance feeds.
- **Minimal protocols** — MCP and A2A follow the respective specs but implement the subset needed here, not the full protocol surface.
- **No LangChain** — LangGraph is used as a named reference alongside the hand-rolled engine. It is an optional dependency, not the core.

For a frank discussion of what works and what does not, see [11_tradeoffs_and_concerns.md](11_tradeoffs_and_concerns.md).

---

## Getting Started

```bash
# Install
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env

# Start Neo4j and ChromaDB
docker compose up -d neo4j chromadb

# Seed sample data
python scripts/seed_graph.py

# Run the API
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

# Run tests
pytest
```

Then open the docs in order, starting with [01_knowledge_graphs.md](01_knowledge_graphs.md), and follow along with the code.
