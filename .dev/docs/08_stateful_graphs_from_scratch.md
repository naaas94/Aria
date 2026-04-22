# Stateful graph orchestration from scratch

## Concept definition

A **stateful graph orchestration engine** executes a workflow as a directed structure where:

1. **State** is a shared, typed data object mutated or replaced as execution proceeds.
2. **Nodes** are units of work (callables) that read state, perform effects through injected services, and return updated state.
3. **Edges** are routing functions that, given the state after a node, choose the **name** of the next node (conditional branching).
4. The **execution engine** loops: run the current node, evaluate the outgoing edge, advance, and stop on a terminal marker, error, or safety cap.

This model appears in frameworks (for example, LangGraph) but can be implemented in plain Python with async functions, dictionaries mapping names to callables, and a small amount of bookkeeping. **Building from scratch** clarifies semantics—no hidden scheduler—and keeps portfolio code easy to read without framework version coupling for the core loop.

## Why it matters

For **ARIA (Automated Regulatory Impact Agent)**, workflows cross **ingestion**, **entity extraction**, **graph writes**, **multi-hop graph reads** (GraphRAG-oriented analysis), and **LLM report generation**. A scratch engine matters because:

- **Transparency**: interviewers and reviewers can read `execute()` and understand termination, error handling, and step limits.
- **Testability**: nodes and edges are pure enough to unit test with fake `ToolPorts`.
- **Alignment with Neo4j/Chroma/MCP**: side effects stay behind `ToolPorts`; the graph only sequences **when** those calls happen.
- **Pedagogical value**: the same `ARIAState` schema is shared with `aria/orchestration/langgraph_reference/`, showing equivalence between a hand-rolled loop and a framework-backed graph.

## How it is implemented in this repository

The scratch implementation lives in `aria/orchestration/scratch/` across four modules: `state.py`, `nodes.py`, `edges.py`, and `graph.py`.

### State objects (typed shared state)

`aria/orchestration/scratch/state.py` defines **`ARIAState`** as a Pydantic `BaseModel` with:

**Inputs and working fields**

- `regulation_id`, `raw_document`, `document_hash`, `query` — capture user or API-provided payloads.
- `extracted_entities` — `ExtractedEntities` contract after LLM extraction.
- `graph_write_status` — `GraphWriteStatus` after Neo4j merge operations.
- `impact_report` — `ImpactReport` after impact analysis.
- `final_report` — string output from report generation.

**Control and diagnostics**

- `error` — optional string; when set, routing and engine logic steer toward termination.
- `current_node` — last recorded node name (updated via `record_step`).
- `history` — append-only list of visited node names for auditing.

**Predicates** (properties)

- `has_error`
- `is_ingestion_request` — `raw_document` is set.
- `is_impact_query` — `regulation_id` without `raw_document`.
- `is_free_query` — `query` without `regulation_id` and without `raw_document`.

`record_step(node_name)` appends to `history` and sets `current_node`. The schema is documented as the **canonical contract** shared with the LangGraph reference implementation.

### Nodes (callable units)

`aria/orchestration/scratch/nodes.py` defines async functions with signature:

```text
async def node_name(state: ARIAState, tools: ToolPorts) -> ARIAState
```

**`ToolPorts`** is a `typing.Protocol` describing async methods: `extract_entities`, `write_to_graph`, `index_vectors`, `query_graph`, `vector_search`, `generate_text`. Orchestration depends on the protocol; concrete adapters (for example, `MCPToolPortsAdapter`) supply behavior.

**Registered node behaviors (summary)**

| Node | Responsibility |
|------|----------------|
| `supervisor_node` | Logs intent classification; relies on **edge** functions for actual branching; records step |
| `ingestion_node` | Calls `tools.extract_entities`, validates `ExtractedEntities` |
| `entity_extractor_node` | Standalone extraction step if separated from ingestion |
| `graph_builder_node` | Calls `tools.write_to_graph`, validates `GraphWriteStatus`, sets errors on failure |
| `impact_analyzer_node` | Calls `tools.query_graph("impact_by_regulation", …)`, builds `ImpactReport` |
| `report_generator_node` | Builds prompt from `impact_report`, calls `tools.generate_text` |
| `end_node` | Terminal bookkeeping and log of full `history` |

Each node sets `state.error` on validation or execution failure and returns state for the edge layer to interpret.

### Edges (conditional routing functions)

`aria/orchestration/scratch/edges.py` defines **`EdgeFunction`**: `Callable[[ARIAState], str]`.

**Routing table (logical)**

- **`route_after_supervisor`**: on error → `end`; ingestion → `ingestion`; impact or free query → `impact_analyzer`; else → `end`.
- **`route_after_ingestion`**: on error → `end`; if `extracted_entities` → `graph_builder`; else → `end`.
- **`route_after_graph_builder`**: on error → `end`; if `regulation_id` → `impact_analyzer`; else → `end`.
- **`route_after_impact_analyzer`**: on error → `end`; if `impact_report` → `report_generator`; else → `end`.
- **`route_after_report_generator`**: always `end`.

**`EDGE_MAP`**: `dict[str, EdgeFunction]` mapping **source node name** to the router for the edge leaving that node:

```text
supervisor → route_after_supervisor
ingestion → route_after_ingestion
graph_builder → route_after_graph_builder
impact_analyzer → route_after_impact_analyzer
report_generator → route_after_report_generator
```

There is no edge map entry for `end`; termination is implicit once the engine reaches the `end` node name as the **next** target.

### Execution engine (loop until termination)

`aria/orchestration/scratch/graph.py` defines:

**`StepTrace`** — dataclass capturing `node_name`, `duration_ms`, `next_node`, and optional `error`.

**`ExecutionResult`** — holds `final_state`, list of `StepTrace`, and helpers: `success` (no error in final state), `total_duration_ms`, `node_path`, `to_trace_dict()` for JSON-style telemetry.

**`OrchestrationGraph`**

- Constructed with `entry_point` (default `"supervisor"`).
- `add_node(name, fn)` populates `_nodes`.
- `add_edge(from_node, edge_fn)` overrides or extends `_edges` (initialized from `EDGE_MAP` copy).
- **`execute(state, tools)`** implements the core loop:
  1. Start at `entry_point`.
  2. While `current != "end"` and `step_count < MAX_STEPS` (20):
     - If current node missing from `_nodes`, set error and break.
     - Time and `await` the node function.
     - Look up edge function for `current`; compute `next_node`.
     - Append `StepTrace`.
     - If `state.has_error` and `next_node != "end"`, force `next_node` to `"end"`.
     - Advance `current` and increment step count.
  3. If loop ends with `current == "end"` and `end` is registered, run `end_node` once and append a final trace.
  4. If step cap exceeded, set error on state.

**`build_default_graph()`** instantiates `OrchestrationGraph`, registers all node functions (`supervisor`, `ingestion`, `graph_builder`, `impact_analyzer`, `report_generator`, `end`), and returns a ready-to-run graph.

### Walkthrough: impact path

1. Initial `ARIAState` includes `regulation_id` and no `raw_document` → `is_impact_query` is true.
2. `supervisor_node` runs; `route_after_supervisor` returns `"impact_analyzer"`.
3. `impact_analyzer_node` queries the graph via `ToolPorts.query_graph`, fills `impact_report`.
4. `route_after_impact_analyzer` returns `"report_generator"` when report exists.
5. `report_generator_node` produces `final_report`.
6. `route_after_report_generator` returns `"end"`; engine runs `end_node` and stops.

Traces record each hop for dashboards or tests.

## Tradeoffs

**Scratch engine**

- Pros: minimal dependencies, explicit semantics, easy to extend with one new node and one edge function.
- Cons: no built-in parallel fan-out, checkpointing, or distributed execution; contributors must maintain discipline so `EDGE_MAP` and `add_node` stay consistent.

**Framework graph (reference only)**

- Pros: ecosystem features (streaming, checkpointing, visualization) when needed.
- Cons: version churn and conceptual overhead for a small fixed graph.

**Pydantic state**

- Pros: validation and schema reuse across modules.
- Cons: large states can make copying semantics subtle; nodes should avoid mutating shared sub-objects unsafely (prefer model updates consistent with project style).

## Further reading

- Internal: `aria/orchestration/scratch/state.py` — full `ARIAState` definition.
- Internal: `aria/orchestration/scratch/nodes.py` — `ToolPorts` and all node implementations.
- Internal: `aria/orchestration/scratch/edges.py` — `EDGE_MAP` and routers.
- Internal: `aria/orchestration/scratch/graph.py` — `OrchestrationGraph`, `ExecutionResult`, `build_default_graph`.
- Internal: `aria/orchestration/langgraph_reference/` — parallel implementation for comparison.
- [LangGraph concepts](https://langchain-ai.github.io/langgraph/) — optional reading for mapping scratch concepts to framework terminology (search current docs for “state graph” and “conditional edges”).
