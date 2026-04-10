# Production notes and notable changes

**Audit findings 22–30 (rationale + file map):** [notes_for_prod_or_changes.md](notes_for_prod_or_changes.md)

---

## HTTP `/ingest/*` vs full ingestion pipeline (documentation decision)

**Problem:** The routes `POST /ingest/text` and `POST /ingest/file` live under `/ingest` and historically sounded like “load documents into ARIA.” In reality they only hash the body, run **in-memory** `chunk_text()`, increment Prometheus counters, and return chunk counts — **no** `ingest_document()`, **no** Neo4j/Chroma writes, **no** entity extraction. Operators or new contributors could assume the HTTP API performs full pipeline ingestion; that assumption is false.

**Framing:** Full document processing (parse → chunk → optional extract → graph → vectors → dedup) is implemented as **`ingest_document()`** in `aria/ingestion/pipeline.py` and is intended to be driven **from development scripts, tests, or future product wiring** — not from the current thin HTTP handlers. Keeping “real” ingestion on the dev side avoids implying a production upload surface before product requirements (auth, quotas, dry-run, cost controls) are defined.

**Decision:** Do **not** change runtime behavior in this step. **Clarify** behavior everywhere it matters:

- OpenAPI: route `summary`/`description`, module docstring, and Pydantic `Field` descriptions on `api/routers/ingest.py` state explicitly that these routes are chunking smoke / metrics only.
- README: endpoint table rows for `/ingest/*` point to the limitation; new section **How to load documents (developer / offline)** lists `ingest_document`, `scripts/seed_corpus.py`, `scripts/seed_graph.py`, and integration tests as the canonical ways to populate the knowledge base.

**Follow-up (not done here):** Optional future work — wire HTTP to the full pipeline behind a flag, add dry-run/estimate mode, or rename routes — only if product asks for user-facing upload.

---

## Neo4j `NEO4J_PASSWORD` default (app vs readiness)

**Change:** `api/connections.py` now uses the same default as `api/readiness.py` (and docker-compose / `.env.example`): `os.getenv("NEO4J_PASSWORD", "aria_dev_password")` instead of defaulting to an empty string when `NEO4J_URI` is set.

**Why:** If `NEO4J_URI` was set but `NEO4J_PASSWORD` was unset, `/ready` could report `neo4j: true` while the app never obtained a Neo4j driver (empty password vs dev default), which was misleading.

**Production:** For anything beyond local dev, set `NEO4J_PASSWORD` explicitly in the environment; do not rely on the baked-in dev default on an exposed host.

## Telemetry write failures (logs + `aria_telemetry_write_errors_total`)

**Change:** HTTP middleware (`api/middleware_telemetry.py`) and agent execution (`aria/agents/base.py`) no longer swallow exceptions from the telemetry store / Prometheus counter updates. On failure they emit a **warning** with the **exception type only** (no traceback), and increment **`aria_telemetry_write_errors_total`** with label `source` = `http_middleware` or `agent`.

**Why:** Silent `except Exception: pass` hid SQLite or counter failures, so ops had no signal when durable telemetry and Prometheus diverged. The new log line plus counter makes failures visible without flooding logs with stack traces.

**Production:** Watch `aria_telemetry_write_errors_total` (and warning logs) if the telemetry DB is under load, disk is full, or metrics registration misbehaves; correlate spikes with DB and `/metrics` health.

---

## Scratch orchestration telemetry (`OrchestrationGraph.execute`)

**Prod path:** `aria/orchestration/scratch/graph.py` — **`OrchestrationGraph.execute`** is the single runtime entry that runs the scratch graph (used from integration/eval tests today; any future HTTP or worker that calls `execute` inherits this behavior automatically).

**Decision (pragmatic first step):** After each graph run completes, record **one** row in **`agent_executions`** and the same **Prometheus** labels as `BaseAgent.run()` (`aria_agent_execution_total`, `aria_agent_execution_duration_seconds`), using a fixed synthetic name **`orchestration.scratch`**. Correlation uses the same **`request_id`** as other writers when structlog context is bound (e.g. HTTP middleware).

**Tradeoffs:**

- **Pros:** Dashboards and `GET /telemetry` JSON that aggregate `agents` / `by_agent` no longer under-count graph-only work; no second table; aligns with existing ops patterns.
- **Cons:** **Aggregate only** — not one row per graph node; per-step detail remains in `ExecutionResult.traces` / `to_trace_dict()` and logs. If a node later calls `BaseAgent.run()`, you can get **both** a per-agent row and one **`orchestration.scratch`** row for the same HTTP request (intentional: layered visibility).
- **Failures:** SQLite write failures increment `aria_telemetry_write_errors_total{source="orchestration"}` and log a warning (same pattern as agents).

**Follow-up (not required for this step):** Per-step persistence, a dedicated `workflow_steps` table, or OpenTelemetry spans if product needs drill-down in the same store as aggregates.
