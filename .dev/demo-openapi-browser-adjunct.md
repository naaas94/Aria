# Browser demo via OpenAPI / Swagger (`/docs`)

**Role:** Optional adjunct for trying the HTTP API in a browser. It does **not** replace the operator golden path (`aria …` in [MVP_PICKUP.md](MVP_PICKUP.md)) or the Phase 6 terminal demo (`.dev/demo/aria-mvp-demo.sh` when present).

**Plan context:** [mvp-phase6-mvp-plus/plan.md](plans/mvp-phase6-mvp-plus/plan.md) — orchestrated routing and portfolio script are separate deliverables; this file only documents how to use FastAPI’s built-in UI.

---

## When to use this vs the CLI

| Goal | Prefer |
|------|--------|
| Full MVP wet run, ingest, portfolio recording | CLI + [MVP_PICKUP.md](MVP_PICKUP.md) Phase 1 sequence |
| “Try `POST /query` without Typer” | `/docs` (this guide) |
| Per-step orchestration story + `aria telemetry` in one terminal session | CLI (`aria query --orchestrated`, when wired) + demo script |
| Production deployment | No `/docs` (see below); use your own client or CLI |

---

## Prerequisites

Same live stack as the golden path:

1. `docker compose up -d neo4j chromadb`
2. LLM env set (`LLM_MODEL`, `LLM_BASE_URL`, API key if needed) — see `.env.example`
3. `export ARIA_PLACEHOLDER_API=false` (code default is `false`; set `true` only for synthetic API responses)
4. `aria init` and `aria ingest <sample>` — full ingest is **CLI-only**; Swagger does not run the ingest pipeline

Check readiness:

```bash
aria status
# optional: curl http://127.0.0.1:8080/ready
```

---

## When `/docs` is available

FastAPI serves interactive OpenAPI UI at **`/docs`** (Swagger UI) and **`/redoc`** unless disabled.

| Condition | `/docs` |
|-----------|---------|
| Local `aria serve` (default) | **Enabled** |
| `DEPLOYMENT_ENV=production` or `prod` | **Disabled** (`docs_url`, `redoc_url`, `openapi_url` set to `None` in `api/main.py`) |

Default bind: `http://127.0.0.1:8080` (`aria serve`; override with `--port` or `API_PORT`).

---

## Start the API

```bash
export ARIA_PLACEHOLDER_API=false
aria serve
# Open http://127.0.0.1:8080/docs
```

Optional smoke before queries: **GET** `/ready` in the same UI (or `curl http://127.0.0.1:8080/ready`).

---

## Standard live query (production path today)

1. In `/docs`, open **POST** `/query` → **Try it out**.
2. Request body (example):

```json
{
  "question": "What are the data minimization requirements?",
  "regulation_id": null,
  "use_graph_rag": true,
  "top_k": 10,
  "orchestrated": false
}
```

3. **Execute**. Inspect:
   - Response body: `answer`, `sources`, `trace`
   - Response headers: `X-ARIA-Mode` → `live` or `placeholder` (not orchestrated)

**Placeholder mode:** set `ARIA_PLACEHOLDER_API=true`, restart `aria serve`, repeat — expect `X-ARIA-Mode: placeholder` and synthetic data without Neo4j/Chroma/LLM.

**Live 503:** missing Neo4j/Chroma returns `503` with `ServiceUnavailableBody` (`detail`, `missing_dependencies`).

---

## Telemetry after a query (browser)

**GET** `/telemetry` with `hours=1` (same aggregate JSON as `aria telemetry --hours 1`).

Use this after a query to see LLM calls, HTTP requests, and agent rows for the window. Per-step orchestration rows (`orchestration.scratch/<node>`) appear in the `agents` section once Phase 6 T3 is deployed and an orchestrated query has run.

---

## Orchestrated mode (MVP+ — when Phase 6 routing is wired)

The request model already includes `orchestrated` (default `false`). **API routing** through `OrchestrationGraph` is Phase 6 T4; until that lands, `orchestrated: true` may still hit `run_compliance_query` — verify against current `api/routers/query.py` before relying on this section.

When wired (per plan):

1. `ARIA_PLACEHOLDER_API=false` and live Neo4j + Chroma (orchestrated mode is **rejected** in placeholder — HTTP **400** with a clear `detail` message).
2. **POST** `/query` body:

```json
{
  "question": "What are the data minimization requirements?",
  "regulation_id": null,
  "use_graph_rag": true,
  "top_k": 10,
  "orchestrated": true
}
```

3. Expect:
   - `X-ARIA-Mode: orchestrated-live` (non-orchestrated live queries keep `live`)
   - `execution_trace` in the JSON body (graph step trace; omitted when not orchestrated)
4. **GET** `/telemetry?hours=1` — look for agent names prefixed with `orchestration.scratch/`

**Important:** Orchestrated answers use the scratch graph’s vector path, **not** the same GraphRAG hybrid path as default `run_compliance_query`. Demo value is routing + trace visibility, not answer parity ([plan Flag 1](plans/mvp-phase6-mvp-plus/plan.md)).

---

## Other useful routes in `/docs`

| Route | Use |
|-------|-----|
| **POST** `/impact` | Impact report for a `regulation_id` from ingest |
| **GET** `/agents` | Agent cards (A2A-style metadata) |
| **GET** `/metrics` | Prometheus scrape text |
| **POST** `/ingest/chunk` | Chunking smoke only — **not** full `aria ingest` pipeline |

OpenAPI path inventory is tested in `tests/eval/expected_api_paths.py`.

---

## curl equivalents (no browser)

```bash
curl -sS -X POST http://127.0.0.1:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the data minimization requirements?","orchestrated":false}'

curl -sS "http://127.0.0.1:8080/telemetry?hours=1"
```

Add `-i` to see `X-ARIA-Mode`. For orchestrated (when wired), set `"orchestrated": true` in the JSON body.

---

## Related artifacts

- [MVP_PICKUP.md](MVP_PICKUP.md) — phases, wet run log, Phase 6 checklist
- [mvp-phase6-mvp-plus/plan.md](plans/mvp-phase6-mvp-plus/plan.md) — `--orchestrated` / `orchestrated: true` wiring
- [architecture/aria/architectural-patterns.md](architecture/aria/architectural-patterns.md) — production call graph vs scratch orchestration
- [notes_for_prod_or_changes.md](notes_for_prod_or_changes.md) — OpenAPI SSOT, ingest HTTP scope
