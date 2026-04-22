# Model Context Protocol (MCP) in ARIA

## Concept definition

The **Model Context Protocol (MCP)** is an open standard for connecting large language model (LLM) applications to external data sources and tools through a well-defined client–server contract. The host (for example, an IDE or an agent runtime) runs an MCP **client**; one or more MCP **servers** expose **tools**, **resources**, and **prompts** that the model can discover and invoke without hard-coding every integration inside the application.

Core protocol concerns include:

- **Tool discovery**: The client can list available tools with machine-readable metadata (name, human-readable description, and JSON Schema for arguments). Discovery is the prerequisite for safe, dynamic tool use: the model or orchestrator learns what operations exist before invoking them.

- **Capability negotiation**: Clients and servers agree on what is exposed. The server’s advertised tool list is the negotiated surface area. Servers do not automatically grant unrestricted access to the host filesystem, network, or arbitrary code execution. In practice, negotiation also includes transport selection (for example, stdio versus HTTP) and optional authentication, depending on deployment.

- **Structured request/response format**: Tool invocations are framed as named operations with JSON-serializable arguments. Results are likewise structured (JSON or text with known semantics), which enables validation, logging, retries, and policy enforcement at the boundary rather than inside unstructured natural language.

MCP is transport-agnostic in principle (stdio, HTTP, WebSocket, and others). The important invariant is a consistent contract for listing and calling tools rather than ad hoc function wiring inside prompts or scattered `import` chains in agent code.

## Why it matters

For a regulatory intelligence system such as **ARIA (Automated Regulatory Impact Agent)**, data lives in multiple stores: a **Neo4j** knowledge graph for obligations and relationships, **ChromaDB** (or similar) for dense retrieval over document chunks, and **GraphRAG-style** pipelines that fuse graph traversal with vector search. MCP matters in this context because it:

- **Decouples** the LLM-facing surface from concrete database drivers and retrieval implementations. Agents depend on tool names and schemas, not on driver-specific APIs.

- Improves **discoverability**: new tools register once with metadata and schemas; orchestration code and prompts do not need a static list of every low-level function.

- Enables **security and governance**: exposing only **named, parameterized** graph operations instead of accepting raw query strings from callers reduces injection risk, narrows blast radius, and supports audit trails (“which named query ran, with which parameters”).

- Aligns with **multi-agent** and **orchestration** patterns where different components share the same tool contract. In ARIA, the scratch graph’s `ToolPorts` protocol can be backed by an MCP adapter so that the same logical operations are used whether the runtime is in-process or remote.

### MCP versus direct function calls

**Direct function calls** tie callers to concrete modules, signatures, and often deployment topology. Refactoring a database layer ripples through every caller. Granting an LLM “use Python” is difficult to sandbox.

**MCP-style boundaries** introduce a stable, documented interface: discovery lists what exists; invocation passes validated JSON; results return through a small envelope type. Benefits include:

- **Decoupling**: swap Neo4j client, vector backend, or transport without changing every node’s imports.

- **Discoverability**: tools self-describe for humans and for automated tooling.

- **Security via allow-listed operations**: ARIA’s `graph_query` tool never executes user-supplied Cypher; it resolves `query_name` against a registry and runs parameterized templates only.

The cost is indirection and the need to maintain schemas and handlers in one place.

## How it is implemented in this repository

ARIA implements an MCP-shaped tool layer under `aria/protocols/mcp/`.

### Tool definitions and JSON schemas

`aria/protocols/mcp/tools.py` defines:

- **Pydantic input models** for each tool (`CypherQueryInput`, `VectorSearchInput`, `HybridRetrievalInput`, `RegulationFetchInput`), which double as runtime validation and as **JSON Schema** via `model_json_schema()` for discovery.

- **`ToolDefinition`**: metadata records with `name`, `description`, and `input_schema` (the JSON Schema dict).

- **`ToolResult`**: a standard result envelope with `tool_name`, `success`, optional `data`, and optional `error` string—uniform success and failure reporting for all tools.

`TOOL_DEFINITIONS` registers four tools:

| Tool name | Role |
|-----------|------|
| `graph_query` | Execute a **named** parameterized Cypher read via the allow-listed query library |
| `vector_search` | Semantic search over regulatory document chunks in the vector store |
| `hybrid_retrieve` | Combined graph traversal and vector search with fusion (GraphRAG-oriented) |
| `fetch_regulation` | Retrieve regulation metadata and article list by regulation ID |

The `CypherQueryInput` model documents available query names by embedding `sorted(QUERIES.keys())` in the field description, reinforcing that only registered names are valid.

### Server: discovery and invocation

`aria/protocols/mcp/server.py` exposes **`MCPServer`**:

- **`list_tools()`** implements tool discovery: it returns `list(TOOL_DEFINITIONS)`.

- **`call_tool(tool_name, arguments)`** implements invocation: it looks up a handler in `_handlers`, validates `arguments` with the appropriate Pydantic model, executes the async handler, measures elapsed time, and returns a `ToolResult`. Unknown tools yield `success=False` with an error listing available tool names.

Handler behavior:

- **`graph_query`**: Validates input, calls `execute_named_query(query_name, parameters)` from `aria/graph/queries.py`, then `Neo4jClient.execute_read` with the resolved Cypher and params. No path accepts arbitrary Cypher from the client.

- **`vector_search`**: Validates input, calls `VectorStore.search` with `top_k` bounds (1–50 per schema).

- **`hybrid_retrieve`**: Validates input, constructs `GraphRetriever` and `HybridRetriever` with `vector_top_k`, `graph_hops`, and optional `node_label_hint`, then returns a dict with `context` and `trace`.

- **`fetch_regulation`**: Runs `get_regulation_by_id` and `get_regulation_articles` via the named query layer and returns `regulation` and `articles`.

### Structured JSON request/response (conceptual)

Although production MCP uses its own message framing over the chosen transport, ARIA’s in-process contract is JSON-shaped at the tool boundary:

**Request (invocation)** — logical shape:

```json
{
  "tool_name": "graph_query",
  "arguments": {
    "query_name": "impact_by_regulation",
    "parameters": { "regulation_id": "REG-123" }
  }
}
```

**Response (result envelope)** — matches `ToolResult`:

```json
{
  "tool_name": "graph_query",
  "success": true,
  "data": [ { "system_id": "...", "requirement_id": "..." } ],
  "error": null
}
```

On failure, `success` is `false`, `data` may be omitted, and `error` carries a human-readable message (for example, missing Neo4j client or validation error).

### Bridging orchestration to MCP

**`MCPToolPortsAdapter`** adapts `MCPServer` to the **`ToolPorts`** protocol declared in `aria/orchestration/scratch/nodes.py`. Methods such as `query_graph` and `vector_search` call `call_tool` with dict arguments matching the Pydantic models, check `result.success`, and either return `result.data` or raise with `result.error`. Higher-level agent operations (`extract_entities`, `write_to_graph`) remain on the adapter as orchestration concerns while graph and vector reads go through MCP tool names.

Module documentation notes that a production deployment might run MCP as a **sidecar** with HTTP transport; locally, behavior is **in-process** with the same interface contract.

## Tradeoffs

**Advantages**

- Clear separation between “what agents may do” and “how Neo4j/Chroma are wired.”
- Schema-first arguments catch mistakes early and support documentation and optional UI generation.
- Named queries enforce a deliberate security posture for graph reads.

**Costs and limitations**

- Indirection versus direct imports: stack traces and debugging span adapter, server, and handlers.
- This repository emphasizes the **contract**; wiring the official MCP SDK and remote transport is left as a deployment step if full ecosystem interoperability is required.
- Tool design is subjective: fine-grained tools improve composability but can overwhelm discovery; coarse tools hide flexibility.

## Operational considerations

- **Logging**: `MCPServer.call_tool` logs completion time per tool name, supporting latency dashboards for retrieval-heavy workloads.
- **Configuration**: Handlers require injected `Neo4jClient` and `VectorStore`; missing configuration surfaces as explicit `RuntimeError` or `ToolResult` failures rather than silent empty results.
- **Testing**: Handlers are async and depend on typed inputs; unit tests can mock clients and assert on `ToolResult` without invoking real databases when appropriate.

## Further reading

- [Model Context Protocol — specification and documentation](https://modelcontextprotocol.io/) (Anthropic and community).
- [Neo4j Cypher manual](https://neo4j.com/docs/cypher-manual/current/) — parameterized queries and injection-aware design.
- Internal: `aria/graph/queries.py` — allow-listed query registry backing `graph_query` and `fetch_regulation`.
- Internal: `aria/retrieval/hybrid_retriever.py` — hybrid retrieval behavior behind `hybrid_retrieve`.
- Internal: `aria/protocols/mcp/server.py` — `MCPServer` and `MCPToolPortsAdapter`.
- Internal: `aria/protocols/mcp/__init__.py` — package docstring describing the MCP tool server role.

The four-tool surface (`graph_query`, `vector_search`, `hybrid_retrieve`, `fetch_regulation`) is intentionally narrow for a portfolio: it demonstrates MCP principles without enumerating every read path in `aria/graph/queries.py`. Additional named queries can be exposed by extending `TOOL_DEFINITIONS` and `_handlers` in parallel with new registry entries.
