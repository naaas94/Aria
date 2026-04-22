# Agent orchestration patterns in ARIA

## Concept definition

**Agent orchestration** is the discipline of composing multiple reasoning steps, tools, and sub-agents into a coherent workflow that terminates with a useful artifact (answer, report, graph update, or error). In ARIA, orchestration interacts with **MCP** (tool calls for graph and vector access) and **A2A** (delegation to remote agent services) as orthogonal layers: the graph decides *when* to move between specialists; protocols decide *how* those specialists touch data or peer agents.

Common patterns differ in how much structure is fixed up front versus discovered at runtime:

- **ReAct** (reasoning + acting): interleaves natural-language “thought” steps with tool calls in a loop until the model emits a final answer. The control flow is often implicit in the transcript rather than a compiled graph.

- **Plan–Execute**: first produce an explicit plan (steps, dependencies, or subgoals), then execute steps sequentially or in parallel. Planning can be a separate LLM pass or a deterministic template.

- **Reflection**: after an initial output, a critic or the same model revises the result using feedback (self-critique, rubric, or test harness). May loop until quality thresholds are met.

- **Supervisor** (hierarchical routing): a dedicated controller classifies intent or state and **routes** to specialized workers (sub-agents or nodes). The supervisor typically does not perform all domain work itself; it decides **which** specialist runs next. Variants include finite-state routers, policy trees, and LLM-based intent classifiers.

These patterns are not mutually exclusive: a supervisor may invoke a ReAct-style sub-agent; a plan–execute phase may precede a reflection phase.

## Why it matters

**ARIA (Automated Regulatory Impact Agent)** combines **Neo4j**, **ChromaDB**, **GraphRAG**, **MCP**, **A2A**, and **multi-agent** pipelines. Orchestration matters because:

- Regulatory workflows have **distinct modes**: ingest new text, query impact by regulation, generate reports, or answer exploratory questions. A single monolithic prompt is hard to test, secure, and observe.

- **Graph and retrieval** steps have different failure modes and latencies than **LLM** steps; explicit routing enables targeted retries, caching, and metrics.

- **Compliance-oriented** systems benefit from **auditable paths**: which node ran, in what order, with what high-level intent—properties that supervisor-plus-graph designs expose naturally.

Choosing the wrong pattern increases cost (too many LLM calls), fragility (unconstrained ReAct), or rigidity (over-planned pipelines that cannot adapt).

## When each pattern is appropriate

### ReAct

**Use when** the task space is **open-ended**, tools are **safe and bounded**, and you want the model to **explore** a solution path without maintaining a custom graph. Good for interactive assistants with a small tool set and strong sandboxing.

**Avoid when** you must enforce **strict ordering** (for example, “always persist entities before impact analysis”), guarantee **termination** bounds, or meet **audit** requirements that need a fixed topology.

### Plan–Execute

**Use when** tasks decompose cleanly into **checklisted steps** with predictable dependencies (research → outline → draft). Useful for batch jobs and repeatable compliance checklists.

**Avoid when** the environment is **highly dynamic** and plans stale quickly, or when planning overhead dominates simple lookups.

### Reflection

**Use when** output quality is subjective or **high-stakes** (executive summaries, risk statements) and you can define **criteria** or **tests** for revision.

**Avoid when** latency or token budgets are tight, or when “reflection” becomes an unbounded loop without clear stop conditions.

### Supervisor

**Use when** you have **distinct specialists** (ingestion, graph write, impact analysis, reporting) and a **small set of intents** or state predicates that determine routing. Supervisors excel when the workflow is a **state machine** with occasional LLM classification at the entry.

**Avoid when** every decision should be **fully emergent** from a single agent (supervisor overhead adds little), or when routing logic becomes so complex that a **declarative workflow engine** or **full planner** is simpler to maintain.

## How it is implemented in this repository

ARIA adopts a **Supervisor pattern** backed by a **stateful graph execution engine** without requiring LangGraph for the primary path: `aria/orchestration/scratch/`.

### Supervisor intent classification

`aria/agents/supervisor.py` defines **`SupervisorAgent`**, a thin **`BaseAgent`** implementation whose `process` method returns a **routing decision dict**:

- If `raw_document` is present → intent `ingestion`
- Else if `regulation_id` and `query` → `gap_analysis`
- Else if `regulation_id` → `impact_query`
- Else if `query` alone → `free_query`
- Else → `unknown`

The orchestration graph does not call this class for every hop; instead, **`ARIAState`** carries inputs and **`supervisor_node`** in `aria/orchestration/scratch/nodes.py` performs **structural routing** using the same predicates (`is_ingestion_request`, `is_impact_query`, `is_free_query`). The standalone `SupervisorAgent` documents the **intent vocabulary** for API layers and tests that classify user payloads before execution.

Together, these embody **supervisor-style routing**: one logical “front door” concept classifies or inspects state, then **edges** send execution to specialized nodes.

### Stateful graph engine (scratch)

Under `aria/orchestration/scratch/`:

- **`state.py`**: `ARIAState` — typed shared state (regulation ID, document text, extracted entities, graph write status, impact report, final report, error, `current_node`, `history`).

- **`nodes.py`**: async node functions (`supervisor`, `ingestion`, `entity_extractor`, `free_query`, `graph_builder`, `impact_analyzer`, `report_generator`, `end`) each taking `(ARIAState, ToolPorts)` and returning updated state. Nodes call tools via **`ToolPorts`** (MCP-shaped), keeping side effects behind a protocol.

- **`edges.py`**: pure functions `route_after_*` implementing the **routing table** after each node.

- **`paths.py`**: canonical node sequences (**`CANONICAL_SCRATCH_*`**) kept in sync with **`build_default_graph`** and **`EDGE_MAP`** for evals and docs.

- **`graph.py`**: **`OrchestrationGraph`** runs a **loop**: execute current node, compute next via edge function, advance until `end`, error, or `MAX_STEPS`.

`build_default_graph()` registers all nodes; routing is entirely via **`EDGE_MAP`**.

**Example paths (high level)**

- **Ingestion**: `supervisor` → `ingestion` (validates document) → `entity_extractor` (calls `tools.extract_entities`) → `graph_builder` → if `regulation_id` → `impact_analyzer` → `report_generator` → `end`; else `end` after graph builder when no regulation id.
- **Impact-only** (regulation id, no document): `supervisor` → `impact_analyzer` → `report_generator` → `end`.
- **Free query** (`query` only, no `regulation_id`, no document): `supervisor` → `free_query` (vector search) → `end`.
- **Error anywhere**: edge functions route to `end`; `OrchestrationGraph.execute` also forces termination when `state.has_error` and the computed next node is not already `end`.

This is **explicit stateful orchestration**: unlike ReAct, the **graph topology** is fixed in code; unlike unconstrained reflection, there is no default self-critique loop (reflection could be added as a node if desired).

### Observability of the supervisor pattern

`ExecutionResult` in `graph.py` aggregates `StepTrace` entries (node name, duration, chosen next node, error snapshot). That structure supports portfolio demonstrations of **which specialist ran** after the supervisor’s implicit routing decision—useful when comparing GraphRAG retrieval timings to LLM report generation.

### LangGraph reference

The repository also contains `aria/orchestration/langgraph_reference/` with a parallel graph built on **LangGraph** conventions (`state`, `nodes`, `graph`). Comments in `state.py` note that **the same `ARIAState` schema** is shared so the scratch engine and LangGraph reference stay aligned. The portfolio emphasizes the **scratch** implementation to show orchestration **without framework lock-in** for the core loop.

### Comparison to other patterns in ARIA

- **ReAct** is not the primary outer loop; individual agents may still use LLM tool-calling internally (`EntityExtractorAgent`, and so on).

- **Plan–Execute** is not the default; steps are **encoded as nodes** rather than a free-form plan document.

- **Reflection** is not wired into the default graph; report quality could be extended with a review node.

The **supervisor + graph** choice trades flexibility for **predictability**, **testability**, and **clear metrics per node**—aligned with regulatory impact reporting.

## Tradeoffs

**Supervisor + stateful graph (chosen)**

- Pros: bounded execution (`MAX_STEPS`), explicit traces (`StepTrace`, `history`), easy to explain in documentation and interviews.
- Cons: new workflows require code changes to nodes or edges; less “emergent” than pure ReAct.

**ReAct-only (not chosen as outer loop)**

- Pros: rapid prototyping for exploratory queries.
- Cons: harder to enforce ordering and allow-listed graph access uniformly.

**Plan–Execute (not chosen as default)**

- Pros: human-readable plans for stakeholders.
- Cons: planning LLM calls add latency; plans may not match graph schema constraints without validation.

**Reflection (optional future)**

- Pros: higher-quality narrative outputs.
- Cons: variable cost; needs stop conditions and evaluation harnesses.

## Further reading

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) — foundational ReAct paper.
- LangGraph documentation — for comparing framework-backed graphs to scratch implementations (search for current LangChain/LangGraph docs).
- Internal: `aria/agents/supervisor.py` — intent classification for API-aligned payloads.
- Internal: `aria/orchestration/scratch/state.py` — `ARIAState` schema.
- Internal: `aria/orchestration/scratch/nodes.py` — node bodies and `ToolPorts`.
- Internal: `aria/orchestration/scratch/edges.py` — `EDGE_MAP` routing table.
- Internal: `aria/orchestration/scratch/paths.py` — canonical paths for traces and evals.
- Internal: `aria/orchestration/scratch/graph.py` — `OrchestrationGraph.execute` and `build_default_graph`.
- Internal: `aria/orchestration/langgraph_reference/` — reference graph sharing `ARIAState`.
- Internal: `tests/unit/test_orchestration.py` — unit coverage for orchestration behavior where present.
- Internal: `aria/protocols/mcp/server.py` — tool layer consumed indirectly via `ToolPorts` adapters during graph execution.

For a visual summary: the supervisor pattern here is a **router node plus explicit edges**, not an LLM choosing arbitrary next steps on every hop—classification can still be LLM-driven upstream before state is injected into `ARIAState`.
