# ARIA — MVP pickup plan

**Created:** 2026-05-24  
**Branch:** `dev` (clean, up to date with `origin/dev`)  
**Audience:** Returning owner — distilled state, gaps, and curated todos toward a **full MVP**  
**How to use:** Treat this as the living backlog. Strike items, add notes inline, and reconcile stale `.dev/` audits when you touch an area.

---

## Executive summary

ARIA is **architecturally complete as a learning/portfolio system** and **operationally incomplete as a demo-ready product**. The skeleton is strong: GraphRAG retrieval, Pydantic contracts, multi-agent layer, scratch orchestration engine, MCP/A2A protocols, tiered golden-set eval, Prometheus + SQLite telemetry, FastAPI, and a **Typer CLI** (`aria`) wired to shared services.

**Where you left off (commits, Apr 10–24):** Audit remediation (telemetry, readiness, security, OpenAPI SSOT), then **CLI + `aria.services` + health/readiness** (Apr 11–12), mypy CI scope (Apr 12), docs pass (Apr 21), and an **architecture folder** draft (May 24, uncommitted in git status at session start — verify on disk).

**The core blocker for “MVP feels real”** is not missing modules — it is **honest end-to-end validation on live infra** plus **closing known eval/observability gaps** that make CI/nightly misleading or red. Production paths today are **services + direct clients**, not scratch orchestration or MCP.

| Signal | State |
|--------|--------|
| Fast golden tier | **27 passed, 5 skipped** (local run) |
| Medium golden tier (retrieval lens) | **5 failed** — empty `retrieved_context` in all retrieval YAMLs |
| CLI | **Implemented** (`aria init`, `ingest`, `query`, `impact`, `status`, `serve`, `telemetry`, `eval`) |
| Placeholder API default | **`ARIA_PLACEHOLDER_API=true`** — demos work without Neo4j/Chroma/LLM |
| Full ingest | **CLI + scripts only** — HTTP `/ingest/*` is chunk-only by design |
| Orchestration in prod | **Not wired** — `POST /query` → `run_compliance_query()`, not `OrchestrationGraph` |
| Wet run (one session) | **Not documented as completed** — highest-value next step |

---

## What “full MVP” means (working definition)

An MVP is **not** “every protocol and LangGraph parity.” It **is**:

1. **Operator path works on live stack** — `docker compose up` → `aria init` → `aria ingest <doc>` → `ARIA_PLACEHOLDER_API=false` → `aria query` / `aria impact` / `aria telemetry` with intelligible failures when Ollama/Neo4j/Chroma are down.
2. **Knowledge base is populated** — at least one real regulatory sample through the **full** `ingest_document()` pipeline (graph + vectors + entities), not only `seed_graph.py` shortcuts.
3. **Answers are grounded** — live query returns retrieval sources tied to ingested content; impact path returns structured gaps for a known regulation id.
4. **CI tells the truth** — fast tier green; medium/slow tiers either green or explicitly quarantined (no empty-context retrieval theater).
5. **Observability is actionable** — `/ready` + `aria status` + `/telemetry` + `/metrics` sufficient to debug one failed query (latency + LLM rows + request_id).
6. **Docs match code** — `.dev/path_to_release.md` and audit tables updated where they still say “no CLI” or list fixed items as open.

**Explicitly out of MVP scope** (unless you expand scope):

- Cross-process A2A mesh, mounted A2A HTTP router in `api/main.py`
- LangGraph reference parity with scratch
- HTTP upload of full ingest pipeline
- Grafana dashboards / alert rules (nice-to-have)
- GNN layer (doc-only today)

**Optional MVP+ (demo “agents in action”):** Wire scratch `OrchestrationGraph` + live `MCPToolPortsAdapter` behind a flag (`?orchestrated=true` or `aria query --orchestrated`). Valuable for portfolio narrative; not required for regulatory Q&A MVP.

---

## Repository map (where truth lives)

| Area | Path | Notes |
|------|------|--------|
| Learning docs (start here) | [`.dev/docs/00_project_overview.md`](docs/00_project_overview.md) | Best onboarding after this file |
| Architecture folder (May 2026) | [`.dev/architecture/aria/`](architecture/aria/INDEX.md) | Module map, contracts, open questions — **verify before orchestrator/pre-plan consumes** |
| Release gap analysis (partially stale) | [`.dev/path_to_release.md`](path_to_release.md) | Written **before CLI** — §1 “CLI does not exist” is **wrong**; observability/eval gaps mostly still valid |
| Audit tracker | [`.dev/AUDIT_DIGEST.md`](AUDIT_DIGEST.md) | Open: retrieval goldens (#2), multi-hop noop (#8), replay label (#18), nightly 3.13 (#19) |
| Implementation changelog | [`CHANGELOG.md`](../CHANGELOG.md) | Apr 10–12 detail (CLI, health, services, mypy CI) |
| Prod/rationale notes | [`.dev/notes_for_prod_or_changes.md`](notes_for_prod_or_changes.md) | Ingest HTTP vs pipeline, telemetry tradeoffs |
| Quick scratch note | [`.dev/QUICK_TODOS`](QUICK_TODOS) | Local model swap (qwen) |

---

## Current codebase snapshot (verified 2026-05-24)

### Implemented and wired

- **Contracts** — `aria/contracts/*` (v0.1.0), strict tests + golden contract lens
- **Graph** — Neo4j schema generators, named queries, builder MERGE, client wrapper
- **Ingestion** — `ingest_document()`, PDF/HTML parsers, chunker, `build_full_ingest_wiring()`
- **Retrieval** — hybrid + vector + reranker; used by `run_compliance_query()`
- **Services** — `aria/services/compliance_query.py`, `impact_report.py` (API + CLI)
- **CLI** — `pyproject.toml` → `aria = aria.cli.main:main`
- **API** — ingest (chunk), query, impact, agents (cards), telemetry, metrics; placeholder mode
- **Health** — `aria/health/assessment.py`, `/ready` with Neo4j + Chroma gate + informational `llm` + probe cache
- **Eval** — 31+ golden YAMLs, multi-lens runner, security audit, trajectory tests, eval store JSONL
- **Scratch orchestration** — tested; aggregate telemetry `orchestration.scratch`; **not on API/CLI path**
- **MCP / A2A** — implemented; MCP adapter **not instantiated** in production paths

### Known gaps (code-evidenced)

| ID | Gap | Severity | Evidence |
|----|-----|----------|----------|
| G1 | Retrieval goldens fail medium tier | **P0** | All 5 `cases/retrieval/*.yaml` have `retrieved_context: ""` |
| G2 | No replay fixtures | High | `tests/eval/golden_set/replay/` only `.gitkeep`; CI label still says “includes replay” |
| G3 | `requires_multi_hop` is declarative only | Medium | `runner.py` sets `multi_hop_declared`, no hop validation |
| G4 | No `tier: slow` cases | Medium | Reserved in conftest; nothing expensive (live LLM) in goldens |
| G5 | Prometheus gaps | Medium | No `aria_http_request_duration_seconds`, `aria_llm_cost_usd_total`, `aria_graph_query_duration_seconds`; `INGESTION_DURATION` not observed in pipeline |
| G6 | LLM telemetry swallow in `LLMClient` | High | `client.py` ~237, ~277: `except Exception: pass` on `record_llm_call` (middleware/agents fixed; this path not) |
| G7 | Production bypasses orchestration/MCP | Design | See [architectural-patterns.md](architecture/aria/architectural-patterns.md) production call graph |
| G8 | Placeholder default | UX | `ARIA_PLACEHOLDER_API` defaults true — easy to think system “works” without backends |
| G9 | `.dev/path_to_release.md` stale | Docs | Claims no CLI; list as doc-debt |
| G10 | Architecture folder may be untracked | Process | Git status showed `?? .dev/architecture/aria/*` — commit when approved per project-architecture skill |

### Test signals (local, this session)

```text
pytest tests/eval/golden_set/test_goldens.py --golden-tier=fast  → 27 passed, 5 skipped
pytest ... --golden-tier=medium                                 → 5 failed (retrieval-q1..q5)
mypy aria api                                                   → in CI; run locally after changes
```

---

## Commit narrative (since pause)

| Date | Commit | Theme |
|------|--------|--------|
| 2026-04-10 | `6875ab2` | Paused with audit digest open; retrieval goldens empty called out |
| 2026-04-09 | `4629209`, `f90698f` | Telemetry enhancements, bug fixes |
| 2026-04-11 | `6d8d9a9`, `207191b` | **CLI implemented**; CLI testing notes |
| 2026-04-12 | `68ab173`, `000e1f3` | Backlog + **mypy** scope/overrides; CI typecheck |
| 2026-04-21 | `a8a599e`, `08286a5` | Docs / prep |
| 2026-05-24 | `21c415c` | Architecture folder for Aria (draft) |

**Interpretation:** The “path to release” doc frozen on Apr 10 is **behind** the Apr 11–12 CLI/services/health work. Trust **code + CHANGELOG.md** over `path_to_release.md` §1.

---

## Open architectural decisions

From [`.dev/architecture/aria/open-questions.md`](architecture/aria/open-questions.md) — resolve during MVP to avoid drift:

| Question | MVP recommendation (suggested) |
|----------|----------------------------------|
| HTTP ingest chunk-only vs full pipeline? | **Keep split** for MVP; document; full ingest via `aria ingest` only |
| LangGraph reference long-term? | **Mark illustrative** in README/module-map; no parity work for MVP |
| Placeholder default? | **Resolved (2026-05-30):** code default flipped to `false` on `dev` (G8 / T1). Use `ARIA_PLACEHOLDER_API=true` for placeholder/demo without backends. |
| A2A cross-process? | **Out of scope** — in-process registry + tests only |
| Telemetry retention | **Document** `ARIA_TELEMETRY_RETENTION_DAYS` in MVP runbook; enable for long demos |
| Scratch + MCP as production runtime? | **Defer** unless doing MVP+ demo; else add one line to README: “production path = services” |

**Resolved in architecture doc:** Query path uses **`run_compliance_query`**, not scratch `free_query_node`.

---

## Curated MVP backlog

Phases are ordered by **unblock demo → honest CI → observability → narrative polish → doc hygiene**.

### Phase 0 — Re-onboarding (½ day, no code)

- [ ] Read [00_project_overview.md](docs/00_project_overview.md) § Code Map + [architecture/aria/INDEX.md](architecture/aria/INDEX.md)
- [ ] `cp .env.example .env`; `docker compose up -d neo4j chromadb`; start Ollama (or set cloud LLM env)
- [ ] `pip install -e ".[dev]"` (or `uv sync`)
- [ ] `aria status` — fix until Neo4j + Chroma pass (LLM may fail independently)
- [ ] Run **wet run script** (Phase 1) and append “Wet run log” section at bottom of this file

### Phase 1 — Golden path wet run (1 day, fixes as discovered)

**Goal:** One documented session that proves live MVP.

```bash
docker compose up -d neo4j chromadb
# Ollama or LLM_* env configured
export ARIA_PLACEHOLDER_API=false

aria init
aria ingest path/to/sample.pdf   # or scripts/seed_corpus.py if PDF path blocked
aria query "Which requirements affect our systems with no policy coverage?"
aria impact <REGULATION_ID_FROM_GRAPH>
aria telemetry --hours 1
aria serve   # optional: curl POST /query with same env
pytest tests/integration -m integration   # if services up
```

- [ ] Record failures (connection, schema, LLM timeout, empty retrieval) inline in **Wet run log**
- [ ] Fix blockers minimalistically (prefer wiring/config over new features)
- [ ] Confirm `aria ingest` preflight matches expectations (requires Neo4j + Chroma + **LLM** — stricter than `/ready`)

### Phase 2 — Eval honesty (P0, 0.5–1 day)

Pick **one** strategy for retrieval goldens (do not leave all three half-done):

- [ ] **Option A (fastest):** Populate `retrieved_context` in each `cases/retrieval/q*.yaml` with deterministic text containing all `expected_components` (synthetic but honest for lens)
- [ ] **Option B:** Add `expect.replay` + record one fixture under `tests/eval/golden_set/replay/` from a live run
- [ ] **Option C:** Quarantine retrieval cases to `tier: fast` skip or mark `xfail` with linked issue until wired to real retriever output

Also:

- [ ] Fix CI step name in `.github/workflows/ci.yml` (“includes replay”) or add minimal replay case (**G2**, audit #18)
- [ ] Implement or remove `requires_multi_hop` (**G3**, audit #8)
- [ ] Add 1–2 `tier: slow` cases (live `HybridRetriever` or recorded LLM output) — **G4**
- [ ] Re-run: `pytest tests/eval/golden_set/test_goldens.py --golden-tier=slow`

### Phase 3 — Observability completeness (1 day)

- [ ] **G6:** Replace `except Exception: pass` in `aria/llm/client.py` with warning + `aria_telemetry_write_errors_total{source="llm"}` (match middleware pattern)
- [ ] **G5:** Add and observe Prometheus histograms: HTTP request duration, graph query duration; increment LLM cost counter when `cost_usd` present
- [ ] Observe `INGESTION_DURATION` in `ingest_document()` completion path
- [ ] Optional: per-request cost rollup in telemetry store by `request_id`
- [ ] Document Ollama `cost_usd` null behavior in README or `.env.example`

### Phase 4 — Product defaults & operator UX (0.5 day)

- [x] Decide placeholder default for “MVP branch” (**G8**) — flipped code default to `false` on `dev` (T1)
- [x] README Quickstart: explicit “live mode” block with `ARIA_PLACEHOLDER_API=false`
- [x] **QUICK_TODOS:** Local model swap — `LLM_MODEL` / `LLM_BASE_URL` in wet run log template (T3-amend)
- [x] Optional: `aria query --json` smoke in CI via CliRunner (T4)

### Phase 5 — Doc & architecture hygiene (0.5 day)

- [ ] Rewrite [path_to_release.md](path_to_release.md) §1 CLI section OR add banner “Superseded by CHANGELOG 2026-04-11”
- [ ] Sync [AUDIT_DIGEST.md](AUDIT_DIGEST.md) open table after Phase 2–3
- [ ] Commit or approve [architecture/aria/](architecture/aria/) per user ownership model
- [ ] Add 1-line “production call graph” to README (from architectural-patterns.md)

### Phase 6 — MVP+ (optional, portfolio demo)

Only if MVP Phases 0–4 are green:

- [ ] Wire `MCPToolPortsAdapter` with live Neo4j/Chroma/LLM; use in scratch nodes
- [ ] `aria query --orchestrated` or API flag routing through `OrchestrationGraph.execute`
- [ ] Per-step trace persistence (beyond aggregate `orchestration.scratch` row)
- [ ] Record asciicast / demo script from wet run

---

## CI / nightly expectations

| Workflow | What it proves | Known mismatch |
|----------|----------------|----------------|
| `ci.yml` | Unit, fast goldens, mypy `aria api`, security, eval subset | Medium retrieval not in fast tier |
| `nightly.yml` | Neo4j + Chroma services, slow goldens, integration | Python 3.12 only vs CI 3.13 matrix (#19) |

**Local pre-push checklist:**

```bash
mypy aria api
pytest tests/unit -q
pytest tests/eval/golden_set/test_goldens.py --golden-tier=fast -q
pytest tests/eval/test_api_contracts.py tests/eval/test_security_audit.py -q
```

---

## Suggested first session (today)

1. Phase 0 checklist (15 min)  
2. Phase 1 wet run — **write failures into Wet run log below** (2–4 hr)  
3. If retrieval returns empty in live mode, fix data path (seed/ingest) before touching goldens  
4. Phase 2 Option A or B so medium tier matches reality  

---

## Wet run log (2026-05-30 session below; blank template at bottom)

```text
Date: 2026-05-30 (T6 golden-path session)

Environment:
  OS: Windows 10 (10.0.19045)
  Python: 3.14.2
  Docker: 29.1.3
  Neo4j: neo4j:5.26.2-community (docker compose; healthy)
  Chroma: chromadb/chroma:1.5.6 (docker compose; compose healthcheck reports unhealthy,
          but GET http://localhost:8000/api/v2/heartbeat returns 200 — usable)
  LLM (live path): gpt-4o-mini via https://api.openai.com/v1
    (Ollama on localhost:11434 present but .env.example model ollama/llama3.2 not installed;
     cold-start probes exceeded 12s timeout on local models — see decision log)

ARIA_PLACEHOLDER_API=false (confirmed for all live CLI/API steps below)

docker compose up -d neo4j chromadb → exit 0 (~27s pull/start; neo4j healthy ≤60s;
  chroma remained "unhealthy" in `docker compose ps` while v2 heartbeat OK)

aria status → exit 0
  neo4j ok | chroma ok | llm ok (with LLM_MODEL=gpt-4o-mini, LLM_BASE_URL=https://api.openai.com/v1)
  T5 note present: "aria ingest additionally requires LLM. aria status exits 0 even when LLM is unavailable."

aria init → exit 0

aria ingest tests/fixtures/sample_regulation.html → exit 0
  graph_written: true | vector_indexed: true
  regulation_ids: reg-gdpr, reg-eu-ai-act, article-1-subject-matter-and-scope
  (Neo4j warning: IngestionRecord.pipeline_complete property missing on first dedup query)

aria query "What are the data minimization requirements?" → exit 0
  Live answer + 1 source chunk (score ~0.27); notes GDPR minimization not explicit in chunk text

aria impact reg-gdpr → exit 0
  Mode: live | Requirements: 0 (no AFFECTS/ADDRESSED_BY edges in graph from ingest-only path;
  Neo4j warnings for missing relationship types)

aria telemetry --hours 1 → exit 0 (JSON summary; 2 LLM calls logged)

aria serve --port 8080 (optional) + curl http://127.0.0.1:8080/ready → HTTP 200
  {"status":"ready","neo4j":true,"chroma":true,"llm":true}

Preflight vs readiness assertion (LLM unreachable):
  aria ingest (LLM_MODEL=ollama/nonexistent-model-xyz) → exit 1
    missing: llm: ... model 'nonexistent-model-xyz' not found
  aria status (same LLM env) → exit 0, llm fail
  aria serve --host 127.0.0.1 --port 8080 + curl /ready → HTTP 200
    {"status":"ready","neo4j":true,"chroma":true,"llm":false,"errors":{"llm":"..."}}

pytest tests/integration -m integration → 25 passed (1.56s)
  Note: run with ARIA_PLACEHOLDER_API=true (default for mocked TestClient suite);
  accidental ARIA_PLACEHOLDER_API=false during pytest caused 2 failures on X-ARIA-Mode assertions.

Failures / surprises:
  - Chroma docker healthcheck false negative (curl missing or v1 vs v2 in compose health test).
  - .env.example LLM model (ollama/llama3.2) not in local Ollama; cloud OpenAI used for live path.
  - aria impact returns 0 requirements after successful ingest (graph lacks impact-chain edges).
  - First integration pytest run failed when shell still had ARIA_PLACEHOLDER_API=false from live steps.

Fixes applied (commit refs): no code fixes required this session (documentation only).

Sign-off (MVP golden path OK? Y/N): Y
  All Phase 1 CLI steps exit 0 on live stack; ingest preflight strictly requires LLM;
  /ready returns 200 with llm:false when LLM probe fails. Caveats: impact chain not populated
  from sample ingest alone; operator should set LLM_* explicitly for cloud vs Ollama.
```

---

## Wet run log template (copy for next session)

Paste a new fenced block below for each live session. The 2026-05-30 golden-path run is recorded in the section above.

```text
Date:
Environment: (OS, Python version, Neo4j version, Chroma version)
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
# For Ollama: LLM_MODEL=ollama/llama3.1:8b  LLM_BASE_URL=http://localhost:11434 — see .env.example
ARIA_PLACEHOLDER_API=false

aria status →
aria init →
aria ingest →
aria query →
aria impact →
aria telemetry →

Failures / surprises:

Fixes applied (commit refs):

Sign-off (MVP golden path OK? Y/N):
```

---

## References

- Architecture INDEX: [`.dev/architecture/aria/INDEX.md`](architecture/aria/INDEX.md)
- Audit open items: [`.dev/AUDIT_DIGEST.md`](AUDIT_DIGEST.md)
- Tradeoffs / scope: [`.dev/docs/11_tradeoffs_and_concerns.md`](docs/11_tradeoffs_and_concerns.md)
- Evaluation methodology: [`.dev/docs/10_evaluation_agentic_systems.md`](docs/10_evaluation_agentic_systems.md)

---

*Next edit:* After wet run, move completed Phase items to a “Done” section with date; add new discoveries under Gaps table.
