# LangGraph API Walkthrough and ARIA Scratch Parity

## Concept definition

**LangGraph** is a library for building stateful, multi-step agent workflows as graphs. Its central abstraction is the **`StateGraph`**: a directed graph whose vertices are **nodes** (typically async callables that read state and return updates) and whose transitions are **edges**. **Conditional edges** route to different successor nodes based on a **routing function** that inspects the current state and returns a label; a **path map** binds that label to the next node or to termination. After wiring nodes and edges, you **`compile()`** the graph to produce an executable runnable that LangGraph can invoke, optionally **checkpoint**, **stream**, or pause for human approval.

Core API pieces in typical usage:

| LangGraph concept | Role |
|-------------------|------|
| `StateGraph(StateSchema)` | Declares the graph and the shape of accumulated state (often a `TypedDict` or a schema with reducers for merging updates). |
| `add_node(name, fn)` | Registers a step; the node receives state and returns a partial update or new state snapshot depending on configuration. |
| `add_conditional_edges(source, router, path_map)` | After `source`, invoke `router(state)`; the string return value selects the next node via `path_map` (values may be node names or `END`). |
| `add_edge(source, target)` | Unconditional transition (used when the next step is always the same). |
| `set_entry_point(name)` | Declares the first node to run. |
| `graph.compile()` | Produces the compiled application ready for `ainvoke`, streaming callbacks, or checkpoint-backed replay. |

**State channels** in LangGraph are often typed with `TypedDict` so static checkers and the framework agree on keys. **Nodes** should be pure with respect to orchestration concerns as far as possible: business logic and side effects live inside them, while the graph encodes **control flow** only.

## Why it matters

Graph-based orchestration replaces implicit control flow in large agent codebases. Benefits include:

- **Explicit structure**: Reviewers can see all legal transitions in one place.
- **Testability**: Routers and nodes can be unit-tested in isolation.
- **Operational hooks**: Tracing, retries, and step limits align naturally with graph steps.

LangGraph adds **ecosystem depth**: persistence, subgraphs, and integration patterns familiar to LangChain users. For **ARIA** (Automated Regulatory Impact Agent), maintaining a **scratch** graph alongside a **LangGraph reference** shows that the hard problems—**state design**, **regulatory routing**, **tool contracts** (MCP-shaped `ToolPorts`)—are independent of the framework; the framework mainly standardizes **how** steps are scheduled and **how** state is merged and stored.

## How it is implemented in this repo

ARIA ships two orchestration layers:

1. **Scratch engine** — `aria/orchestration/scratch/`
2. **LangGraph reference** — `aria/orchestration/langgraph_reference/` (optional: `pip install "aria[langgraph]"`)

The README points readers to this document for the comparison artifact.

### StateGraph versus `OrchestrationGraph`

The scratch **`OrchestrationGraph`** in `scratch/graph.py` implements the same **operational** pattern as `StateGraph`:

- Nodes are registered in a dictionary and invoked by name.
- After each node, an **edge function** decides the next node.
- Execution stops on `"end"`, on error (with guardrails), or after **`MAX_STEPS`** to prevent infinite loops.
- **`ExecutionResult`** captures **`StepTrace`** entries (node name, duration, chosen next node, errors) and exposes **`to_trace_dict()`** for observability.

LangGraph’s **`build_langgraph()`** in `langgraph_reference/graph.py` constructs a **`StateGraph(ARIAStateDict)`** with the same **named nodes** and **conditional edges** as scratch: `supervisor` → (`ingestion` | `free_query` | `impact_analyzer` | `END`), ingestion → `entity_extractor` → `graph_builder` → …, mirroring **`EDGE_MAP`** in `scratch/edges.py`.

### Side-by-side: state as TypedDict adapter

Canonical state is the Pydantic model **`ARIAState`** (`scratch/state.py`): fields for `regulation_id`, `raw_document`, `extracted_entities`, `impact_report`, `final_report`, `error`, `history`, and helpers such as **`has_error`**, **`is_ingestion_request`**, **`is_impact_query`**, **`is_free_query`**.

LangGraph expects dict-shaped state for the graph type parameter. **`ARIAStateDict`** (`langgraph_reference/state.py`) is a **`TypedDict`** (with `total=False` where appropriate) mirroring those fields, including nested structures as `dict[str, Any]` where Pydantic would use nested models. Conversion helpers:

- **`pydantic_to_dict(state: ARIAState) -> ARIAStateDict`**
- **`dict_to_pydantic(state_dict) -> ARIAState`**

In practice, LangGraph **routers and nodes** call **`ARIAState.model_validate(state)`** so they reuse the **exact same boolean logic** as scratch edge functions that take **`ARIAState`** directly.

| Concern | LangGraph reference | Scratch |
|--------|---------------------|---------|
| Primary state type | Dict at API boundary | `ARIAState` |
| Validation | `_wrap_state` / `model_validate` | Native Pydantic in nodes |
| History / current node | Serialized in dict | Mutated on `record_step` |

### Side-by-side: nodes

Scratch **node functions** (`scratch/nodes.py`) have the signature **`async (ARIAState, ToolPorts) -> ARIAState`**. They perform substantive work: **`tools.extract_entities`**, **`tools.write_to_graph`**, **`tools.query_graph`**, **`tools.generate_text`**, with Pydantic validation of tool payloads into **`ExtractedEntities`**, **`GraphWriteStatus`**, **`ImpactReport`**, and so on.

LangGraph **node functions** (`langgraph_reference/nodes.py`) accept **`dict[str, Any]`**, convert to **`ARIAState`**, perform **step recording** and **guard checks** analogous to the scratch nodes (e.g., empty document → error), then **`model_dump()`** back to a dict. The module docstring states that this layer is a **thin, framework-facing** surface; full **tool orchestration** is illustrated in scratch, while a deeper LangGraph integration could wire **tool nodes** or **bind_tools** patterns.

**Mapping summary**: Same **node names** and **state transitions**; scratch carries **production-shaped I/O** via **`ToolPorts`**; LangGraph reference emphasizes **graph wiring** and **dict state** conventions.

### Side-by-side: conditional edges and routing decisions

Scratch defines **`EdgeFunction = Callable[[ARIAState], str]`** and **`EDGE_MAP`** in `scratch/edges.py`:

- **`route_after_supervisor`**: errors → `end`; ingestion → `ingestion`; free query → `free_query`; impact query (`regulation_id` without document) → `impact_analyzer`; else → `end`.
- **`route_after_ingestion`**: errors → `end`; else → **`entity_extractor`**.
- **`route_after_entity_extractor`**: errors → `end`; if **`extracted_entities`** → `graph_builder`; else → `end`.
- **`route_after_free_query`**: → `end`.
- **`route_after_graph_builder`**: errors → `end`; if **`regulation_id`** → `impact_analyzer`; else → `end`.
- **`route_after_impact_analyzer`**: errors → `end`; if **`impact_report`** → `report_generator`; else → `end`.
- **`route_after_report_generator`**: always **`end`**.

LangGraph registers the **same logical predicates** via **`add_conditional_edges`**, importing **`route_after_*`** from `langgraph_reference/nodes.py` (wrapping dict → **`ARIAState`** internally). The **path map** translates string outputs to the next node or **`END`**, e.g. `"end": END` for termination.

This is the clearest **1:1 mapping** in the repo: **one routing decision**, two syntaxes (table-driven **`EDGE_MAP`** versus **`add_conditional_edges`**).

### Compilation and execution entry points

- **LangGraph**: **`compiled = graph.compile()`** then invoke with the framework’s async API and initial state dict.
- **Scratch**: **`build_default_graph()`** returns **`OrchestrationGraph`**; call **`await graph.execute(initial_state, tools)`** with a concrete **`ToolPorts`** implementation.

Scratch’s **`execute`** method is the **hand-rolled runtime**: try/except per node, edge lookup, **`StepTrace`**, optional final **`end` node** invocation. LangGraph’s runtime handles scheduling, merge semantics, and optional checkpointing **inside** the compiled object.

### Worked mental model: two paths

**Ingestion path (high level)**  
`supervisor` (document present) → `ingestion` → `entity_extractor` → if entities extracted → `graph_builder` → if `regulation_id` set → `impact_analyzer` → if report → `report_generator` → `end`.  
Both implementations follow this **skeleton**; scratch fills in **tool calls** at each step.

**Impact path**  
`supervisor` → `impact_analyzer` when **`regulation_id`** is set and there is **no** `raw_document` (includes gap-style payloads with both `regulation_id` and `query`), then **`report_generator`** when an impact report exists.

**Free query path**  
`supervisor` → `free_query` → `end` when **`query`** is set and **`regulation_id`** and **`raw_document`** are absent.

Tracing **`node_path`** from **`ExecutionResult`** in scratch parallels inspecting LangGraph run metadata or custom callbacks if you add them.

### State merge semantics (conceptual)

LangGraph can apply **reducer** functions per channel so that multiple nodes contribute to the same key (for example appending messages). ARIA’s scratch graph uses a **single mutable `ARIAState`** object passed through the loop: nodes mutate **in place** (e.g. **`record_step`** appends to **`history`**). That is simpler to read for a portfolio-sized graph but differs from reducer-based merging. If you evolve ARIA toward LangGraph-native state, consider whether **`history`** should be an **append-only channel** with an explicit reducer to match parallel or fan-out patterns.

### Diagram: equivalent topology (simplified)

```text
                         ┌─────────────┐
                         │ supervisor  │
                         └──────┬──────┘
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
 ┌────────────┐      ┌─────────────────┐      ┌────────────┐
 │ ingestion  │      │ impact_analyzer │      │ free_query │
 └─────┬──────┘      └────────┬────────┘      └─────┬──────┘
       ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐              END
│entity_extract│      │report_generat│
└──────┬───────┘      └──────┬───────┘
       ▼                     ▼
┌──────────────┐            END
│graph_builder │
└──────┬───────┘
       ▼
      END   (or → impact_analyzer → … when regulation_id present)
```

Both **`OrchestrationGraph`** and **`StateGraph`** realize the same branching; the diagram omits every **`end`** self-loop for space. Scratch additionally invokes an explicit **`end`** node after the loop when registered.

## Tradeoffs

**When LangGraph adds value**

- **Checkpointing and replay** for long regulatory workflows or human review gates.
- **Standard patterns** for streaming tokens or partial state to UIs.
- **Reduced custom code** as the graph grows (parallel branches, subgraphs, dynamic interrupts).

**When hand-rolling is more instructive or preferable**

- **Pedagogy**: Reading **`OrchestrationGraph.execute`** teaches execution semantics without framework indirection.
- **Dependency minimalism**: Core ARIA demos do not require **`langgraph`**.
- **Tight coupling to `ToolPorts`**: A single **`execute(state, tools)`** signature keeps MCP-shaped injection obvious for portfolio reviewers.

**Honest parity note**

The LangGraph reference optimizes for **graph isomorphism** and **shared routing logic** on **`ARIAState`**. It does not automatically delegate every line of **`scratch/nodes.py`** into LangGraph node bodies; extending the reference to call scratch node functions with an adapter for **`ToolPorts`** would tighten behavioral parity at the cost of more boilerplate.

## Further reading

- LangGraph documentation: [https://langchain-ai.github.io/langgraph/](https://langchain-ai.github.io/langgraph/) — `StateGraph`, conditional edges, compilation, persistence, subgraphs.
- ARIA scratch: `aria/orchestration/scratch/graph.py`, `edges.py`, `nodes.py`, `state.py`.
- ARIA LangGraph reference: `aria/orchestration/langgraph_reference/graph.py`, `nodes.py`, `state.py`.
- Project layout and optional dependency: `README.md`, `pyproject.toml` (`aria[langgraph]`).
