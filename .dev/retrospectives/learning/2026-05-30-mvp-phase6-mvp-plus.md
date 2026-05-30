# Learning retrospective — MVP Phase 6 (MVP+ orchestrated demo path)

**Date:** 2026-05-30  
**Task:** `mvp-phase6-mvp-plus` — wire live `MCPToolPortsAdapter` behind opt-in orchestrated query (`aria query --orchestrated` / `POST /query` with `orchestrated: true`), persist per-step orchestration traces in existing telemetry tables, and ship a portfolio demo script.  
**Produced:** Commits `a387091` (DTO contracts) → `b2ff729` (per-step telemetry in graph execute) → `e2c725a` (CLI/API routing) → `2248f92` (demo script, README `## Demo`, MVP_PICKUP Phase 6 `[x]`) → `e2aadc6` (live MCP adapter module + `index_vectors` fix + decision log + plan §8 refresh); plan v1.1 at promoted path `.dev/plans/mvp-phase6-mvp-plus/plan.md`; decision log `.dev/decision-logs/T2-mcp-adapter-wiring.md`; audit `.dev/audits/2026-05-30-mvp-phase6-mvp-plus.md` (**pass-with-conditions** at `e2aadc6`). Verification: **128 passed** unit (`pytest tests/unit -q`), **38 passed** trajectory eval.

**Why this qualified:** Phase 6 introduced a **second production entry point** for compliance queries (scratch `OrchestrationGraph` + MCP tool ports vs existing `run_compliance_query` GraphRAG path), an **architectural** adapter/service subtask, and a **process failure** that left routing commits on `dev` while the module they import (`aria.services.orchestrated_query`) was only on disk — clean checkout pytest failed until remediation. The integration story and the commit-ordering incident are both worth compounding.

---

## 1. Task context

Pre-plan exploration (scout SHA `ee87002`, 2026-05-25) returned **CONDITIONAL** readiness: orchestrated semantics vs `run_compliance_query`, per-step telemetry shape, and demo artifact location were unresolved. The orchestrator resolved seven ambiguity flags in plan §0 (vector-only scratch path accepted; factory ownership in `orchestrated_query.py`; `orchestrated` body field on existing DTO; slash-separated `agent_name` rows; placeholder gate literals; demo under `.dev/demo/`).

Execution DAG on paper: contracts (T1) → parallel **{live MCP adapter wiring, per-step trace persistence}** → CLI/API routing (depends on adapter) → demo/README/checkboxes (depends on routing + traces). Reality in git: T1, T3, T4, T5 landed in that order **without a T2 commit**; T4 imported `run_orchestrated_query` from a module that did not exist at `2248f92`; user remediation commit `e2aadc6` landed T2 artifacts plus plan §8 and bundled unrelated retrospective markdown and an OpenAPI adjunct doc.

All four MVP_PICKUP Phase 6 checklist items are marked done. Optional `aria-mvp-demo.cast` was not committed (plan-allowed).

---

## 2. What I now understand that I didn't before

### Two query paths, one product — and that is intentional

Production traffic for “real” compliance Q&A still flows through **`run_compliance_query`** (HybridRetriever + LLM synthesis). Phase 6 adds **`run_orchestrated_query`**, which builds `ARIAState`, runs `OrchestrationGraph.execute` with `MCPToolPortsAdapter`, and returns `execution_trace` from `ExecutionResult.to_trace_dict()`. The scratch **`free_query_node` path is vector-only** (`vector_search` via MCP), not GraphRAG hybrid. Answers will **not** match the standard path — and the plan explicitly rejected parity work as Phase 7 scope.

Portfolio/demo value is **visible multi-agent routing, step timings, and trace JSON**, not answer equivalence. That reframes “wire orchestration into production” from “replace the retriever” to “add an opt-in observability-rich alternate path.” README’s production call graph (Phase 5) stays true for default queries; MVP+ is a flag, not a migration.

### MCP is the adapter seam, not the orchestration engine

`ToolPorts` in scratch nodes is an in-process protocol. **`MCPToolPortsAdapter`** implements it by delegating to **`MCPServer.call_tool`** with live `Neo4jClient` and `VectorStore` injected at construction. Phase 6’s architectural move is **`build_mcp_adapter(conns: AppConnections)`** in `aria/services/orchestrated_query.py` — same layering instinct as `run_compliance_query` taking `AppConnections`, keeping CLI and API as thin routers.

Before this phase, `MCPToolPortsAdapter` was effectively **test/eval infrastructure** (context map: `none_found` production consumers). Phase 6 is the first time the adapter is on a user-invokable path. The graph did not learn MCP; the **service layer** connected existing graph + existing adapter + existing connections.

### Stubs that return success are worse than missing features

`MCPToolPortsAdapter.index_vectors` returned **`True` without writing to Chroma**. Orchestration ingest nodes could “succeed” with no indexed vectors. Fixing it required reading **`VectorStore.index_chunks`** and mapping orchestration chunk dicts to **`DocumentChunk`** — not guessing method names. Kill criterion “no silent no-op” was load-bearing; a green boolean hid a broken demo path.

### Per-step telemetry without schema migration

Instead of a `step_traces` table, each graph step calls **`record_agent_execution`** with `agent_name = "orchestration.scratch/{node_name}"` (including `end`), while the aggregate **`orchestration.scratch`** row remains. **`aria telemetry`** can show per-node durations for the demo’s step 4 without migrations. Tradeoff: N+1 SQLite rows per orchestrated request — acceptable for MVP+ throughput, wrong default if orchestrated became the main path.

### Placeholder mode and orchestrated mode must not compose

With Phase 4’s G8 flip, default is live — but tests and demos still set **`ARIA_PLACEHOLDER_API=true`**. Orchestrated routing without an explicit gate would call **`build_mcp_adapter`** with null clients and fail opaquely. Frozen CLI stderr and API **`detail`** strings (exit 1 / HTTP 400) are part of the contract, not polish. This is the same class of lesson as G8: **mode mistakes should fail loudly with a single sentence the operator can act on.**

### Lazy import is a real integration tool, not a smell to hand-wave

`build_default_graph` is imported **inside** `run_orchestrated_query` to avoid import cycles between `aria.services` and `aria.orchestration.scratch.graph`. The decision log records that choice. I had treated “lazy import in services” as technical debt; here it is the **minimal correct seam** when a service module orchestrates a graph factory without pulling orchestration at import time.

### Conditional JSON fields preserve backward-compatible tests

`execution_trace` on `ComplianceQueryResponse` defaults to **`None`**, and **`_success_payload` omits the key when None**. Phase 4’s `test_query_json_placeholder_returns_valid_payload` uses **exact five-key equality** on the non-orchestrated placeholder path. Adding a sixth key with value `null` would have failed CI even though Pydantic allows the field. **Optional response fields that must not appear on some paths need omission semantics**, not null-in-JSON semantics — especially when tests freeze key sets.

### HTTP mode header vs JSON `aria_mode` can diverge

On orchestrated API success, the router sets **`X-ARIA-Mode: orchestrated-live`**, but `ComplianceQuerySuccess` still carries **`aria_mode="live"`** in the body (audit cold-read). CLI **`--json`** consumers reading only the payload will not see “orchestrated” in `aria_mode`; HTTP clients reading headers will. Not a bug for Phase 6 scope, but a **contract footgun** if clients assume one source of truth for mode labeling.

### Plan DAG edges are logical dependencies; git history is the enforcement layer

The orchestrator correctly marked T4 blocked on T2’s **importable module**. Executors still committed T4 and T5 while T2 existed only in the working tree. **`pytest` on a dirty tree with uncommitted T2 passed (128 tests); clean checkout at `2248f92` failed at import** with `ModuleNotFoundError: aria.services.orchestrated_query`. I now treat “T2 complete” as **“`git show HEAD:aria/services/orchestrated_query.py` succeeds”**, not “agent said done” or “local tests green.”

### CHANGELOG under one dated header is a concurrent write surface (again)

During T3’s commit, an executor staged a **T2 changelog bullet** that belonged to parallel work, then tried to “fix scope” by **deleting the T2 bullet** from the file — worse than leaving a stray line in a commit. Reset/amend recovered file contents in git history, but the incident is documented in plan appendix `documented_mess_up_to_cover_for_in_retro_method`. Phase 4 taught CHANGELOG **semantic** regression; Phase 6 added **cross-subtask vandalism** as a failure mode when scope-hygiene panics.

---

## 3. Decisions I would make again

**Accept vector-only orchestrated answers (Flag 1).** Avoided graph redesign, trajectory eval churn, and false promise of GraphRAG parity in a demo flag.

**Factory + runner in `aria/services/orchestrated_query.py`, not in `compliance_query.py`.** Keeps default query module free of orchestration imports; T4 fans in routing only.

**Single route + `orchestrated: bool` on `ComplianceQueryRequest`**, not `POST /orchestrated-query`. One OpenAPI surface, backward compatible default `False` with `extra="forbid"` preserved.

**Per-step rows via `agent_name` suffix**, not new SQLite schema. Demo-ready with `aria telemetry`; aligns with Phase 3 observability patterns.

**Explicit placeholder gate before adapter construction** with byte-frozen CLI/API messages. Surfaces 8/9 from context map closed cleanly.

**Lazy `build_default_graph` import inside `run_orchestrated_query`.** Kill criterion for circular import did not fire; tests and mypy stayed green.

**Demo script structure** (`.dev/demo/aria-mvp-demo.sh`): `export ARIA_PLACEHOLDER_API=false`, `aria status`, standard query, `--orchestrated --json`, `aria telemetry --hours 1`. Makes the two-path story legible without reading source.

**Tiered CHANGELOG with deferred coverage gaps** (API placeholder 400 unit test, full orchestrated success path, DTO-only round-trip). Auditor accepted documented deferrals — same discipline as Phases 3–4.

**Generalizable principle:** For **“wire existing graph/adapters into CLI/API”** phases, the plan product is **integration contracts and failure envelopes**; the demo is proof those seams work, not that answers improved.

---

## 4. Decisions I would change

**Enforce T2 commit before allowing T4/T5 commits on `dev`.** Human or agent checklist: after T4 packet, run `git show HEAD:aria/services/orchestrated_query.py` before push. Optional CI: import every module referenced from `api/routers/*.py` in a minimal job. The DAG was right; **execution order violated it without technical merge conflict** — only importers broke.

**Never edit another subtask’s CHANGELOG bullet when fixing index scope.** Reset staged hunks (`git restore --staged`) or `git add -p CHANGELOG.md` for **only** the new bullet; do not delete peer lines. Plan appendix already proposes this; I should treat it as **hard executor law**.

**Avoid `git commit --amend` on a dirty index with parallel work in flight.** T3 recovery used reset + clean recommit — correct — but amend briefly swept T2 files into the wrong commit. **Better rule:** amend only when `git status` shows exclusively owned paths staged.

**Make `e2aadc6` T2-only.** That commit also added Phase 4/5 learning retrospectives and `.dev/demo-openapi-browser-adjunct.md` (audit F-03). Process noise makes `git log` archaeology harder and blurs “what Phase 6 changed.”

**Refresh plan §8 and Status in the same commit as T2 code**, not only inside a mega-commit mixed with retros. At audit time, §8 still described “T2 missing” until read against `e2aadc6` — narrative lag identical to Phase 4’s closure-at-HEAD lesson.

**Align `test_mcp_adapter_construction` with §2 contract.** Test constructs `MCPToolPortsAdapter` directly; contract ties the name to **`build_mcp_adapter`**. Factory is trivial today; the drift is how contracts erode (audit F-04).

**Consider committing API placeholder + orchestrated test before calling T4 done.** CHANGELOG defers it; one FastAPI TestClient case would have caught gate regressions symmetric to CLI smoke.

**Underlying errors:** Treating executor completion as subtask completion without **artifact-at-HEAD** check; repeating CHANGELOG parallel-write mistakes from Phase 4 without a mechanical guard; bundling unrelated docs at closure “while I’m committing.”

**Better rule:** After any subtask that **exports a symbol others import**, the closure check is **`git show HEAD:<path>` + clean-tree `pytest`**, not working-tree pytest.

---

## 5. Patterns in my own thinking

**Assumed parallel {T2,T3} safety implied parallel {T2,T4} execution.** File disjointness for T2/T3 was real; T4’s **logical** dependency on T2 was stronger than T3’s. I did not treat “T4 started” as a red flag while T2 was uncommitted.

**Over-weighted green pytest locally.** Dirty tree masked a broken `dev` for anyone cloning at `2248f92`. Same failure mode as “works on my machine,” but **self-inflicted** by commit order.

**Trusted CHANGELOG bullets at HEAD as evidence T2 landed.** T2 bullet appeared before T2 code commit — **narrative/code drift**. I should read bullets as claims to verify with `git show`, not as provenance.

**Scope-hygiene panic in executors (observed, not only my action).** Deleting another subtask’s audit trail to fix a bad `git add` is motivated reasoning: “the commit must be pure” at the cost of **destroying someone else’s in-progress truth**. The correct move is index surgery only.

**Relief at pass-with-conditions audit while plan Status still Active.** Implementation met intent at `e2aadc6`; process artifacts lagged. I am still prone to conflate **“code audit pass”** with **“phase closed.”**

**Underweighted wet-run for orchestrated path.** Demo script is manual; no committed asciicast. Unit tests defer full `run_orchestrated_query` success. I know the vector-only path works in theory; **I have not internalized operator experience** of side-by-side answers from one question (steps 2–3 in demo script).

**Compared Phase 6 favorably to “just wiring.”** Wiring across CLI → service → adapter → MCP → graph → telemetry is **most of the system surface area** for agentic demos; LOC is small, coupling is not.

---

## 6. Open questions

- Should **`aria_mode` in JSON** align with **`X-ARIA-Mode`** for orchestrated responses (`orchestrated-live` or similar), or is dual signaling intentional for backward compatibility?
- Is there a **pre-push hook or CI job** that imports all router dependencies on a clean checkout — cheap insurance after Phase 6?
- For parallel subtasks, are **CHANGELOG HTML comment anchors** (`<!-- phase6-t2 -->`) or **one bullet per commit (never edit siblings)** better than honor-system `git add -p`?
- When should **`run_orchestrated_query` success** get a mocked-graph unit test vs staying deferred until a live-stack integration test exists?
- Does orchestrated mode eventually deserve **GraphRAG in `free_query_node`**, or a separate graph variant — and how would that interact with trajectory eval constants?
- After G8 default `false`, is the demo script’s explicit `export ARIA_PLACEHOLDER_API=false` **redundant documentation** or still necessary because operators may override in `.env`?

---

## 7. Single paragraph synthesis

Phase 6 taught me that **an opt-in “second production path” is an integration project**: the scratch graph, MCP adapter, connections layer, DTOs, CLI/API routers, placeholder gates, and telemetry naming must agree — and the demo only makes sense when you accept **different semantics** (vector-only orchestrated trace vs GraphRAG default), not when you pretend they are the same query engine. The deepest surprise was not technical but **operational**: routing and demo commits landed on `dev` without the service module they import, so **green pytest on a dirty tree lied about cloneability** until `e2aadc6`. The compounding lessons pair with Phase 4: **shared CHANGELOG sections and cross-subtask git hygiene are as load-bearing as type contracts**; verify landings with `git show HEAD:<path>` and clean-tree tests; never delete a parallel subtask’s changelog line to “fix” staging; and treat **commit order as the real DAG** when logical dependencies cross subtasks. If I remember one thing in six months: **MVP+ is a flag-driven observability story on top of existing orchestration code, not a new brain — and the flag is worthless if the module it calls is not at HEAD.**
