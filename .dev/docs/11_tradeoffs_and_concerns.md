# Tradeoffs and Known Concerns

## Concept definition

Every architecture choice in **ARIA** (Automated Regulatory Impact Agent) trades **latency**, **complexity**, **correctness**, and **operational burden**. This document collects **known tradeoffs** and **honest limits** of the portfolio implementation: where **graph expansion** helps versus hurts, how **A2A** and **MCP** add overhead, what **local-first** stacks sacrifice, how **schema evolution** ripples through the codebase, and why **non-deterministic LLMs** undermine naive evaluation. It complements the technical walkthroughs of **LangGraph**, **GraphRAG**, and the **eval suite** in sibling docs.

## Why it matters

Reviewers and hiring managers distinguish **demonstration code** from **production systems** by whether authors acknowledge **failure modes** and **cost drivers**. Regulatory tooling especially demands clarity: a missed requirement is not merely a bad UX event. Stating tradeoffs explicitly signals **engineering maturity** and guides **next steps** if the project grows beyond a portfolio scope.

## How it is implemented in this repo (context for each concern)

ARIA combines **Neo4j** for structured regulatory and systems knowledge, **ChromaDB** for vector retrieval, **GraphRAG**-style patterns that join graph traversal with text chunks, **scratch orchestration** with an optional **LangGraph** reference, **MCP**-shaped tool servers (**`aria/protocols/mcp/`**), and **A2A** client/server pieces (**`aria/protocols/a2a/`**, API routes under **`api/routers/`**). The **CLI** (**`aria/cli/`**) and **`aria.services`** share query/impact logic with FastAPI. **`aria.health`** powers **`GET /ready`**, **`aria status`**, and stricter **`aria ingest`** preflight (all three of Neo4j, Chroma, LLM). Integration tests and README copy reference **Ollama** for local LLMs. **Pydantic** models in **`aria/contracts/`** define cross-layer payloads. **Evaluation** scaffolding lives in **`tests/eval/`** (including **golden_set**, API contract, and security suites). The following sections map **concerns** to this layout.

### Graph versus vector latency

**Graph queries** (multi-hop Cypher, impact expansion) can return **precise, explainable** paths: regulation to requirement to system to policy coverage. **Vector search** over **ChromaDB** is often **faster** for broad semantic similarity when the question maps to a small number of chunks and does not require relational joins.

**When graph expansion costs outweigh benefit**

- **Shallow questions** with clear lexical anchors (e.g. a single article definition) may be answered from **one or two chunks** without traversing the full ontology.
- **Large fan-out** from a regulation node to thousands of requirements and systems increases **query time** and **result serialization**; pagination and limits become mandatory.
- **Cold graph** or **poor indexing** can make vector fallback **feel** faster even when graph answers would be **more correct**.

**When graph value dominates**

- **Compliance gap** questions that require **joining** systems, teams, policies, and obligations.
- **Auditable paths**: graph results tie to **explicit relationships** suitable for **impact reports** (**`impact_analyzer_node`** in **`aria/orchestration/scratch/nodes.py`**).

The eval module **`graphrag_vs_vector_rag.py`** encodes **multi-hop** versus **single-hop** question types to stress this split; **`requires_multi_hop`** flags questions intended to favor **GraphRAG**.

### Health, readiness, and ingest preflight

- **`GET /health`** — process liveness only; does not prove Neo4j/Chroma/LLM.
- **`GET /ready`** — JSON reports **neo4j**, **chroma**, **llm**; HTTP **200 vs 503** is gated by **Neo4j + Chroma** so the data plane can be “up” without a working LLM provider. The **llm** field may use a **cached** probe to avoid hammering the provider on every request.
- **`aria ingest`** — preflight requires **all three** (Neo4j, Chroma, LLM) via **`full_ingest_dependencies_satisfied`**; stricter than **`GET /ready`** or **`aria status`** exit rules.

This split avoids confusing “HTTP green” with “safe to run a full LLM ingest.”

### Telemetry storage and retention

Request/agent/LLM telemetry can persist to **SQLite** (**`aria/observability/telemetry_store.py`**) with optional **retention pruning** in app lifespan. **Multi-replica** deployments need a strategy: per-process DBs fragment analytics; **Prometheus `/metrics`** or external stores are better for HA-style observability. See **`CHANGELOG.md`** and **`README.md`** for env vars.

### A2A overhead for local deployment

**Agent-to-Agent (A2A)** protocols treat agents as **HTTP peers** with **agent cards** and **task delegation** (**`A2AClient`**, **`A2AServer`**, **`agent_card.py`**). On a **single machine**, the same work could be **in-process function calls** through **`ToolPorts`** or direct Python imports.

**Overhead sources**

- **Serialization** of tasks and responses
- **TCP stack** and **connection** management even for `localhost`
- **Operational duplication**: separate processes or containers per agent for fidelity to the protocol

**Why keep A2A in a portfolio project**

- **Demonstrates interoperability** assumptions (independent deployable agents, distinct **endpoints** in **`AGENT_CARDS`**)
- **Mirrors** multi-team ownership in real organizations

**Mitigation** for local demos: colocate agents, reuse **FastAPI** app mounting, or provide a **“monolith mode”** that bypasses HTTP where the README documents it. The tradeoff is **less realistic** networking behavior versus **simpler** debugging.

### MCP versioning challenges

**MCP** (Model Context Protocol) evolves **tool schemas**, **transport** details, and **capability negotiation**. ARIA’s **`MCPServer`** and metrics (**`MCP_TOOL_CALL_COUNTER`**, **`MCP_TOOL_CALL_DURATION`**) assume a **stable tool surface**.

**Risks**

- **Client/server skew**: agent code built for one schema version calling an older server
- **Silent behavior change** when upgrading SDKs without **contract tests**
- **Documentation drift** between **README** examples and actual **tool JSON**

**Mitigation patterns**

- Version **tool definitions** explicitly in **agent cards** or **OpenAPI**-like artifacts
- Add **contract tests** that invoke each tool with **golden arguments**
- Pin **dependency versions** in **`pyproject.toml`** and document upgrade playbooks

### Local-first limitations: Ollama versus cloud APIs

Running **Ollama** (or similar) keeps **data** on-prem and **cost** predictable but often sacrifices **frontier reasoning**, **multilingual quality**, and **tool-calling reliability** compared to **hosted APIs**. Smaller models may **hallucinate** structured JSON for **entity extraction** or **omit** regulatory nuance.

**Implications for ARIA**

- **Extraction** and **report generation** nodes depend on **model quality**; errors surface as **`ARIAState.error`**
- **Evaluation** becomes noisier; see **`tests/eval/`** and doc **`10_evaluation_agentic_systems.md`**

**Mitigation**

- Use **larger** local models where hardware allows
- **Validate** all critical structures with **Pydantic** and **repair** prompts
- Optionally **route** only specific tasks to cloud models behind a **policy flag** (not required for the portfolio default)

### Schema evolution when Pydantic models change

**`aria/contracts/`** defines **ExtractedEntities**, **ImpactReport**, **GraphWriteStatus**, and related types. **Nodes** validate tool outputs with **`model_validate`**. Any **field rename**, **type change**, or **required field** addition propagates to:

- **MCP tool** handlers and **Neo4j** write payloads
- **LangGraph** **`ARIAStateDict`** shape (nested dicts)
- **Tests** and **seed data**
- **API** response models if exposed

**Without migration discipline**, production graphs contain **legacy property keys** while code expects **new** ones—leading to **empty query results** or **validation exceptions**.

**Concrete friction points in ARIA**

- **`scratch/nodes.py`** maps **Cypher rows** into **`AffectedAsset`** and **`ImpactReport`**; renamed columns in **`impact_by_regulation`** break silently or raise at runtime.
- **`ARIAState`** and **`ARIAStateDict`** must stay aligned when adding fields (e.g. a new **audit** timestamp for **WORM** storage).
- **OpenAPI** or **agent card** JSON shown to external integrators must be **regenerated** when contracts change.

**Mitigation**

- Prefer **additive** schema changes with **defaults**
- Use **explicit migrations** in Neo4j (batch `MATCH`/`SET`)
- Maintain **versioned** golden fixtures for **eval**
- Add a **single** “contract changelog” section in release notes when models move

### Evaluation reliability with non-deterministic LLMs

Even with **fixed** prompts, **temperature**, and **seeds** (where supported), outputs vary. **Lexical** retrieval scoring (**`score_retrieval`**) and **trace** checks (**`evaluate_trace`**) reduce but do not eliminate **flakiness** when end-to-end runs include **live** models.

**Strategies** (summarized; see eval doc for detail)

- Test **structure** (traces, schemas) before **natural language**
- **Record** tool responses for CI
- **Aggregate** over multiple samples for **quality metrics**

## Tradeoffs (summary matrix)

| Area | Gain | Cost |
|------|------|------|
| GraphRAG / Neo4j | Explainable multi-hop answers | Query latency, modeling effort |
| Vector / Chroma | Fast similarity retrieval | Weaker relational guarantees |
| A2A | Decoupled agents, realistic protocol | Local HTTP overhead |
| MCP | Standard tool surface | Version coupling |
| Local LLM | Privacy, cost cap | Model capability ceiling |
| Strict Pydantic | Runtime safety | Migration friction on change |
| Cached LLM readiness | Fewer probe calls on `/ready` | Stale **`llm`** field until TTL expires |
| SQLite telemetry | Simple local analytics | Per-replica fragmentation, file locking caveats |

## Portfolio versus production-grade implementation

**What this project demonstrates well**

- **End-to-end shape** of a regulatory impact agent: ingest, graph, analyze, report
- **Dual orchestration** (scratch + LangGraph reference) for **learning** and **comparison**
- **Protocol stubs** (MCP, A2A) showing **where** enterprise integration hooks attach
- **Eval scaffolding** for **retrieval** and **traces**, with clear paths to deepen

**What a production rollout would add**

- **Authentication**, **authorization**, **audit logs**, and **data retention** policies
- **SLAs**, **horizontal scaling**, **queueing**, and **idempotent** ingestion pipelines
- **Robust eval** (LLM judges, human loops, continuous monitoring)
- **Formal verification** of critical rules where LLMs are **not** the source of truth
- **Disaster recovery** for **Neo4j** and **Chroma** backups

The codebase is intentionally **readable** and **modular** rather than **exhaustive** in security and SRE depth.

## Further reading

- Orchestration and traces: `aria/orchestration/scratch/graph.py`, [09_langgraph_reference.md](09_langgraph_reference.md)
- Evaluation: `tests/eval/`, [10_evaluation_agentic_systems.md](10_evaluation_agentic_systems.md)
- Operational changes: `CHANGELOG.md` (repo root)
- A2A: `aria/protocols/a2a/client.py`, `aria/protocols/a2a/server.py`, `api/routers/agents.py`
- MCP: `aria/protocols/mcp/server.py`, `aria/observability/metrics.py`
- Graph and API: `aria/graph/client.py`, `api/routers/query.py`, `api/routers/impact.py`
- Neo4j performance: official **Cypher tuning** and **indexing** guides
- MCP specification and release notes: vendor documentation for the protocol version you pin
