# Agent-to-Agent (A2A) Protocol in ARIA

## Concept definition

**Agent-to-Agent (A2A)** protocols describe how autonomous software agents discover peers, advertise capabilities, delegate work, and return structured outcomes across process or network boundaries. Google’s **Agent2Agent (A2A) protocol** (publicly positioned in 2025 as an open approach to interoperable agents) emphasizes:

- **Agent Cards** as machine-readable capability descriptors (identity, skills, schemas, endpoints).
- A **registry** or discovery mechanism so orchestrators can find agents that satisfy a required capability.
- **Task delegation** via structured envelopes that carry task type, input payload, status, and output or error detail—rather than opaque RPC or ad hoc JSON blobs.
- A **client/server architecture**: a delegating agent (client) sends tasks to a remote agent (server) that exposes an HTTP (or similar) API; the server validates, executes, and responds with the same envelope type for correlation and auditing.

A2A sits at the **multi-agent coordination** layer: one agent’s output becomes another’s input, possibly across services owned by different teams or runtime environments.

## Why it matters

ARIA (**Automated Regulatory Impact Agent**) combines **Neo4j**, **ChromaDB**, **GraphRAG**, **multi-agent orchestration**, **MCP** for tool-shaped access, and **A2A** for agent-shaped delegation. A2A matters because:

- **Scaling and isolation**: impact analysis and report generation can run in dedicated services with their own rate limits, models, and secrets—without collapsing everything into one monolith.

- **Explicit contracts**: Agent Cards document what each agent accepts and produces, reducing implicit coupling between teams and between LLM prompts.

- **Operational clarity**: `TaskEnvelope` carries `task_id`, `status`, timestamps, and error fields—suitable for traces, retries, and human review in regulated workflows.

- **Ecosystem alignment**: as the industry moves toward standardized agent interoperability, ARIA’s A2A-shaped modules demonstrate how a portfolio system can participate in that model alongside MCP for tools.

## How it is implemented in this repository

Implementation lives under `aria/protocols/a2a/` with shared envelopes in `aria/contracts/agent_messages.py`.

### Agent Cards as capability descriptors

`aria/protocols/a2a/agent_card.py` defines **`AgentCard`** (Pydantic model) with:

- `agent_id`, `name`, `version`, `description`
- `capabilities`: list of capability tags (for example, `regulatory_impact_analysis`, `report_generation`)
- `input_schema` / `output_schema`: string names referencing expected Pydantic or logical schema identifiers
- `endpoint`: base URL for HTTP A2A (for example, `http://localhost:8001/a2a`)
- `protocol_version` (module constant `PROTOCOL_VERSION = "0.1"`)

`supports_capability(capability)` returns whether a tag is present. **`AGENT_CARDS`** is a static dictionary keyed by logical agent keys (`supervisor`, `ingestion_agent`, `entity_extractor`, `graph_builder`, `impact_analyzer`, `report_generator`) holding exemplar cards. Some cards include `endpoint` (impact analyzer, report generator); others are orchestration-local in this sample layout.

Agent Cards are the **discovery primitive**: consumers do not need to know internal class names if they can match on `capabilities` and read `endpoint`.

### Registry pattern

`aria/protocols/a2a/registry.py` implements **`AgentRegistry`**:

- In-memory map from `agent_id` to `AgentCard`
- **`register` / `deregister`** for lifecycle
- **`get`**, **`list_all`**
- **`find_by_capability`**: returns all cards that advertise a given capability tag
- **`find_by_name`**: resolve by human-readable `name`
- **`save` / `load`**: optional JSON persistence to `agent_registry.json` (default path) for file-backed discovery in development or small deployments

The registry is the **central index** that a supervisor or router can query before delegating (“which agent offers `report_generation` and has an endpoint?”).

### Task delegation via TaskEnvelope

`aria/contracts/agent_messages.py` defines **`TaskEnvelope`**:

- Identifiers and lifecycle: `task_id` (UUID default), `status` (`TaskStatus`: pending, in_progress, completed, failed, cancelled), `created_at`, `updated_at`
- Routing: `source_agent`, `target_agent`
- Work: `task_type` (canonical name such as `entity_extraction`), `input_payload`, `output_payload`
- Failure: `error_detail`
- Methods: `mark_in_progress()`, `mark_completed(output)`, `mark_failed(error)` — update status and timestamps consistently

The same envelope type is used for **A2A HTTP bodies** and for conceptual parity with broader inter-agent messaging (`AgentMessage` exists for typed message kinds but A2A paths in this repo center on `TaskEnvelope`).

### Client/server architecture

**Server — `aria/protocols/a2a/server.py`**

**`A2AServer`** wraps a FastAPI **`APIRouter`** with prefix `/a2a`:

- `GET /health` — returns `status` and `agent_id`
- `GET /card` — returns the mounted `AgentCard` as JSON (card discovery over HTTP)
- `POST /tasks` — accepts a `TaskEnvelope`, marks in_progress, invokes an injected async **`handler(envelope.input_payload)`**, then marks completed with output or failed with exception text; returns the updated envelope

The handler type is `Callable[[dict], Awaitable[dict]]`, keeping the HTTP layer thin and pushing domain logic to the agent’s `process` implementation.

**Client — `aria/protocols/a2a/client.py`**

**`A2AClient`** implements outbound delegation:

- **`delegate_task(target_card, task_type, input_payload, source_agent)`** — builds a `TaskEnvelope`, `POST`s JSON to `{endpoint}/tasks`, validates the JSON response back into `TaskEnvelope`, returns it. On HTTP or network errors, marks the envelope failed and returns it (no uncaught leak of partial state without record).

- **`check_health(target_card)`** — `GET {endpoint}/health` with short timeout

Default HTTP timeout is 120 seconds for long-running LLM or graph work.

Together, this is the **client/server** split: any agent that mounts `A2AServer` becomes an A2A peer; supervisors use `A2AClient` to call them using metadata from `AgentCard` and the registry.

### End-to-end delegation flow (conceptual)

1. A supervisor resolves a target agent: query `AgentRegistry.find_by_capability("report_generation")` or look up a known `AgentCard`.
2. Verify `target_card.endpoint` is non-empty; otherwise delegation cannot proceed (`ValueError` on the client).
3. Build `TaskEnvelope` with `source_agent`, `target_agent`, `task_type`, and `input_payload`.
4. `A2AClient` posts to `{endpoint}/tasks` with JSON serialization (`model_dump(mode="json")`).
5. The remote `A2AServer` marks the task in progress, runs the registered handler, attaches `output_payload` or `error_detail`, and returns the envelope.
6. The caller inspects `TaskEnvelope.status` and payloads for downstream orchestration or user response.

This sequence mirrors how larger multi-agent platforms correlate work across services while keeping a single envelope type for logging and replay.

### Security and deployment notes

Production use of A2A requires **TLS**, **authentication** (for example, mTLS or OAuth2 bearer tokens between agents), and **authorization** tied to capability claims—not shown in the minimal FastAPI sample. The portfolio implementation intentionally foregrounds **structure** (cards, registry, envelopes) over production hardening. Treat `endpoint` URLs and persisted `agent_registry.json` as sensitive configuration in real deployments.

## A2A compared to MCP

| Dimension | MCP (in ARIA) | A2A (in ARIA) |
|-----------|----------------|---------------|
| Primary abstraction | **Tools** — discrete operations with JSON args and results | **Agents** — bounded services with cards, endpoints, and task lifecycles |
| Discovery | `list_tools()` and JSON Schema per tool | Agent Cards + registry + optional `GET /card` |
| Granularity | Fine-grained reads (`graph_query`, `vector_search`, …) | Coarse-grained tasks (`task_type` + payload) |
| Typical transport | In-process in demo; MCP stdio/HTTP in full ecosystems | HTTP (`httpx`) to `/a2a/tasks` |
| Coupling | Callers depend on tool names/schemas | Callers depend on capability tags and envelope contract |

**MCP** is ideal when the model or a thin orchestrator needs **many small, repeatable operations** on data (especially with policy-bound graph access).

**A2A** is ideal when another **autonomous agent** (possibly remote, separately scaled) owns a multi-step pipeline or its own internal tools.

They are **complementary**: MCP can be the tool layer *inside* an A2A-served agent, while A2A routes work between agents.

## Tradeoffs

**Advantages**

- Clear separation between agents with explicit cards and HTTP boundaries.
- Envelopes support status tracking and failure propagation suitable for observability.
- Registry + capability search supports dynamic topologies in principle.

**Costs and limitations**

- Static `AGENT_CARDS` and file registry are simplified; production systems need secure registration, authentication, and schema versioning beyond string `input_schema` names.
- `endpoint` must be configured consistently across environments (localhost ports in examples are not production-ready).
- Duplication risk: without discipline, task payloads can drift from Pydantic contracts used elsewhere—contract tests help.

## Relation to the full A2A specification

The published **Agent2Agent** standard describes JSON-RPC over HTTP(S), streaming, Agent Cards, Tasks, Messages, and Artifacts in greater detail than this repository’s minimal FastAPI router. ARIA’s `TaskEnvelope` is a **deliberately reduced** parallel: it captures task identity, routing, status, and input/output dictionaries so portfolio code stays readable. Aligning `AgentCard` fields and HTTP routes with the official spec’s Agent Card and task lifecycle is a natural evolution path when integrating with third-party A2A runtimes.

## Further reading

- [Agent2Agent (A2A) Protocol](https://google.github.io/A2A/) — overview and documentation.
- [A2A specification](https://google.github.io/A2A/specification/) — normative protocol details (JSON-RPC, tasks, agent cards).
- [google-a2a/A2A on GitHub](https://github.com/google-a2a/A2A) — reference materials and community implementations.
- Internal: `aria/protocols/a2a/agent_card.py` — `AgentCard` and `AGENT_CARDS`.
- Internal: `aria/protocols/a2a/registry.py` — `AgentRegistry` persistence and lookup.
- Internal: `aria/protocols/a2a/client.py` and `server.py` — delegation and inbound task handling.
- Internal: `aria/contracts/agent_messages.py` — `TaskEnvelope` and `TaskStatus`.
