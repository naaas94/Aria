# Product / architecture audit — orchestration, GraphRAG vs vector, MCP / A2A

**Scope:** Orchestration & agents (supervisor, LangGraph reference, scratch state), GraphRAG vs vector retrieval eval, MCP / A2A protocols.  
**Method:** Static code review (CI not run for this document).  
**Date:** 2026-04-09

---

## Executive summary

- **Scratch orchestration** (`OrchestrationGraph`, `MAX_STEPS`, `StepTrace`, `ExecutionResult.to_trace_dict`) is the real execution path and is **well covered** by eval tests (`tests/eval/test_trajectory_eval.py`) and integration tests using `MockToolPorts`. **Per-step graph traces are in-memory** unless callers persist `to_trace_dict()`; they are **not** automatically written to `TelemetryStore` (unlike `BaseAgent.run()`, which records `agent_executions`).
- **LangGraph reference** (`aria/orchestration/langgraph_reference/`) mirrors **routing topology** and reuses `scratch.edges`, but **several nodes are stubs** (`langgraph_reference/nodes.py` docstring and `entity_extractor` / `free_query` implementations). There are **no tests** importing `build_langgraph()` (optional `aria[langgraph]`). **Not a production-equivalent runtime** without further work.
- **GraphRAG vs vector “eval”** (`tests/eval/graphrag_vs_vector_rag.py` + `scripts/benchmark_retrieval.py`) uses **lexical keyword hits** and, in the script, **fixed synthetic context strings**—useful as a **smoke / methodology placeholder**, **not** as evidence of live retrieval quality. **`tests/eval/e2e/test_live_queries.py`** documents **live** `POST /query` behavior when `ARIA_PLACEHOLDER_API=false` (needs runtime + CI env)—that is the closer product signal.
- **MCP** (`MCPServer`): graph access is **named, parameterized Cypher only** (`execute_named_query` in `aria/graph/queries.py`); failures return **generic** `ToolResult` messages; Prometheus counters/histograms exist. **MCP is not mounted as a separate HTTP surface in `api/main.py`**—it is an **in-process** protocol used via adapters (README architecture still accurate at a logical level).
- **A2A**: server can enforce `X-A2A-Secret` when `A2A_SHARED_SECRET` is set (`verify_a2a_secret_when_configured`). **`A2AClient.delegate_task` never sends that header**, so secured peer agents would **401**; default cards with `localhost` endpoints are **dev-shaped**. **`/a2a/health` is unauthenticated** (by design in `A2AServer._setup_routes`).

---

## Scope map

| Area | Primary locations |
|------|-------------------|
| Scratch graph runtime | `aria/orchestration/scratch/graph.py` (`OrchestrationGraph.execute`, `MAX_STEPS`, `StepTrace`, `ExecutionResult`), `aria/orchestration/scratch/edges.py`, `aria/orchestration/scratch/state.py`, `aria/orchestration/scratch/nodes.py` |
| LangGraph reference | `aria/orchestration/langgraph_reference/graph.py` (`build_langgraph`), `nodes.py`, `state.py` |
| Docs (orchestration) | `docs/07_agent_orchestration_patterns.md`, `docs/09_langgraph_reference.md` |
| GraphRAG vs vector eval | `tests/eval/graphrag_vs_vector_rag.py`, `scripts/benchmark_retrieval.py` |
| Live query E2E | `tests/eval/e2e/test_live_queries.py`, `api/routers/query.py` |
| MCP | `aria/protocols/mcp/server.py`, `tools.py`, `aria/graph/queries.py`, `MCPToolPortsAdapter` in same file |
| A2A | `aria/protocols/a2a/server.py`, `client.py`, `aria/protocols/a2a/agent_card.py` |
| API / security context | `api/main.py`, `api/deps.py` (API key), `.env.example` |
| Telemetry (complement) | `aria/observability/telemetry_store.py`, `api/middleware_telemetry.py`, `aria/agents/base.py` (`record_agent_execution` on `run()` only) |
| Golden / contract tests | `tests/eval/golden_set/runner.py` (A2A + MCP checks), `tests/eval/test_api_contracts.py` |

---

## Findings

| Severity | Finding | Evidence | Impact | Recommendation |
|----------|-----------|----------|--------|----------------|
| **P1** | **`A2AClient` does not send `X-A2A-Secret`**, so outbound delegation fails against servers that enforce `A2A_SHARED_SECRET`. | `aria/protocols/a2a/client.py` (`delegate_task`: `httpx` POST with JSON only, no headers); server gate in `aria/protocols/a2a/server.py` (`verify_a2a_secret_when_configured`). | Secured multi-agent setups: **broken delegation**; if peers omit the secret, **unauthenticated** access (dev only). | **Must-fix for real A2A:** add optional header from env (e.g. same `A2A_SHARED_SECRET`) and tests that 401 without it / 200 with it. |
| **P1** | **GraphRAG vs vector benchmark is not a live retrieval experiment**: `scripts/benchmark_retrieval.py` feeds **two fixed strings** into `score_retrieval`; scoring is **lexical keywords**, and the file comments admit simplification. | `scripts/benchmark_retrieval.py` (`vector_context` / `graphrag_context`); `tests/eval/graphrag_vs_vector_rag.py` (`score_retrieval`, lines 86–88). | **Misleading product conclusions** if treated as measured retrieval quality. | Treat as **methodology stub**; for decisions, rely on **`tests/eval/e2e/test_live_queries.py`** + seeded graph, or add a script that calls real `HybridRetriever` / vector store with the same `EVAL_QUESTIONS`. |
| **P2** | **LangGraph reference is explicitly partial** (stubs, `_NoopTools` for supervisor/ingestion); **no automated LangGraph tests** in `tests/`. | `aria/orchestration/langgraph_reference/nodes.py` (lines 1–7, `_NoopTools`, stub `entity_extractor` / `free_query`); no `build_langgraph` in tests. | Risk of **assuming parity** with scratch or production behavior. | Document in README pointer, or add **optional** `pytest` skip-if-no-langgraph smoke that compiles and runs one trivial invoke; keep scope minimal. |
| **P2** | **Orchestration traces vs telemetry**: graph execution produces **`ExecutionResult.traces`** but **does not** call `TelemetryStore.record_agent_execution`; that path is **`BaseAgent.run()`** only. | `aria/orchestration/scratch/graph.py` vs `aria/agents/base.py` (`record_agent_execution` in `run()`); nodes call `tools.*` directly in `scratch/nodes.py`. | **Dashboards / SQLite** may **under-count** agent work done inside the graph; correlation is **HTTP-centric** unless you bridge traces. | If product needs it: emit one telemetry row or structured log per `ExecutionResult.to_trace_dict()` at API boundary (smallest change: single call site). |
| **P2** | **`/telemetry` and `/metrics` are unauthenticated** (documented). | `api/main.py` (telemetry router without `_route_auth`); `.env.example` lines 46–48. | **Info disclosure** (latencies, paths) if exposed to untrusted networks. | Ops: **network policy / reverse proxy**; not necessarily code change. |
| **P3** | **`StepTrace.error` duplicates `state.error`** for the step (same string on every trace after first error until routed to `end`). | `aria/orchestration/scratch/graph.py` lines 127–136. | Telemetry readers might think **multiple distinct failures**. | Optional: record error only on transition into error state (small follow-up). |
| **P3** | **Telemetry middleware swallows store failures** (`except Exception: pass`). | `api/middleware_telemetry.py` lines 50–51. | **Silent loss** of HTTP rows under DB pressure. | Log at warning once or increment a **dropped** counter (narrow change). |

---

## Failure-mode matrix

| Scenario | Symptom | Mitigation |
|----------|---------|------------|
| **Misconfig: `A2A_SHARED_SECRET` set on peer, not on client** | `401` on `POST .../a2a/tasks`; delegation returns failed envelope | Align client to send `X-A2A-Secret`; document env in runbooks |
| **Misconfig: Neo4j/Chroma missing while `ARIA_PLACEHOLDER_API=false`** | `503` / errors from query or MCP handlers | `GET /ready`, logs; `MCPServer` returns `MCP_TOOL_EXECUTION_FAILED` with generic text |
| **Partial failure: MCP tool handler throws** | Caller sees `ToolResult` with `error_code` / generic message; **stack in server logs** | Pattern in `MCPServer.call_tool` (`aria/protocols/mcp/server.py` 77–86) |
| **Scale: multi-worker API + SQLite telemetry** | Contention; `busy_timeout=5000`; possible **silent skip** in middleware | `telemetry_store.py` WAL + lock; **horizontally**: external store or single writer |
| **Orchestration loop / bad routing** | `state.error` set; edge forces `"end"`; **max steps** sets error | `graph.py` 139–153; `test_trajectory_eval.py` documents semantics |
| **Trusting lexical GraphRAG vs vector scores** | **Optimistic** scores if synthetic context is rich | Use live E2E or LLM-judge; see `graphrag_vs_vector_rag.py` 86–88 |

---

## Test gaps

- **LangGraph:** no `build_langgraph()` compile/run test (optional dependency may justify skip).
- **GraphRAG vs vector:** tests only cover **question definitions** and **scoring mechanics**, not **retrieval** (`TestEvalQuestionDefinitions`, `TestScoringMechanism` in `graphrag_vs_vector_rag.py`).
- **A2A client + secret:** golden set covers server-side enforcement (`tests/eval/golden_set/runner.py`); **client** path not covered for the header gap.
- **End-to-end product comparison:** `tests/eval/e2e/test_live_queries.py` is the right layer; **CI coverage** depends on env (file states nightly/live)—not verified in this audit.

---

## Recommended next steps (ordered, smallest viable first)

1. **P1 — A2A client:** add `X-A2A-Secret` when `A2A_SHARED_SECRET` is set; unit test with `httpx.MockTransport` or ASGI `TestClient` against `A2AServer`.
2. **P1 — Benchmark honesty:** clarify that `scripts/benchmark_retrieval.py` uses synthetic strings, or wire it to real retrievers behind a flag; avoid presenting it as measured production retrieval quality.
3. **P2 — LangGraph:** one optional smoke test **or** a single doc sentence: reference graph is routing-aligned; nodes may be stubbed.
4. **P2 — Traceability:** if product requires SQLite/agent metrics for graph runs, persist `ExecutionResult.to_trace_dict()` at the API entry that runs the graph (single call site).
5. **P3 — Telemetry middleware:** log or metric on `record_request` failure (narrow).

---

## Out of scope but related

General API auth (`API_KEY`), placeholder mode (`ARIA_PLACEHOLDER_API`), schema version enforcement (`tests/eval/test_api_contracts.py` notes), Neo4j password defaults in `.env.example` (dev-only comment present).
