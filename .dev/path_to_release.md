# Path to Release — Gap Analysis

**Date:** 2026-04-10
**DoD:** CLI wet runs + fix what breaks · cost tracking in observability · latency/health monitoring · eval polish + final wet run
**Source:** Full codebase audit (72+ modules under `aria/`, 51+ test files, 3 CI workflows, API surface, infra, eval harness)

---

## Executive summary

ARIA has a solid architectural skeleton: multi-agent orchestration, GraphRAG retrieval, Pydantic contracts, tiered golden-set evaluation, Prometheus + SQLite telemetry, and CI/nightly pipelines. But the system has never been run end-to-end from the terminal as a user would. **No CLI exists.** The API works in placeholder mode but the live path (Neo4j + Chroma + LLM) has not been wet-run through a complete ingest→query→impact flow in one session. The gap between "code compiles and tests pass" and "a human can type a command and watch agents work" is the core blocker.

---

## 1. CLI — does not exist

### What's missing

There is **no CLI module, no `[project.scripts]` entry, and no console entry point** anywhere in the project. Today the only ways to interact with ARIA are:

| Method | What it covers |
|--------|---------------|
| `uvicorn api.main:app` | HTTP surface (placeholder by default) |
| `pytest` with markers | Eval harness, golden sets, security audits |
| `python -m tests.eval.eval_store` | Eval JSONL review (list / review / summary) |
| `python scripts/seed_graph.py` | Seed Neo4j with sample entities |
| `python scripts/seed_corpus.py` | Ingest sample HTML through `ingest_document` |
| `python scripts/benchmark_retrieval.py` | Print lexical-score comparison table |

None of these let a user say: `aria ingest doc.pdf && aria query "What gaps do we have?"`.

### What needs to be built

A `cli/` package (or `aria/cli/`) with at minimum:

| Command | What it does | Wiring target |
|---------|-------------|---------------|
| `aria serve` | Start the FastAPI server (wraps `uvicorn`) | `api.main:app` |
| `aria ingest <file>` | Run full ingestion pipeline on a local file | `aria.ingestion.pipeline.ingest_document` |
| `aria query "<question>"` | Send a compliance query and print answer + sources | `POST /query` or direct `HybridRetriever` + `LLMClient` |
| `aria impact <regulation_id>` | Run impact analysis and print summary | `POST /impact/{id}` or direct `ImpactAnalyzerAgent` |
| `aria status` | Show connection health (Neo4j, Chroma, LLM) | `api.readiness.readiness_payload` logic |
| `aria eval` | Run golden-set tests, print report | Wraps `pytest tests/eval/golden_set/` |
| `aria telemetry` | Print cost/latency summary from SQLite | `TelemetryStore.telemetry_summary` |

**Files to create / modify:**
- `aria/cli/__init__.py` — package
- `aria/cli/main.py` — argument parser (argparse or click/typer)
- `aria/cli/commands/` — one module per command
- `pyproject.toml` — add `[project.scripts]` entry: `aria = "aria.cli.main:main"`

### Wet-run risks

When someone first runs `aria ingest` and `aria query` against a real stack, these things will break:

1. **`ingest_document` has no HTTP caller** — the HTTP `/ingest/text` route only chunks; the full pipeline (`parse→chunk→extract→graph→vectors`) is only called from scripts and tests. The CLI must call `ingest_document()` directly.
2. **`LLMClient` requires a running Ollama (or cloud key)** — first-time users will hit `ConnectionError` from LiteLLM if Ollama isn't up. The CLI needs a preflight check.
3. **`VectorStore.connect()` can fail silently** — `connections.py` catches all exceptions; the CLI should surface them clearly.
4. **Neo4j schema not auto-created** — `aria/graph/schema.py` has `generate_constraint_statements()` and `generate_index_statements()` but nothing calls them on first run. The CLI (or a `aria init` command) should run DDL.
5. **`OrchestrationGraph` is never called from the API** — the scratch orchestration engine (`aria/orchestration/scratch/graph.py`) is tested in unit tests but `api/routers/query.py` bypasses it entirely and calls `HybridRetriever` + `LLMClient` directly. The "watch agents in action" demo needs to go through the orchestration graph.

---

## 2. Cost tracking in observability

### What exists

| Component | File | Status |
|-----------|------|--------|
| LLM cost capture | `aria/llm/client.py:220-221` | **Works** — reads `response._hidden_params["response_cost"]` from LiteLLM, stores as `cost_usd` in SQLite |
| SQLite `llm_calls` table | `aria/observability/telemetry_store.py:91-103` | Has `cost_usd REAL` column |
| Cost summary query | `telemetry_store.py:250-289` | `cost_summary(since)` returns `total_cost_usd` and `by_model` breakdown |
| `/telemetry` JSON endpoint | `api/routers/telemetry.py:45-68` | Exposes `llm.total_cost_usd` and `llm.cost_by_model` |
| Prometheus LLM counters | `aria/observability/metrics.py:85-96` | `aria_llm_call_total` and `aria_llm_call_duration_seconds` — **no cost gauge** |

### Gaps

| # | Gap | Severity | Fix |
|---|-----|----------|-----|
| C1 | **No Prometheus cost gauge** — cost is only in SQLite, not scrapable. Grafana/alerting can't see spend. | Medium | Add `aria_llm_cost_usd_total` Counter (labels: `model`) in `metrics.py`; increment in `LLMClient.complete()` |
| C2 | **Cost is NULL for Ollama** — local models return no `response_cost`; `cost_usd` column is NULL for all local calls. Dashboard shows $0.00 always during dev. | Low | Expected for local; document it. Optionally compute estimate from token count × configurable rate. |
| C3 | **No per-request cost** — HTTP middleware records latency but not accumulated LLM cost for that request. A single `/query` may make multiple LLM calls (structured output retry path in `complete_structured`). No way to see "this request cost $X". | Medium | Aggregate `cost_usd` by `request_id` in `cost_summary` or add a dedicated view. |
| C4 | **No cost budget / alerting** — no threshold, no env var like `ARIA_MAX_COST_USD_PER_HOUR`, no circuit breaker. | Low | Add optional budget guard; log warning when threshold approached. |
| C5 | **`telemetry_store.py:237-238` swallows cost-write exceptions** — `LLMClient.complete()` line 237 has bare `except Exception: pass` after `record_llm_call`. If SQLite is locked or disk-full, cost data is silently lost. The AUDIT_DIGEST marked this [FIXED] for middleware/agent paths but this specific call site in `client.py` still swallows. | High | Apply same pattern as middleware fix: log warning + increment `aria_telemetry_write_errors_total`. |
| C6 | **No cost in `/telemetry` agent section** — agent executions track `duration_ms` but not cost. If an agent makes multiple LLM calls, the cost is attributed to the LLM layer only, not to the agent. | Low | Join `agent_executions.request_id` to `llm_calls.request_id` for per-agent cost view. |

---

## 3. Latency / health monitoring

### What exists

| Component | File | Status |
|-----------|------|--------|
| HTTP latency (Prometheus) | `aria/observability/metrics.py:15-18` | `aria_http_requests_total` Counter — no histogram (latency not in Prometheus for HTTP!) |
| HTTP latency (SQLite) | `api/middleware_telemetry.py` → `telemetry_store.record_request(latency_ms=…)` | Works; percentiles via `request_summary()` |
| LLM latency (Prometheus) | `metrics.py:91-96` | `aria_llm_call_duration_seconds` Histogram with buckets |
| LLM latency (SQLite) | `telemetry_store.py:148` | `latency_ms` column in `llm_calls` |
| Agent duration (Prometheus) | `metrics.py:59-64` | `aria_agent_execution_duration_seconds` Histogram |
| Agent duration (SQLite) | `telemetry_store.py:206` | `duration_ms` column in `agent_executions` |
| Retrieval latency (Prometheus) | `metrics.py:46-51` | `aria_retrieval_duration_seconds` Histogram |
| `/health` | `api/main.py:192-195` | Liveness only — always `{"status": "healthy"}` |
| `/ready` | `api/main.py:198-203` → `readiness.py` | Probes Neo4j + Chroma via pooled connections |
| Docker healthchecks | `docker-compose.yml` | Neo4j (cypher-shell) + Chroma (curl heartbeat) |

### Gaps

| # | Gap | Severity | Fix |
|---|-----|----------|-----|
| L1 | **No HTTP latency Histogram in Prometheus** — `HTTP_REQUEST_COUNTER` only counts requests by `method`/`status_code`. There is no `aria_http_request_duration_seconds` Histogram, so p50/p95/p99 latency is invisible to Prometheus/Grafana. All HTTP latency percentiles come only from SQLite. | High | Add `HTTP_REQUEST_DURATION = Histogram("aria_http_request_duration_seconds", …, ["method", "path"])` in `metrics.py`. Observe in `middleware_telemetry.py`. |
| L2 | **No LLM health check** — `/ready` probes Neo4j and Chroma but not the LLM provider. If Ollama is down or the API key is invalid, `/ready` still reports healthy and the first `/query` fails with a 500. | High | Add LLM probe to readiness (e.g., `litellm.acompletion` with a 1-token max_tokens and short timeout, or Ollama `/api/tags`). |
| L3 | **`/ready` does not report LLM status** — the readiness JSON has `neo4j` and `chroma` booleans but no `llm` field. | Medium | Add `llm: bool` to readiness payload. |
| L4 | **No startup duration metric** — time from process start to lifespan `yield` is not measured. Slow Neo4j/Chroma connects are invisible. | Low | Log and record startup time at end of lifespan setup. |
| L5 | **Orchestration traces not persisted** — `OrchestrationGraph.execute()` produces `ExecutionResult.traces` (node path, per-step duration) but never writes to `TelemetryStore.record_agent_execution`. Only `BaseAgent.run()` records agent rows. If the orchestration graph is used (which it should be for the demo), per-node timing is lost. | High | Call `record_agent_execution` for each `StepTrace` at the API boundary after `execute()`. |
| L6 | **No graph query latency tracking** — `GRAPH_QUERY_COUNTER` counts queries but there is no `GRAPH_QUERY_DURATION` Histogram. Neo4j slow queries are invisible. | Medium | Add `aria_graph_query_duration_seconds` Histogram. Observe in `queries.py` or `client.py`. |
| L7 | **Ingestion duration Histogram exists but is never observed** — `INGESTION_DURATION` is defined in `metrics.py` but no code calls `.observe()` on it. `INGESTION_COUNTER` is incremented in the HTTP ingest routes, but the full pipeline (`ingest_document`) does not touch Prometheus at all. | Medium | Observe `INGESTION_DURATION` in `ingest_document()` at pipeline completion. |
| L8 | **No alerting / SLO definitions** — no thresholds for p95 latency, error rate, or cost. No Prometheus alerting rules or Grafana dashboard JSON. | Low | Define SLOs (e.g., p95 query < 5s, LLM error rate < 5%) and add a `prometheus/alerts.yml` or document thresholds. |

---

## 4. Eval polish + final wet run

### What exists

The eval harness is extensive:

| Layer | Location | Status |
|-------|----------|--------|
| Golden-set (YAML cases) | `tests/eval/golden_set/cases/` | 31 cases across retrieval, trace, security, contract, edge |
| Multi-lens runner | `tests/eval/golden_set/runner.py` | 6 lenses: contract, trace, retrieval, security, quality, replay |
| Tiered execution | `conftest.py` → `--golden-tier` | fast / medium / slow |
| JUnit + JSON reports | `tests/eval/golden_set/report.py` | `golden_report.json`, `golden_report.xml` |
| Eval store (JSONL) | `tests/eval/eval_store.py` | Append-only + CLI review |
| Trajectory analysis | `tests/eval/test_trajectory_eval.py` | ~566 lines, scratch orchestration paths |
| E2E live queries | `tests/eval/e2e/test_live_queries.py` | httpx → `POST /query` (placeholder + live) |
| GraphRAG vs vector | `tests/eval/graphrag_vs_vector_rag.py` | Lexical scoring benchmark |
| Security audit | `tests/eval/test_security_audit.py` | Auth, CORS, Cypher, MCP, A2A, supply chain |
| Safety / reliability | `tests/eval/test_safety_reliability.py` | Failure injection, idempotency |

### Gaps

| # | Gap | Severity | Fix |
|---|-----|----------|-----|
| E1 | **All 5 retrieval golden cases have `retrieved_context: ""`** — guaranteed failure in medium/slow tiers. This is the #2 P0 from AUDIT_DIGEST and is still unfixed. Nightly is red. | **P0** | Populate `retrieved_context` with deterministic text matching `expected_components`, or switch to replay fixtures. |
| E2 | **Replay directory is empty** — `tests/eval/golden_set/replay/` has only `.gitkeep`. No case uses `expect.replay`. CI step label says "includes replay" — misleading. The recorder infrastructure (`recorder.py`) exists but has never been used. | High | Record at least 1 replay fixture from a live run and add a replay golden case. Or remove "replay" from CI label. |
| E3 | **`requires_multi_hop` is a no-op** — `runner.py:198-199` sets `sub["multi_hop_declared"] = True` but validates nothing about actual multi-hop retrieval. False confidence. | Medium | Implement real multi-hop validation (trace metadata, hop count, graph-expanded context check) or remove flag. |
| E4 | **`slow` tier has no cases** — no YAML file sets `tier: slow`. `--golden-tier=slow` means "run all tiers" by convention but there are no true slow-only cases (e.g., live LLM calls, real retrieval). | Medium | Add 2-3 slow-tier cases that require live infrastructure. |
| E5 | **Quality lens never tested against real LLM output** — quality checks run on `case.input["answer"]` which is hand-written in YAML. No case feeds a real LLM response through the quality lens. | Medium | Add a slow-tier case that calls the LLM and runs quality checks on the response, or record a replay. |
| E6 | **Eval store integration with golden runner is opt-in** — `--emit-eval-store` flag exists but defaults to off. CI fast tier does not emit. Only nightly slow-tier emits. | Low | Acceptable; document explicitly. |
| E7 | **`test_security_audit.py` references non-existent `docs/security_audit_report.md`** — assertion message mentions this file; `docs/` is gitignored and empty. | Low | Fix assertion message to point at `tests/eval/golden_set/cases/security/`. |
| E8 | **GraphRAG benchmark uses synthetic data and lexical scoring** — `benchmark_retrieval.py` and `graphrag_vs_vector_rag.py` use hardcoded strings and keyword matching. Not evidence of real retrieval quality. | Medium | Label as methodology stub. For real eval, use `tests/eval/e2e/test_live_queries.py` with seeded graph. |

---

## 5. Orchestration gap — API bypasses agent graph

This is the highest-impact architectural gap for the "watch agents in action" demo.

### Current state

```
POST /query  →  HybridRetriever.retrieve()  →  LLMClient.complete()  →  response
POST /impact →  ImpactAnalyzerAgent.process()  →  response
```

The API routes call agents and retrievers **directly**. The scratch orchestration engine (`OrchestrationGraph` in `aria/orchestration/scratch/graph.py`) is only exercised in unit tests (`tests/unit/test_orchestration.py`, `tests/eval/test_trajectory_eval.py`).

### What's needed for a demo

```
CLI/API  →  OrchestrationGraph.execute(state, tools)
         →  supervisor classifies intent
         →  routes to ingestion / entity_extractor / graph_builder / impact_analyzer / report_generator
         →  each node calls ToolPorts (MCP bridge)
         →  traces emitted to telemetry
         →  final_report returned
```

### Files involved

| File | Current state | Needed |
|------|--------------|--------|
| `aria/orchestration/scratch/graph.py` | Engine works, tested | Wire to API or CLI |
| `aria/orchestration/scratch/nodes.py` | All 8 nodes implemented | Need real `ToolPorts` (not `_NoopTools`) |
| `aria/protocols/mcp/tools.py` | `MCPToolPortsAdapter` bridges MCP → `ToolPorts` | Never instantiated outside tests |
| `api/routers/query.py` | Calls `HybridRetriever` directly | Option: add `?orchestrated=true` flag to route through `OrchestrationGraph` |
| `api/routers/impact.py` | Calls `ImpactAnalyzerAgent` directly | Same: orchestrated path option |

---

## 6. Missing modules and broken wiring

| # | Item | Files | Status |
|---|------|-------|--------|
| M1 | **CLI package** | Does not exist | Must build (see §1) |
| M2 | **Neo4j schema DDL runner** | `aria/graph/schema.py` has generators; nothing calls them at startup | Add `aria init` or auto-run in lifespan |
| M3 | **`ToolPorts` live implementation** | `MCPToolPortsAdapter` in `aria/protocols/mcp/tools.py` | Exists but never wired to actual Neo4j/Chroma/LLM in a running context |
| M4 | **LangGraph reference** | `aria/orchestration/langgraph_reference/` | Stub nodes (`_NoopTools`), no tests, optional dep — acceptable as reference |
| M5 | **Ingestion HTTP → full pipeline bridge** | `api/routers/ingest.py` only chunks | Documented as intentional; CLI `aria ingest` should call full pipeline |
| M6 | **A2A delegation end-to-end** | `a2a/client.py` sends tasks, `server.py` receives | Never tested with two running ARIA instances |

---

## 7. Current bugs

| # | Bug | File | Severity |
|---|-----|------|----------|
| B1 | **Silent `except Exception: pass` in `LLMClient.complete()`** — lines 237-238 and 277-278 swallow telemetry write failures. AUDIT_DIGEST marked the middleware/agent instances [FIXED] but these two call sites remain. | `aria/llm/client.py` | High |
| B2 | **Retrieval golden cases guaranteed fail** — empty `retrieved_context` across all 5 retrieval YAMLs → medium/slow tiers fail. | `tests/eval/golden_set/cases/retrieval/*.yaml` | P0 |
| B3 | **`StepTrace.error` accumulates** — after the first error, every subsequent `StepTrace` records the same `state.error` string (line 135 in `graph.py`). Trace analysis sees the same error repeated N times. | `aria/orchestration/scratch/graph.py` | Low |
| B4 | **`complete_structured` records 2 `llm_calls` rows for one logical request** — repair path calls `complete()` twice; both record to SQLite with same `request_id`, inflating call counts and cost. | `aria/llm/client.py` | Low |
| B5 | **Prometheus `model` label cardinality unbounded** — `LLM_CALL_COUNTER.labels(model=self.model)` accepts any string. A misconfigured `LLM_MODEL` creates new time series. | `aria/llm/client.py` + `metrics.py` | Low |

---

## 8. Tech debt

| # | Debt | Files | Impact |
|---|------|-------|--------|
| D1 | **Observability routes use two auth patterns** — data routes use `Depends(require_api_key_when_configured)`; observability uses `Depends(require_api_key_for_observability)`. Two code paths, two tests, two mental models. | `api/main.py`, `api/deps.py` | Maintainability |
| D2 | **Configuration via raw `os.getenv` scattered across modules** — `api/config.py` centralizes some, but `connections.py`, `limits.py`, `readiness.py`, `vector_store.py`, `llm/client.py` each read env vars directly. No single settings object. | Multiple | Could use Pydantic Settings for all config |
| D3 | **Golden security checks duplicate `test_security_audit.py`** — `runner.py` reimplements Cypher, API key, A2A, Dockerfile, supply chain checks that also live in the test file. Two sources of truth. | `runner.py`, `test_security_audit.py` | Divergence risk |
| D4 | **`eval_store.py` CLI is a raw `sys.argv` parser** — no argument validation, no help text, no shell completion. | `tests/eval/eval_store.py` | UX |
| D5 | **No type-checking CI step** — `pyproject.toml` configures mypy strict mode but neither `ci.yml` nor `nightly.yml` runs `mypy`. Type errors may accumulate unnoticed. | `.github/workflows/ci.yml` | Quality |
| D6 | **Dockerfile installs twice** — `RUN pip install --no-cache-dir .` then `COPY . .` then `RUN pip install --no-cache-dir -e .`. First install has no source (only `pyproject.toml`), second reinstalls everything. | `Dockerfile` | Build time |
| D7 | **`uv.lock` committed but CI uses `pip install`** — lock file is never consumed in CI; reproducibility benefit is lost. | `ci.yml`, `nightly.yml`, `uv.lock` | Reproducibility |
| D8 | **No `__main__.py`** — `aria` package cannot be run with `python -m aria`. | `aria/` | UX |
| D9 | **Nightly pins Python 3.12 only; CI tests 3.12 + 3.13** — nightly misses 3.13 regressions. | `.github/workflows/nightly.yml` | Coverage |

---

## 9. Execution plan — path to demo-ready release

### Phase 1: Foundations (unblocks everything else)

| Task | Effort | Blocks |
|------|--------|--------|
| Fix B1: replace `except Exception: pass` in `LLMClient` with warning + counter | XS | Cost accuracy |
| Fix B2: populate retrieval golden `retrieved_context` or quarantine cases | S | Nightly green |
| Wire `MCPToolPortsAdapter` to real Neo4j/Chroma/LLM and expose via API or CLI | M | Demo |
| Build CLI skeleton (`aria serve`, `aria status`, `aria ingest`, `aria query`, `aria impact`) | M | Wet run |
| Add `aria init` → run Neo4j DDL from `schema.py` | S | First-time setup |

### Phase 2: Observability completeness (cost + latency + health)

| Task | Effort | Blocks |
|------|--------|--------|
| Add `aria_llm_cost_usd_total` Prometheus Counter; increment in `LLMClient` | S | Cost in Grafana |
| Add `aria_http_request_duration_seconds` Histogram; observe in middleware | S | Latency in Grafana |
| Add LLM health check to `/ready` and readiness payload | S | Accurate readiness |
| Persist orchestration traces to telemetry store | S | Agent-level monitoring |
| Add `aria_graph_query_duration_seconds` Histogram | XS | Graph latency visibility |
| Observe `INGESTION_DURATION` in `ingest_document()` | XS | Ingestion latency visibility |

### Phase 3: Eval polish

| Task | Effort | Blocks |
|------|--------|--------|
| Record first replay fixture from live run | S | Replay lens usable |
| Add 2-3 slow-tier golden cases with real LLM/retrieval | M | Slow-tier meaningful |
| Implement real `requires_multi_hop` validation or remove flag | S | No false confidence |
| Fix `test_security_audit.py` stale reference to `docs/security_audit_report.md` | XS | Clean test output |
| Add `mypy` step to CI | S | Type safety |

### Phase 4: Final wet run

| Task | Effort | Blocks |
|------|--------|--------|
| `docker compose up -d` → `aria init` → `aria ingest <sample_doc>` → `aria query "..."` → `aria impact <reg_id>` → `aria telemetry` | L (time, not code) | Release confidence |
| Fix everything that breaks during the wet run | Variable | Release |
| Record the session as a demo / asciicast | S | Stakeholder demo |

---

## 10. File-level reference

Files that need changes, grouped by workstream:

### CLI (new)
- `aria/cli/__init__.py` — new
- `aria/cli/main.py` — new
- `aria/cli/commands/serve.py` — new
- `aria/cli/commands/ingest.py` — new
- `aria/cli/commands/query.py` — new
- `aria/cli/commands/impact.py` — new
- `aria/cli/commands/status.py` — new
- `aria/cli/commands/init.py` — new
- `aria/cli/commands/eval.py` — new (wraps pytest)
- `aria/cli/commands/telemetry.py` — new
- `pyproject.toml` — add `[project.scripts]`

### Cost tracking
- `aria/observability/metrics.py` — add `LLM_COST_USD_COUNTER`
- `aria/llm/client.py` — increment cost counter; fix bare `except` (lines 237, 277)
- `aria/observability/telemetry_store.py` — optional per-request cost aggregation view

### Latency / health
- `aria/observability/metrics.py` — add `HTTP_REQUEST_DURATION` Histogram, `GRAPH_QUERY_DURATION` Histogram
- `api/middleware_telemetry.py` — observe `HTTP_REQUEST_DURATION`
- `api/readiness.py` — add LLM health probe
- `aria/orchestration/scratch/graph.py` — emit telemetry per step trace
- `aria/ingestion/pipeline.py` — observe `INGESTION_DURATION`
- `aria/graph/queries.py` or `aria/graph/client.py` — observe `GRAPH_QUERY_DURATION`

### Eval polish
- `tests/eval/golden_set/cases/retrieval/*.yaml` (5 files) — populate `retrieved_context`
- `tests/eval/golden_set/replay/` — add first fixture
- `tests/eval/golden_set/runner.py` — implement or remove `requires_multi_hop`
- `tests/eval/test_security_audit.py` — fix stale doc reference
- `.github/workflows/ci.yml` — add mypy step; fix replay label

### Orchestration wiring
- `api/routers/query.py` — optional orchestrated path
- `api/routers/impact.py` — optional orchestrated path
- `aria/protocols/mcp/tools.py` — instantiate `MCPToolPortsAdapter` with live deps

### Tech debt (opportunistic)
- `Dockerfile` — fix double install
- `.github/workflows/ci.yml` — add mypy; use `uv` for reproducibility
- `.github/workflows/nightly.yml` — add Python 3.13
- `api/` config modules — consider Pydantic Settings consolidation
