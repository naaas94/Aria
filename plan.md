# ARIA — Automated Regulatory Impact Agent
## Cursor Project Specification

---

## 1. Purpose and Learning Objectives

This repository is simultaneously a **working system** and a **learning artifact**.

**Business problem it solves:** When a new or amended regulation is published (EU AI Act, GDPR enforcement decisions, CCPA updates, sector-specific guidance), compliance teams must manually parse the document, cross-reference it against their internal policy library, identify which systems and teams are affected, and track remediation deadlines. This process takes days to weeks, relies on individual expertise, and produces gaps. The multi-hop relational reasoning it requires — "this article affects these system categories → which of our systems qualify → who owns them → do any existing policies already address this → what is the deadline" — is structurally beyond what flat vector RAG can answer.

**What ARIA does:** Ingests regulatory documents, extracts structured entities, builds and updates a Neo4j knowledge graph, answers multi-hop compliance queries via GraphRAG, routes remediation tasks via a multi-agent orchestration layer, and exposes all of this through a FastAPI interface.

**What this repo teaches by building:**
- Knowledge graph modeling for relational domains
- GraphRAG: when and why it outperforms naive vector RAG
- Stateful multi-agent orchestration (LangGraph pattern, implemented from scratch + LangGraph reference)
- MCP: Model Context Protocol for tool exposure to agents
- A2A: Agent-to-Agent protocol for inter-agent discovery and delegation
- Property graph schema design (Neo4j + Cypher)
- Pydantic-validated agent I/O contracts
- Evaluation and observability for agentic systems

---

## 2. Tech Stack

| Layer | Tool | Rationale |
|---|---|---|
| Knowledge graph | Neo4j (local via Docker) | Industry standard property graph DB; Cypher is learnable and widely referenced |
| Vector store | ChromaDB (local) | Lightweight, no managed infra; sits alongside Neo4j for hybrid retrieval |
| Orchestration | Custom stateful graph + LangGraph reference | Build the pattern raw first; LangGraph as named reference |
| LLM | Ollama (local) + LiteLLM abstraction | Local-first, production-switchable |
| Agent I/O contracts | Pydantic v2 | Type-safe, validated schemas for all agent inputs and outputs |
| Tool protocol | MCP (custom implementation) | Exposes Neo4j query tools, vector search, document retrieval |
| Agent interop | A2A (custom implementation) | Agent card discovery, task delegation between independently deployed agents |
| API layer | FastAPI | REST interface; consistent with existing portfolio patterns |
| Document parsing | pdfplumber + BeautifulSoup | PDF and HTML regulatory source ingestion |
| Observability | Prometheus metrics + structured JSON logging | Consistent with SMA and QI patterns |
| Testing | pytest | Unit and integration tests per layer |

No LangChain. No CrewAI. LangGraph is used as a named reference implementation alongside the hand-rolled version — not as a project dependency.

---

## 3. Repository Structure

```
aria/
│
├── README.md                          # System overview, architecture diagram, quickstart
│
├── docs/                              # Conceptual MD files — the pedagogical layer
│   ├── 01_knowledge_graphs.md
│   ├── 02_property_graph_schema.md
│   ├── 03_graphrag_vs_vector_rag.md
│   ├── 04_gnns_overview.md
│   ├── 05_mcp_protocol.md
│   ├── 06_a2a_protocol.md
│   ├── 07_agent_orchestration_patterns.md
│   ├── 08_stateful_graphs_from_scratch.md
│   ├── 09_langgraph_reference.md
│   ├── 10_evaluation_agentic_systems.md
│   └── 11_tradeoffs_and_concerns.md
│
├── aria/                              # Core application package
│   │
│   ├── graph/                         # Knowledge graph layer
│   │   ├── schema.py                  # Node and edge type definitions (Pydantic)
│   │   ├── client.py                  # Neo4j driver wrapper
│   │   ├── queries.py                 # Cypher query library
│   │   ├── builder.py                 # Graph population and update logic
│   │   └── README.md                  # Graph schema documentation with diagrams
│   │
│   ├── retrieval/                     # Hybrid retrieval layer (GraphRAG)
│   │   ├── vector_store.py            # ChromaDB interface
│   │   ├── graph_retriever.py         # Multi-hop Cypher-based retrieval
│   │   ├── hybrid_retriever.py        # Fuses vector and graph results
│   │   └── reranker.py                # Result scoring and merging logic
│   │
│   ├── ingestion/                     # Document ingestion pipeline
│   │   ├── parsers/
│   │   │   ├── pdf_parser.py          # pdfplumber-based PDF extraction
│   │   │   └── html_parser.py         # BeautifulSoup-based HTML extraction
│   │   ├── chunker.py                 # Semantic chunking strategy
│   │   └── pipeline.py                # End-to-end ingestion orchestrator
│   │
│   ├── agents/                        # Agent definitions
│   │   ├── base.py                    # BaseAgent abstract class with lifecycle hooks
│   │   ├── supervisor.py              # Orchestrator agent — routes and delegates
│   │   ├── ingestion_agent.py         # Triggers and monitors ingestion pipeline
│   │   ├── entity_extractor.py        # LLM-powered entity and relationship extraction
│   │   ├── graph_builder.py           # Translates extracted entities into graph writes
│   │   ├── impact_analyzer.py         # Multi-hop graph traversal for impact assessment
│   │   └── report_generator.py        # Structured output generation with Pydantic contracts
│   │
│   ├── orchestration/                 # Stateful graph orchestration
│   │   ├── scratch/                   # Hand-rolled implementation
│   │   │   ├── state.py               # Typed shared state object
│   │   │   ├── nodes.py               # Node definitions (callable units)
│   │   │   ├── edges.py               # Conditional edge logic
│   │   │   └── graph.py               # Graph assembly and execution engine
│   │   └── langgraph_reference/       # LangGraph implementation of same graph
│   │       ├── state.py
│   │       ├── nodes.py
│   │       └── graph.py
│   │
│   ├── protocols/
│   │   ├── mcp/                       # Model Context Protocol implementation
│   │   │   ├── server.py              # MCP server exposing tools to agents
│   │   │   ├── tools.py               # Tool definitions: graph query, vector search, doc fetch
│   │   │   └── README.md              # MCP protocol explained with this implementation as example
│   │   └── a2a/                       # Agent-to-Agent protocol implementation
│   │       ├── agent_card.py          # Agent capability descriptor (A2A spec)
│   │       ├── registry.py            # Local agent card registry (discovery)
│   │       ├── client.py              # A2A client for outbound delegation
│   │       ├── server.py              # A2A server for inbound task reception
│   │       └── README.md              # A2A protocol explained with this implementation as example
│   │
│   ├── contracts/                     # Pydantic schemas for all agent I/O
│   │   ├── regulation.py              # Regulation, Article, Requirement models
│   │   ├── graph_entities.py          # Node and edge schema models
│   │   ├── impact.py                  # ImpactReport, AffectedAsset, RemediationTask
│   │   └── agent_messages.py          # Inter-agent message envelope schemas
│   │
│   ├── llm/                           # LLM abstraction layer
│   │   ├── client.py                  # LiteLLM wrapper with retry and observability
│   │   └── prompts/                   # Prompt templates per agent task
│   │       ├── entity_extraction.py
│   │       ├── impact_analysis.py
│   │       └── report_generation.py
│   │
│   └── observability/
│       ├── metrics.py                 # Prometheus counters and histograms
│       └── logger.py                  # Structured JSON logger
│
├── api/
│   ├── main.py                        # FastAPI app
│   └── routers/
│       ├── ingest.py                  # POST /ingest — trigger document ingestion
│       ├── query.py                   # POST /query — multi-hop compliance query
│       ├── impact.py                  # GET /impact/{regulation_id} — impact report
│       └── agents.py                  # GET /agents — A2A agent registry view
│
├── tests/
│   ├── unit/
│   │   ├── test_graph_queries.py
│   │   ├── test_hybrid_retrieval.py
│   │   ├── test_entity_extraction.py
│   │   └── test_orchestration.py
│   ├── integration/
│   │   ├── test_ingestion_pipeline.py
│   │   └── test_end_to_end.py
│   └── eval/
│       ├── graphrag_vs_vector_rag.py  # Side-by-side retrieval quality comparison
│       └── agent_trace_analysis.py    # Evaluates agent decision traces
│
├── scripts/
│   ├── seed_graph.py                  # Populates Neo4j with sample regulatory data
│   ├── seed_corpus.py                 # Loads sample regulation PDFs into ingestion pipeline
│   └── benchmark_retrieval.py         # Runs retrieval benchmarks and prints results
│
├── docker-compose.yml                 # Neo4j + ChromaDB + API
├── pyproject.toml
└── .env.example
```

---

## 4. Knowledge Graph Schema

### Node Types

```
(:Regulation {id, title, jurisdiction, domain, effective_date, source_url})
(:Article {id, number, title, text_summary, regulation_id})
(:Requirement {id, text, obligation_type, deadline})
(:PolicyDocument {id, title, owner_team, version, last_reviewed})
(:InternalSystem {id, name, description, category, owner_team, data_types})
(:Team {id, name, function, contact})
(:Jurisdiction {id, name, region})
(:Deadline {id, date, type, article_id})
```

### Edge Types

```
(:Regulation)-[:CONTAINS]->(:Article)
(:Article)-[:IMPOSES]->(:Requirement)
(:Regulation)-[:AMENDS]->(:Regulation)
(:Regulation)-[:REFERENCES]->(:Regulation)
(:Regulation)-[:APPLIES_IN]->(:Jurisdiction)
(:Requirement)-[:AFFECTS]->(:InternalSystem)
(:Requirement)-[:ADDRESSED_BY]->(:PolicyDocument)
(:PolicyDocument)-[:OWNED_BY]->(:Team)
(:InternalSystem)-[:OWNED_BY]->(:Team)
(:Article)-[:HAS_DEADLINE]->(:Deadline)
```

### Example multi-hop query (Cypher)

```cypher
MATCH (r:Regulation {title: "EU AI Act"})-[:CONTAINS]->(a:Article)
      -[:IMPOSES]->(req:Requirement)-[:AFFECTS]->(sys:InternalSystem)
      -[:OWNED_BY]->(t:Team)
WHERE NOT (req)-[:ADDRESSED_BY]->(:PolicyDocument)
RETURN r.title, a.number, req.text, sys.name, t.name
ORDER BY a.number
```

This answers: "Which EU AI Act requirements affect our systems, have no existing policy coverage, and which teams are responsible?" — a query that is structurally impossible to answer with vector similarity alone.

---

## 5. Agent Architecture

### Supervisor Agent
- Receives user query or system trigger (new regulation ingested)
- Classifies intent: ingestion request, impact query, gap analysis, report generation
- Routes to appropriate sub-agents via orchestration graph
- Maintains shared state across the pipeline execution

### Ingestion Agent
- Triggered by new document arrival (API call or polling)
- Delegates to parsers, validates output structure
- Hands structured chunks to Entity Extractor
- Reports ingestion status to Supervisor

### Entity Extractor Agent
- Receives structured document chunks
- LLM-powered extraction of: regulations, articles, requirements, obligations, deadlines, referenced regulations, jurisdictions
- All output validated against `contracts/regulation.py` Pydantic schemas
- Handles extraction failures with dead-letter queue pattern

### Graph Builder Agent
- Receives validated entity payloads
- Translates to Cypher MERGE operations (idempotent — safe to re-run)
- Detects conflicts (same regulation, different version) and flags for review
- Updates vector store embeddings in parallel

### Impact Analyzer Agent
- Receives regulation ID or specific article
- Executes multi-hop Cypher traversals via MCP graph query tool
- Identifies: affected systems, owning teams, existing policy coverage, uncovered gaps, deadlines
- Produces structured `ImpactReport` Pydantic object

### Report Generator Agent
- Receives `ImpactReport` from Impact Analyzer
- Generates human-readable summary + structured remediation task list
- Output: Markdown report + JSON task payload

---

## 6. Orchestration: Stateful Graph (Scratch Implementation)

Located in `aria/orchestration/scratch/`. This is the pedagogical core — implement this before touching LangGraph.

### State object
```python
class ARIAState(BaseModel):
    regulation_id: str | None = None
    raw_document: str | None = None
    extracted_entities: ExtractedEntities | None = None
    graph_write_status: GraphWriteStatus | None = None
    impact_report: ImpactReport | None = None
    final_report: str | None = None
    error: str | None = None
    current_node: str = "supervisor"
    history: list[str] = []
```

### Nodes (callable units)
Each node is a function `(state: ARIAState) -> ARIAState`. Nodes do one thing and return updated state. No side effects outside of state mutation and external I/O (graph writes, LLM calls).

### Edges (conditional transitions)
```python
def route_after_supervisor(state: ARIAState) -> str:
    if state.raw_document:
        return "ingestion"
    elif state.regulation_id:
        return "impact_analyzer"
    else:
        return "end"
```

### Execution engine
A simple loop: `current_node = graph.entry_point` → execute node → evaluate edge condition → advance. Supports cycles (agent can loop back to supervisor after tool call). Terminates on `"end"` node or error state.

### LangGraph reference implementation
Located in `aria/orchestration/langgraph_reference/`. Implements the identical graph using LangGraph's `StateGraph` API. The MD file `docs/09_langgraph_reference.md` documents the mapping: what each LangGraph concept corresponds to in the scratch implementation. This is the comparison artifact — same logic, two expressions.

---

## 7. MCP Implementation

Located in `aria/protocols/mcp/`.

The MCP server exposes the following tools to agents:

```python
tools = [
    Tool(
        name="graph_query",
        description="Execute a Cypher read query against the Neo4j knowledge graph",
        input_schema=CypherQueryInput,
        handler=run_cypher_query
    ),
    Tool(
        name="vector_search",
        description="Semantic search over regulatory document chunks",
        input_schema=VectorSearchInput,
        handler=run_vector_search
    ),
    Tool(
        name="hybrid_retrieve",
        description="Combined graph traversal + vector search with result fusion",
        input_schema=HybridRetrievalInput,
        handler=run_hybrid_retrieve
    ),
    Tool(
        name="fetch_regulation",
        description="Retrieve full regulation metadata and article list by ID",
        input_schema=RegulationFetchInput,
        handler=fetch_regulation_from_graph
    )
]
```

The MCP server runs as a sidecar process. Agents call tools via structured JSON requests. The `docs/05_mcp_protocol.md` file explains the protocol layer: message format, tool discovery, capability negotiation, and why this matters versus direct function calls.

---

## 8. A2A Implementation

Located in `aria/protocols/a2a/`.

Each agent publishes an **Agent Card** — a structured JSON descriptor of its capabilities:

```json
{
  "agent_id": "impact-analyzer-01",
  "name": "Impact Analyzer",
  "version": "0.1.0",
  "capabilities": ["regulatory_impact_analysis", "multi_hop_graph_traversal"],
  "input_schema": "ImpactAnalysisRequest",
  "output_schema": "ImpactReport",
  "endpoint": "http://localhost:8001/a2a",
  "protocol_version": "0.1"
}
```

The **registry** (`registry.py`) is a local in-memory + file-persisted store of agent cards. Agents register on startup and query the registry to discover peers.

The **client** (`client.py`) handles outbound delegation: serialize task, POST to peer agent endpoint, await response, validate against expected schema.

The **server** (`server.py`) is a lightweight FastAPI router that each agent mounts to receive inbound A2A tasks.

**Why A2A matters here:** the Ingestion Agent and Impact Analyzer are independently deployable. The Supervisor does not need to know their internal implementation — only their card. This is the architectural claim A2A makes: agent interoperability across team or system boundaries. The `docs/06_a2a_protocol.md` explains the Google spec, compares it to MCP, and documents where this implementation diverges for local-first simplicity.

---

## 9. GraphRAG Implementation

Located in `aria/retrieval/`.

**Indexing phase** (runs after graph population):
1. Each `(:Article)` and `(:Requirement)` node has its `text_summary` embedded and stored in ChromaDB with the node's ID as metadata.
2. Graph community detection (simple: connected component analysis over `:REFERENCES` and `:AMENDS` edges) produces community summaries — these are additional embeddings representing thematic clusters of regulations.

**Query phase:**
1. Query is embedded → ChromaDB retrieves top-K semantically similar chunks
2. Retrieved chunk IDs are used as graph anchors → Cypher traversal expands to neighboring nodes (one or two hops depending on query type)
3. Graph-expanded context + original vector results are fused by `hybrid_retriever.py`
4. Fused context is passed to LLM for answer generation

**Evaluation** (`tests/eval/graphrag_vs_vector_rag.py`): runs a fixed set of multi-hop compliance questions against both pure vector RAG and GraphRAG, scores by answer completeness and factual correctness, prints comparison table. This is the empirical demonstration of why the graph layer matters.

---

## 10. Documentation Layer (docs/)

Each file is a standalone concept document. Structure per file: concept definition → why it matters → how it is implemented in this repo → tradeoffs → further reading.

| File | Contents |
|---|---|
| `01_knowledge_graphs.md` | Property graphs vs RDF, nodes/edges/properties, when graphs > relational |
| `02_property_graph_schema.md` | Schema design for this domain, modeling decisions and tradeoffs |
| `03_graphrag_vs_vector_rag.md` | Vector RAG limitations, GraphRAG indexing + query phases, when each wins |
| `04_gnns_overview.md` | Graph Neural Networks conceptual overview, GCN/GAT/GraphSAGE, relevance to MLE roles |
| `05_mcp_protocol.md` | MCP spec, tool discovery, capability negotiation, implementation walkthrough |
| `06_a2a_protocol.md` | A2A spec (Google 2025), Agent Cards, comparison to MCP, implementation walkthrough |
| `07_agent_orchestration_patterns.md` | ReAct, Plan-Execute, Reflection, Supervisor patterns — when and why |
| `08_stateful_graphs_from_scratch.md` | State, nodes, edges, cycles — the raw pattern without framework abstraction |
| `09_langgraph_reference.md` | LangGraph API walkthrough, mapping to scratch implementation, when to use it |
| `10_evaluation_agentic_systems.md` | Trajectory evaluation, tool call accuracy, retrieval quality, output contracts |
| `11_tradeoffs_and_concerns.md` | Graph vs vector latency, A2A overhead, MCP versioning, local-first limitations |

---

## 11. Implementation Phases

### Phase 1 — Graph Foundation
- Docker Compose with Neo4j + ChromaDB
- Schema definitions in `graph/schema.py`
- Cypher query library for all read patterns
- `seed_graph.py` with sample regulatory data (GDPR, EU AI Act subset)
- `docs/01_knowledge_graphs.md` and `docs/02_property_graph_schema.md`

### Phase 2 — Ingestion Pipeline
- PDF and HTML parsers
- Entity extractor (LLM-powered, Pydantic-validated)
- Graph builder (idempotent MERGE operations)
- Vector store population in parallel
- `seed_corpus.py` with publicly available regulation PDFs

### Phase 3 — Retrieval Layer
- ChromaDB vector search
- Multi-hop Cypher retrieval
- Hybrid fusion
- `docs/03_graphrag_vs_vector_rag.md`
- Retrieval evaluation script

### Phase 4 — Agent Layer (Scratch Orchestration)
- `BaseAgent` abstract class
- All five sub-agents with Pydantic I/O contracts
- Stateful graph: state, nodes, edges, execution engine
- Supervisor routing logic
- `docs/07_agent_orchestration_patterns.md` and `docs/08_stateful_graphs_from_scratch.md`

### Phase 5 — MCP
- MCP server with four tools
- Agent integration (agents call tools via MCP, not direct function calls)
- `docs/05_mcp_protocol.md`

### Phase 6 — A2A
- Agent Card definitions for all agents
- Local registry
- A2A client and server on each agent
- `docs/06_a2a_protocol.md`

### Phase 7 — LangGraph Reference
- LangGraph implementation of Phase 4 orchestration graph
- Side-by-side documentation
- `docs/09_langgraph_reference.md`

### Phase 8 — API + Observability
- FastAPI routers
- Prometheus metrics
- Structured logging
- Docker Compose final configuration

### Phase 9 — Evaluation + Documentation Completion
- End-to-end integration tests
- GraphRAG vs vector RAG benchmark
- Agent trace analysis
- All remaining `docs/` files

---

## 12. Cursor Prompting Notes

When feeding this spec to Cursor, scaffold in phase order. Suggested session structure:

- **Session 1:** "Scaffold the full directory structure from the spec. Create empty files with module-level docstrings describing each file's responsibility. Do not implement yet."
- **Session 2:** "Implement `aria/graph/` — schema, client, queries, builder. Use Neo4j Python driver. All node and edge types from the schema section."
- **Session 3:** "Implement `aria/ingestion/` — PDF parser with pdfplumber, chunker, entity extractor with Pydantic contracts."
- Continue per phase.

Keep sessions scoped to one layer. Cursor loses coherence when asked to implement multiple layers in a single session.

---

## 13. Portfolio Framing

This is a personal implementation of production patterns, not an enterprise system. Honest scope claims:

- Local-first infrastructure (Neo4j via Docker, ChromaDB, Ollama) — not managed cloud equivalents
- Sample regulatory corpus — not a live compliance data feed
- MCP and A2A are custom minimal implementations following the respective specs — not production-grade protocol libraries
- The system demonstrates architectural judgment, not infrastructure scale

The differentiating claim: end-to-end ownership of a multi-agent system with explicit attention to retrieval architecture, agent protocol design, and the tradeoffs between abstraction and control. The `docs/` layer makes the reasoning legible.