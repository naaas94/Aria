# Evaluating Agentic Systems in ARIA

## Concept definition

**Agentic systems** combine language models with **control flow** (graphs, planners, supervisors), **tools** (retrieval, APIs, databases), and **state** that evolves over many steps. **Evaluation** therefore spans more than a single final string: it must address **whether the system took appropriate steps** (**trajectory evaluation**), **whether tools were invoked correctly** (**tool call accuracy**), **whether retrieved context was sufficient** (**retrieval quality**), **whether outputs satisfy schemas and policies** (**output contract validation**), and **whether behavior stays stable across releases** (**regression testing**).

Unlike traditional unit tests with deterministic assertions, many agent evaluations are **probabilistic**: the same prompt can yield different valid paths or phrasings. Mature practice combines **structural checks** (traces, schemas, tool arguments), **reference-based or rubric scoring**, and **repeated sampling** with statistical summaries.

## Why it matters

Regulatory and compliance-oriented applications amplify evaluation stakes. Wrong **routing** can skip mandatory analysis steps; wrong **retrieval** can omit obligations or invent coverage; invalid **structured outputs** break downstream auditors or dashboards. Without explicit eval harnesses, teams discover failures only in production or through expensive manual review.

ARIA (Automated Regulatory Impact Agent) uses **Neo4j**, **ChromaDB**, **GraphRAG**, **multi-agent orchestration**, **MCP**, and **A2A**-style protocols. Each layer introduces **failure modes**: graph queries can be empty, embeddings can drift, agents can mis-delegate. A portfolio project should show **how** you would score quality—not only that a demo runs once.

## How it is implemented in this repo

The evaluation-oriented code lives under **`tests/eval/`**, marked with **`@pytest.mark.eval`**. Run examples:

- `pytest tests/eval/graphrag_vs_vector_rag.py -v --tb=short -m eval`
- `pytest tests/eval/agent_trace_analysis.py -v --tb=short -m eval`

### Trajectory evaluation

**Trajectory evaluation** asks whether the **sequence of steps** (nodes, sub-agents, or phases) matches expectations for a given task class.

In **`agent_trace_analysis.py`**, **`AgentTrace`** aggregates **`TraceStep`** records (node name, input/output state snapshots, tool call names, duration, errors). **`evaluate_trace`** returns a **`TraceEvaluation`** with booleans for **correct routing**, **correct tool usage**, **efficient path**, and **completed successfully**, plus a list of **issues**.

The module defines **expected flows** aligned with **`aria/orchestration/scratch/paths.py`** (same sequences as **`build_default_graph`** / **`EDGE_MAP`**), for example:

- **`EXPECTED_INGESTION_FLOW`**: `supervisor` → `ingestion` → `entity_extractor` → `graph_builder` → `end`
- **`EXPECTED_QUERY_FLOW`**: `supervisor` → `impact_analyzer` → `report_generator` → `end`
- **`EXPECTED_FREE_QUERY_FLOW`**: `supervisor` → `free_query` → `end`

Tests assert that a **synthetic** trace matching the ingestion flow passes, that **errors** mark completion as failed, that **excessive repetition** of a node flags **inefficient_path**, and that **wrong ordering** (e.g. jumping to **`report_generator`** after **`supervisor`**) fails **correct_routing**.

When you change **`EDGE_MAP`** or default node wiring, update **`paths.py`** and these **`EXPECTED_*`** aliases together so trajectory evals stay honest.

### Tool call accuracy

**Tool call accuracy** checks that the right **tools** run with **valid arguments** and **expected cardinality** (not too few or too many redundant calls).

The trace model’s **`tool_calls: list[str]`** per step and **`tool_call_count`** on **`AgentTrace`** support aggregating usage. The current **`evaluate_trace`** focuses on **routing**, **errors**, **length**, and **loop heuristics**; **`correct_tool_usage`** is reserved for extension. A natural next step is to assert **per-node** expected tools (e.g. **`ingestion`** must record **`extract_entities`**) and validate argument shapes against **Pydantic** contracts in **`aria/contracts/`**.

### Retrieval quality scoring

**`graphrag_vs_vector_rag.py`** implements a **retrieval quality** comparison scaffold between **GraphRAG** and **pure vector RAG**. It defines **`EvalQuestion`** objects with:

- **`question`**: natural-language compliance query
- **`expected_components`**: abstract facets the retrieved context should cover (e.g. **`system_name`**, **`requirement_text`**, **`gap_status`**)
- **`requires_multi_hop`**: whether the question is designed to need graph-style traversal

**`EVAL_QUESTIONS`** includes multi-hop scenarios (EU AI Act coverage gaps, deadlines and teams, cross-regulation joins, data-type-driven system lists) and a **single-hop** baseline (GDPR right to erasure) where vector RAG is expected to be competitive.

**`score_retrieval`** takes **`retrieved_context`** and a **`strategy`** label (`"vector"` or `"graphrag"`), then computes **`RetrievalScore`** with per-component **boolean hits** and **`completeness`** as the fraction of components matched. Matching uses a **lexical keyword table** (e.g. **`gap_status`** → `"gap"`, `"uncovered"`, `"no policy"`). The docstring states this is **simplified**; production would add **LLM-as-judge**, embedding similarity, or **human labels**.

Tests under **`TestEvalQuestionDefinitions`** validate the **question set** (unique IDs, presence of components, mix of multi-hop vs single-hop). **`TestScoringMechanism`** verifies **perfect**, **zero**, and **partial** scores on synthetic strings.

### Output contract validation

ARIA centralizes structured payloads in **Pydantic** models under **`aria/contracts/`** (regulations, graph entities, impact reports). **Output contract validation** means:

- Parsing tool and LLM JSON through **`model_validate`**
- Failing fast with clear **`error`** fields in **`ARIAState`**

The orchestration **nodes** already enforce many contracts (e.g. **`ExtractedEntities`**, **`ImpactReport`**). **Eval** can be extended with **golden JSON** fixtures and **pytest** parametrization to assert **schema compliance** independent of natural-language report text.

### Regression testing

**Regression testing** for agents combines:

- **Frozen fixtures** (documents, graph seeds, embedding snapshots where feasible)
- **Trace-level assertions** (as in **`agent_trace_analysis.py`**)
- **Retrieval completeness thresholds** over **`EVAL_QUESTIONS`** (once wired to live or recorded retrievers)

The **`@pytest.mark.eval`** marker separates slower or environment-dependent suites from fast unit tests. CI can run eval tests on a schedule or behind a flag to manage **flake** from **non-deterministic** models.

### API contracts, security, and golden suite

Beyond retrieval and trace modules, **`tests/eval/`** includes:

- **`test_api_contracts.py`** — HTTP response shapes, error codes, named Cypher return aliases, readiness JSON, and related REST contracts.
- **`test_security_audit.py`** — API key behavior, observability route gating, A2A shared secret header, OpenAPI path set vs `expected_api_paths.py`, and similar checks.
- **`golden_set/`** — YAML cases (trace, retrieval, contract, security, edge) run via **`tests/eval/golden_set/test_goldens.py`**; **`aria eval`** exercises this harness.

### Non-deterministic LLM outputs and stable evaluation

Language models introduce **variance** in wording, optional reasoning steps, and occasional **tool argument drift**. Strategies used in industry and applicable to ARIA:

1. **Evaluate structure before prose**  
   Prefer **node paths**, **tool names**, **JSON schema validity**, and **retrieval component hits** over exact string match of free text.

2. **Temperature and seed control**  
   For local models (**Ollama**), fix **temperature** and **seed** where the runtime supports it; document remaining variance.

3. **Repeated trials**  
   Run **N** samples; report **success rate** or **distribution** of completeness scores rather than a single pass/fail.

4. **LLM-as-judge with rubrics**  
   Use a separate, constrained prompt to score relevance; cache judgments and version the rubric.

5. **Record-and-replay**  
   For CI, replay **recorded** tool responses (graph rows, chunk text) so tests do not depend on live LLM calls.

The eval modules intentionally mix **deterministic** tests (question definitions, scoring arithmetic) with **hooks** for **non-deterministic** integration once retrievers and agents are connected.

### Evaluating MCP and A2A boundaries (conceptual)

**MCP** exposes tools over a structured protocol; **A2A** delegates tasks between agents over HTTP. Evaluation at these boundaries overlaps with **integration testing**:

- **MCP**: Assert **tool name**, **JSON arguments**, **latency** (see **`aria/observability/metrics.py`** for counters and histograms you can drive assertions against in staging).
- **A2A**: Assert **agent card** metadata, **routing** to the correct peer **`endpoint`**, and **serialized task** shape (**`aria/protocols/a2a/`**).

Unit tests typically **mock** transports; eval suites **exercise** them end-to-end against local servers. ARIA’s **`ToolPorts`** protocol in **`scratch/nodes.py`** is the seam where **mock** versus **real** MCP implementations swap for **different eval tiers**.

### Golden datasets and version control

For regulatory text, **golden documents** (synthetic or redacted real excerpts) should live beside **expected extracted entities** and **expected graph patterns** (e.g. regulation nodes linked to requirements). When **Pydantic** models or **Cypher** templates change, **golden files** make diffs visible. Pair them with **`graphrag_vs_vector_rag`**-style **component lists** so retrieval evals stay aligned with **ontology** updates.

### CI tiers: smoke versus deep eval

A practical layout:

| Tier | Scope | Typical gate |
|------|--------|----------------|
| Fast | Schema, trace logic, scoring unit tests | Every commit |
| Medium | Mocked tools, fixed embeddings | Pull request |
| Slow | Neo4j + Chroma + Ollama, full GraphRAG | Nightly or manual |

Document which tier **`pytest -m eval`** maps to in your pipeline so contributors know why a job skipped or failed.

## Tradeoffs

- **Lexical retrieval scoring** is **cheap and deterministic** but **brittle** to paraphrases and multilingual text.
- **Trace equality** against a single golden path **misses** valid alternative strategies unless you allow **sets** of acceptable paths.
- **Heavy eval** (live Neo4j, Chroma, Ollama) improves **fidelity** but hurts **CI speed** and **reproducibility** without containers and seeds.
- **LLM-as-judge** scales rubric coverage but introduces **second-order** non-determinism and **bias**; it must be versioned like any model.
- **Mock-heavy CI** gives **stable** signals but can **drift** from production if mocks do not track **contract** changes in **`aria/contracts/`**.
- **Human evaluation** remains the **ground truth** for high-stakes compliance copy; automate **structure**, sample **substance**.

## Further reading

- ARIA eval suite: `tests/eval/graphrag_vs_vector_rag.py`, `tests/eval/agent_trace_analysis.py`, `tests/eval/golden_set/`, `tests/eval/test_api_contracts.py`, `tests/eval/test_security_audit.py`.
- Canonical orchestration paths for trace expectations: `aria/orchestration/scratch/paths.py`.
- Release-level changes: repo root `CHANGELOG.md`.
- Orchestration traces: `aria/orchestration/scratch/graph.py` (`ExecutionResult`, `StepTrace`, `to_trace_dict`).
- Contracts for validation targets: `aria/contracts/`.
- **Agent evaluation** surveys: search for “LLM agent evaluation benchmark” and “tool use evaluation” for current public leaderboards and methodologies.
- **RAG evaluation**: LangSmith / Ragas-style metrics (faithfulness, context precision) as upgrades to lexical **`score_retrieval`**.

### Appendix: eval question IDs in `graphrag_vs_vector_rag.py`

| ID  | Theme |
|-----|--------|
| q1  | AI Act requirements, systems, policy gaps |
| q2  | Deadlines, articles, team responsibility |
| q3  | Cross-regulation overlap (GDPR + AI Act) via teams |
| q4  | Single-hop GDPR factual (vector-friendly baseline) |
| q5  | Systems, data types, requirements, regulations |

These IDs anchor **regression reports** and **before/after** comparisons when changing retrieval or graph schema.

Together, structural trace checks and retrieval completeness provide a **defensible baseline** for iterating on ARIA without relying solely on anecdotal chat transcripts.
